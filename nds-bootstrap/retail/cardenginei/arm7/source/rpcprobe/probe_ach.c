// probe_ach.c - see probe_ach.h.
//
// Memory: the set and the checker's state live in DSIRPC_ACH_LOCATION (main
// RAM that the bootloader keeps the ROM cache out of; locations.h). The set
// file is copied there whole: its 64-byte header, then the pass lane's
// program, the frame lane's (version 4), then (version 3 and up) the in-game
// menu's list. The state follows it: the pass lane's (memory values, hit
// counts), the frame lane's twice (the VM that checks and the one that
// samples) and the frame lane's ring of samples. Above ACH_SET_SPACE (DSiRPC
// builds sets to fit it) come 4 KB to read RPCUNLK.BIN into when the game
// starts, then the per-frame capture's ring (probe_watch.c).
//
// The two lanes. RetroAchievements' rules are checked once a frame on an
// emulator: "changed since the last frame", hit counts of frames, a flag
// that's only set for one frame. The pass lane reads the game's memory at
// the start of each pass, and a pass over a big set takes several frames,
// so what happens in between is missed. The frame lane is the achievements
// DSiRPC picked as needing every frame (core/offline.py), few enough to
// sample every frame: ProbeAch_Sample() reads every memory value they use at
// the start of every VBlank (after the ARM9 has written its data cache back
// to main RAM, so the ARM7 sees what the game wrote; probe_watch.c), all at
// once, into a ring of samples. The checking takes them in order, so every
// frame is checked as it was, however late. If the checking falls so far
// behind that the ring is full, frames aren't sampled until there's room
// (a gap, counted in the report).
//
// Time: the checking runs while the game's ARM7 idles, from nds-bootstrap's
// swiHalt hook (ProbeAch_Idle()), outside interrupts, so the game's own
// interrupts and threads come first. It stops for nds-bootstrap's ARM9 ROM
// reads (served in the same hook) and after RPCPROBE_ACH_IDLE_LINES_PER_VISIT
// scanlines a visit and RPCPROBE_ACH_IDLE_LINES_PER_FRAME a frame, leaving
// the rest of the idle time to the ARM7's sleep. The frame lane's samples
// come first, then the pass lane, which can stop after any 8 memory values
// or conditions and carry on next time. A game whose swiHalt nds-bootstrap
// couldn't hook gets it all in the VBlank instead (ProbeAch_Tick()), in
// RPCPROBE_ACH_LINES_PER_VBLANK scanlines a tick. Before anything runs, the
// set's CRC-32 is checked, a slice a tick.
//
// Unlocks: each one waits in a small queue until ProbeAch_SaveOne() writes
// it to its own RPCUNLK.BIN slot, outside interrupts with nds-bootstrap's SD
// card lock held (probe_hook.c's SD card rule). The slot's time is the
// console's clock, read when the achievement unlocks (clockNow() below).
// The VBlanks stop while the console sleeps (lid closed) and while the
// in-game menu is open, so the launcher's clock (RPCHAND.TXT's time=) plus
// the VBlanks since falls behind by that long; it's only used when the clock
// can't be read just then. Achievements already in RPCUNLK.BIN when the game
// starts aren't checked again.
//
// In-game menu: a version 3 or 4 set has a list of every achievement of the
// game after the programs (dsirpc_ach_menu.h). Once the set's CRC has been
// checked, this game's unlocks waiting in RPCUNLK.BIN and each new unlock
// are marked in it (earned on the console, when, and an unlock number for
// the menu's "new" marks), and so are the ones DSiRPC unlocked itself and
// tells the console about (ProbeAch_Push()); the anchor in the header's
// bytes 40-63 says where it is. nds-bootstrap's in-game menu reads it
// (arm9_igm's dsirpc_ach.c). Version 2 sets have no list and are still
// checked.

#include <nds/ndstypes.h>
#include "rpcprobe_build.h"
#include "locations.h"
#include "my_fat.h"
#include "dsirpc_ach_menu.h"
#include "probe_ach.h"
#include "probe_ach_vm.h"
#include "probe_watch.h"

#ifndef ACH_REG_VCOUNT // (the PC tests have their own)
#define ACH_REG_VCOUNT      (*(vu16*)0x04000006)
#define ACH_RAM             ((const u8 *)0x02000000) // RetroAchievements address 0 on the DS
#endif
#define ACH_LINES_PER_FRAME 263
#define ACH_HEADER_SIZE     64
#define ACH_RAM_SIZE        0x400000
#define ACH_RECENT          8

// RPCUNLK.BIN (DSiRPC's core/offline.py): 256 slots of 16 bytes, slot 0 the
// header ("DRUL", u16 version 1, u16 slot size, u16 slot count)
#define ACH_UNLOCK_SLOT     16
#define ACH_UNLOCK_SLOTS    256
#define ACH_UNLOCK_FILE     (ACH_UNLOCK_SLOT * ACH_UNLOCK_SLOTS)
#define ACH_UNLOCK_MAGIC    0x4C555244 // "DRUL"
#define ACH_UNLOCK_FORMAT   0x00100001 // version 1, 16-byte slots
#define ACH_SET_SPACE       (DSIRPC_ACH_SIZE - ACH_UNLOCK_FILE - DSIRPC_WATCH_RING_SIZE) // DSiRPC's offline.ACH_MEMORY
#define ACH_PENDING         8          // unlocks waiting to be saved (a power of 2)
#define ACH_VBLANKS_X1000   59826      // VBlanks in 1000 s (59.8261 Hz)
#define ACH_FRAME_SLOTS     8          // the frame lane's ring of samples (a power of 2;
                                       // DSiRPC's offline.FRAME_SLOTS)
#define ACH_PUSHED          8          // DSiRPC's unlocks waiting to be marked (a power of 2)
#define ACH_CLEAN_WAIT      3          // scanlines a sample waits for the ARM9's cache write-back

enum { STAGE_OFF, STAGE_CHECKING, STAGE_RUNNING };

s16 probeAchLoaded = PROBE_ACH_NONE;
u16 probeAchFrameLane = 0;
u32 probeAchStamp = 0;
u16 probeAchTriggered = 0;
u16 probeAchSaved = 0;
u16 probeAchLost = 0;
u16 probeAchSaveFailed = 0;
u16 probeAchWaiting = 0;

static u8 stage = STAGE_OFF;
static AchVm vm;                       // the pass lane
static AchVm frameVm, sampleVm;        // the frame lane: checking, sampling
static u32 *ring;                      // its samples: ACH_FRAME_SLOTS x frameMem values
static u16 frameMem;                   // memory values in a sample (0: no frame lane)
static volatile u8 ringHead, ringTail; // the VBlank adds at ringHead, the checking takes from ringTail
static volatile u8 busy;               // the idle side is part way through a turn of checking
static u8 cleanOk;                     // the last sample got the ARM9's write-back
static u32 cleanSeen;                  // probe_watch.c's write-back count at the last sample
static u16 idleLines;                  // scanlines the idle side used this frame
static ProbeAchStats stats;
static u32 bodySize, crcPos, crc, crcWanted;   // body: the programs, then the list

// The in-game menu's list and the anchor (dsirpc_ach_menu.h)
#define ACH_ANCHOR ((volatile DsirpcMenuAnchor *)(DSIRPC_ACH_LOCATION + DSIRPC_MENU_ANCHOR_OFFSET))
static u32 listOffset, listSize;       // where the set's list is, from DSIRPC_ACH_LOCATION
static DsirpcListEntry *listEntries;   // set once the CRC has been checked
static u16 listCount;
static u16 unlockSeq;                  // the console's unlocks this game
static u16 menuSeen;                   // unlockSeq when the menu last opened
static u8 menuOpen;
static u32 recent[ACH_RECENT];
static u8 recentCount, recentNext;

// Saving: the VBlank side adds at pendHead, the saving side takes from
// pendTail, each only moving its own index.
static aFile unlockFile;
static u16 unlockNext;                 // the next free slot (0: no RPCUNLK.BIN to save to)
static u32 pendId[ACH_PENDING], pendWhen[ACH_PENDING];
static volatile u8 pendHead, pendTail;
static u32 clockStart, clockSeconds;   // the console's clock (seconds since 2000) at clockSeconds 0; seconds of VBlanks since
static u32 clockPart;                  // the part second, in 1/1000 VBlanks
static u8 clockKnown;                  // clockStart is a time (the launcher's, or a reading)
static u8 clockTried;                  // the console's clock was read (or couldn't be) this tick

// DSiRPC's own unlocks (ProbeAch_Push()): the VBlank adds at pushHead, the
// checking takes from pushTail
static u32 pushId[ACH_PUSHED], pushWhen[ACH_PUSHED];
static volatile u8 pushHead, pushTail;

// The console's clock (the RTC): year (0 = 2000), month, day, weekday, hour,
// minute, second. nds-bootstrap's rtcGetTimeAndDate() (clock.c, which its
// in-game menu also calls from the VBlank interrupt), with interrupts off,
// and only if the game isn't in the middle of talking to the clock itself
// (chip select high). 0: not read.
#ifndef ACH_RTC_READ // (the PC tests have their own)
#define ACH_REG_RTC         (*(vu8*)0x04000138)
#define ACH_REG_IME         (*(vu32*)0x04000208)
void rtcGetTimeAndDate(u8 *time);
static int rtcRead(u8 *t) {
	if (ACH_REG_RTC & 0x04) return 0;
	u32 ime = ACH_REG_IME;
	ACH_REG_IME = 0;
	rtcGetTimeAndDate(t);
	ACH_REG_IME = ime;
	return 1;
}
#define ACH_RTC_READ(t) rtcRead(t)
#endif

static const u16 daysBefore[12] = { 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334 };

// When an achievement unlocks: the console's clock, in seconds since
// 2000-01-01 (local time, like the launcher's time=), read at most once a
// tick (the tick's other unlocks share it) and kept as the new clockStart,
// so the VBlanks carry on from it. A reading that can't be right (a field out
// of range, or more than a minute before the launcher's time plus the
// VBlanks, which can only fall behind) is ignored. Without a reading: the
// last one (or the launcher's time) plus the VBlanks since. 0: no clock.
static u32 clockNow(void) {
	u8 t[7];
	if (!clockTried && ACH_RTC_READ(t)) {
		u32 y = t[0], m = t[1] - 1u, d = t[2] - 1u;
		if (y < 100 && m < 12 && d < 31 && t[4] < 24 && t[5] < 60 && t[6] < 60) {
			u32 days = y * 365 + (y + 3) / 4 + daysBefore[m] + d + (m > 1 && !(y & 3));
			u32 now = ((days * 24 + t[4]) * 60 + t[5]) * 60 + t[6];
			if (now + 60 >= clockStart + clockSeconds) {
				clockStart = now - clockSeconds;
				clockKnown = 1;
			}
		}
	}
	clockTried = 1;
	return clockKnown ? clockStart + clockSeconds : 0;
}

static u16 linesSince(u16 start) {
	u16 now = ACH_REG_VCOUNT & 0x1FF;
	return (now >= start) ? now - start : now + ACH_LINES_PER_FRAME - start;
}

static u32 rd32(const u8 *p) {
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24);
}

// A slot's check: 0x5AA5 + its first seven little-endian u16s
static u16 slotCheck(const u8 *s) {
	u32 sum = 0x5AA5;
	for (int i = 0; i < 14; i += 2) sum += s[i] | (s[i + 1] << 8);
	return (u16)sum;
}

// CRC-32 (zlib's), a nibble at a time: a 64-byte table instead of 1 KB
static const u32 crcTable[16] = {
	0x00000000, 0x1DB71064, 0x3B6E20C8, 0x26D930AC, 0x76DC4190, 0x6B6B51F4, 0x4DB26158, 0x5005713C,
	0xEDB88320, 0xF00F9344, 0xD6D6A3E8, 0xCB61B38C, 0x9B64C2B0, 0x86D3D2D4, 0xA00AE278, 0xBDBDF21C
};

// The anchor, when the game starts (the header has just been read over it,
// or there's no set): which game, `status`, no list yet, the menu closed
static void anchorStart(const void *ndsHeader, s16 status) {
	volatile DsirpcMenuAnchor *a = ACH_ANCHOR;
	const u8 *game = (const u8 *)ndsHeader + 0x0C;
	for (int i = 0; i < 4; i++) a->game[i] = game[i];
	a->status = status;
	a->unlocks = 0;
	a->newFrom = 0;
	a->open = 0;
	a->list = 0;
	a->reserved = 0;
	a->magic = DSIRPC_MENU_ANCHOR_MAGIC;
}

static void loadFailed(s16 why) {
	probeAchLoaded = why;
	stage = STAGE_OFF;
	ACH_ANCHOR->status = why;
}

// A valid RPCUNLK.BIN slot of this game: its achievement ID, else 0
static u32 slotId(const u8 *s, u32 game) {
	u32 id = rd32(s);
	return (id && rd32(s + 4) == game && slotCheck(s) == (s[14] | (s[15] << 8))) ? id : 0;
}

// RPCUNLK.BIN, read into the space the set leaves free: unlocks are saved
// after its last used slot (a half-written slot counts as used), and this
// game's unlocks already in it aren't checked again. No file (the game
// wasn't started from the launcher) or not ours: nothing gets saved.
static void loadUnlocks(u32 game) {
	getBootFileCluster(&unlockFile, "RPCUNLK.BIN", 0);
	if (unlockFile.firstCluster == CLUSTER_FREE) return;

	const u8 *buf = (const u8 *)DSIRPC_ACH_LOCATION + ACH_SET_SPACE;
	fileRead((char *)buf, &unlockFile, 0, ACH_UNLOCK_FILE);
	if (rd32(buf) != ACH_UNLOCK_MAGIC || rd32(buf + 4) != ACH_UNLOCK_FORMAT ||
	    (buf[8] | (buf[9] << 8)) != ACH_UNLOCK_SLOTS) {
		return;
	}
	u16 next = 1;
	for (u16 i = 1; i < ACH_UNLOCK_SLOTS; i++) {
		const u8 *s = buf + i * ACH_UNLOCK_SLOT;
		u32 id = slotId(s, game);
		if (rd32(s) | rd32(s + 4) | rd32(s + 8) | rd32(s + 12)) next = i + 1;
		if (id && (AchVm_SetUnlocked(&vm, id) | AchVm_SetUnlocked(&frameVm, id))) probeAchWaiting++;
	}
	unlockNext = next;
}

// The menu's list: an achievement earned, on the console (flag
// DSIRPC_LIST_ON_CONSOLE) or by DSiRPC (DSIRPC_LIST_EARNED). when: 0 = not
// known (no clock); seq: its unlock number this game, 0 for one that was
// already waiting in RPCUNLK.BIN.
static DsirpcListEntry *listFind(u32 id) {
	for (u16 i = 0; i < listCount; i++) {
		if (listEntries[i].id == id) return &listEntries[i];
	}
	return 0;
}

static void listMark(u32 id, u32 when, u16 seq, u8 flag) {
	DsirpcListEntry *e = listFind(id);
	if (!e) return;
	e->flags |= flag;
	if (when) e->when = when;
	if (seq) e->seq = seq;
}

// Once the CRC has been checked (the list mustn't change before): the
// list, if the set has a good one, with this game's waiting unlocks marked.
static void listStart(void) {
	u8 *base = (u8 *)DSIRPC_ACH_LOCATION;
	const DsirpcList *l = (const DsirpcList *)(base + listOffset);
	if (listSize < sizeof(DsirpcList) || l->magic != DSIRPC_LIST_MAGIC ||
	    l->version != DSIRPC_LIST_VERSION ||
	    sizeof(DsirpcList) + l->count * sizeof(DsirpcListEntry) + l->textSize > listSize) {
		return;
	}
	listEntries = (DsirpcListEntry *)(base + listOffset + sizeof(DsirpcList));
	listCount = l->count;
	if (unlockNext) {
		u32 game = rd32(base + 8);
		const u8 *buf = base + ACH_SET_SPACE;
		for (u16 i = 1; i < ACH_UNLOCK_SLOTS; i++) {
			const u8 *s = buf + i * ACH_UNLOCK_SLOT;
			u32 id = slotId(s, game);
			if (id) listMark(id, rd32(s + 8), 0, DSIRPC_LIST_ON_CONSOLE);
		}
	}
	ACH_ANCHOR->list = listOffset;
}

void ProbeAch_Load(const void *ndsHeader) {
	listEntries = 0; // (no list until the CRC has been checked)
	listCount = 0;
	aFile file;
	getBootFileCluster(&file, "RPCSET.BIN", 0);
	if (file.firstCluster == CLUSTER_FREE) { // no set: nothing to do
		anchorStart(ndsHeader, DSIRPC_MENU_NO_SET);
		return;
	}

	u8 *base = (u8 *)DSIRPC_ACH_LOCATION;
	fileRead((char *)base, &file, 0, ACH_HEADER_SIZE);
	anchorStart(ndsHeader, DSIRPC_MENU_CHECKING);

	// "DRSE", version 2-4, header size 64, game code, RA game id, stamp,
	// achievements, flags, program size, state size, (3:) list size,
	// (4:) frame lane program size
	u16 version = base[4] | (base[5] << 8);
	if (base[0] != 'D' || base[1] != 'R' || base[2] != 'S' || base[3] != 'E' ||
	    version < 2 || version > 4 || (base[6] | (base[7] << 8)) != ACH_HEADER_SIZE) {
		loadFailed(PROBE_ACH_E_HEADER);
		return;
	}
	const u8 *game = (const u8 *)ndsHeader + 0x0C;
	for (int i = 0; i < 4; i++) {
		if (base[8 + i] != game[i]) { // left over from another game
			loadFailed(PROBE_ACH_E_GAME);
			return;
		}
	}
	u32 programSize = rd32(base + 24);
	u32 stateSize = rd32(base + 28);
	listSize = (version >= 3) ? rd32(base + 32) : 0;
	u32 frameSize = (version >= 4) ? rd32(base + 36) : 0;
	const u8 *frameProgram = base + ACH_HEADER_SIZE + programSize;
	listOffset = ACH_HEADER_SIZE + programSize + frameSize;
	bodySize = programSize + frameSize + listSize;
	u32 stateOffset = (ACH_HEADER_SIZE + bodySize + 3) & ~3u;
	if (programSize > ACH_SET_SPACE || frameSize > ACH_SET_SPACE || listSize > ACH_SET_SPACE ||
	    stateSize > ACH_SET_SPACE || stateOffset + stateSize > ACH_SET_SPACE ||
	    ((listSize || frameSize) && ((programSize | frameSize) & 3))) {
		loadFailed(PROBE_ACH_E_SIZE);
		return;
	}

	fileRead((char *)base + ACH_HEADER_SIZE, &file, ACH_HEADER_SIZE, bodySize);
	if (AchVm_Load(&vm, base + ACH_HEADER_SIZE, programSize, base + stateOffset, stateSize,
	               ACH_RAM, ACH_RAM_SIZE) != ACHVM_OK) {
		loadFailed(PROBE_ACH_E_PROGRAM);
		return;
	}
	// The frame lane: two states (checking, sampling), then the ring
	frameMem = 0;
	frameVm.nAch = 0;
	if (frameSize) {
		u32 at = stateOffset + stateSize;
		u32 need = AchVm_StateSize(frameProgram, frameSize);
		if (!need) {
			loadFailed(PROBE_ACH_E_PROGRAM);
			return;
		}
		u32 ringAt = at + 2 * need;
		if (ringAt > ACH_SET_SPACE || AchVm_Load(&frameVm, frameProgram, frameSize, base + at, need,
		                                         ACH_RAM, ACH_RAM_SIZE) != ACHVM_OK) {
			loadFailed(PROBE_ACH_E_SIZE);
			return;
		}
		AchVm_Load(&sampleVm, frameProgram, frameSize, base + at + need, need, ACH_RAM, ACH_RAM_SIZE);
		u32 mem = frameVm.nPlain + frameVm.nMod;
		if (ringAt + ACH_FRAME_SLOTS * 4 * mem > ACH_SET_SPACE) {
			loadFailed(PROBE_ACH_E_SIZE);
			return;
		}
		ring = (u32 *)(base + ringAt);
		frameMem = (u16)mem;
	}
	loadUnlocks(rd32(base + 8));

	crcWanted = probeAchStamp = rd32(base + 16);
	crc = 0xFFFFFFFF;
	crcPos = 0;
	stage = STAGE_CHECKING;
}

static void onTriggered(u32 id, void *ud) {
	(void)ud;
	probeAchTriggered++;
	recent[recentNext] = id;
	recentNext = (recentNext + 1) % ACH_RECENT;
	if (recentCount < ACH_RECENT) recentCount++;
	u32 when = clockNow();

	// In the menu's list, whether or not it can be saved
	listMark(id, when, ++unlockSeq, DSIRPC_LIST_ON_CONSOLE);
	ACH_ANCHOR->unlocks = unlockSeq;

	// Queued for ProbeAch_SaveOne(), with when it happened
	u8 head = pendHead, next = (head + 1) & (ACH_PENDING - 1);
	if (!unlockNext || next == pendTail) { // nowhere to save it, or nothing has saved for a while
		probeAchLost++;
		return;
	}
	pendId[head] = id;
	pendWhen[head] = when;
	pendHead = next;
}

// The VBlank budget: what's left of RPCPROBE_ACH_LINES_PER_VBLANK
static int keepGoing(void *ud) {
	return linesSince(*(const u16 *)ud) < RPCPROBE_ACH_LINES_PER_VBLANK;
}

// The stamp is the CRC-32 of the body: the programs, then the list
static void checkStamp(u16 start) {
	const u8 *p = (const u8 *)DSIRPC_ACH_LOCATION + ACH_HEADER_SIZE;
	u32 c = crc, pos = crcPos;
	while (pos < bodySize) {
		u32 end = pos + 256;
		if (end > bodySize) end = bodySize;
		for (; pos < end; pos++) {
			c ^= p[pos];
			c = (c >> 4) ^ crcTable[c & 15];
			c = (c >> 4) ^ crcTable[c & 15];
		}
		if (!keepGoing(&start)) break;
	}
	crc = c;
	crcPos = pos;
	if (pos < bodySize) return;

	if ((crc ^ 0xFFFFFFFF) != crcWanted) {
		loadFailed(PROBE_ACH_E_STAMP);
		return;
	}
	probeAchLoaded = (s16)(vm.nAch + frameVm.nAch);
	probeAchFrameLane = frameVm.nAch;
	stage = STAGE_RUNNING;
	listStart();
	ACH_ANCHOR->status = DSIRPC_MENU_READY;
	// The frame lane's samples need the game's writes in main RAM
	if (frameMem) ProbeWatch_Clean();
}

void ProbeAch_SetTime(u32 secondsSince2000) {
	clockStart = secondsSince2000;
	clockKnown = secondsSince2000 != 0;
}

void ProbeAch_MenuOpened(void) {
	volatile DsirpcMenuAnchor *a = ACH_ANCHOR;
	a->newFrom = menuSeen; // new to the menu: the unlocks since it last opened
	menuSeen = unlockSeq;
	a->open = 1;
	menuOpen = 1;
}

void ProbeAch_MenuClosed(void) {
	if (!menuOpen) return;
	ACH_ANCHOR->open = 0;
	menuOpen = 0;
}

void ProbeAch_Sample(void) {
	if (stage != STAGE_RUNNING || !frameMem) return;
	u16 start = ACH_REG_VCOUNT & 0x1FF;
	u8 head = ringHead, next = (head + 1) & (ACH_FRAME_SLOTS - 1);
	if (next == ringTail) { // the checking is that far behind: a gap
		stats.dropped++;
		return;
	}
	// The ARM9 writes its data cache back to main RAM at the start of its
	// VBlank (probe_watch.c); wait a moment for that, unless it didn't come
	// last time either (then only once a second, to notice it's back).
	u32 seen = ProbeWatch_Cleaned();
	if (seen == cleanSeen && (cleanOk || !(stats.unclean & 63))) {
		while ((seen = ProbeWatch_Cleaned()) == cleanSeen && linesSince(start) < ACH_CLEAN_WAIT) {}
	}
	cleanOk = seen != cleanSeen;
	cleanSeen = seen;
	// None: ring the ARM9 again now and then (its hook isn't in yet, or the
	// game replaced its VBlank handler)
	if (!cleanOk && (++stats.unclean & 31) == 2) ProbeWatch_Clean();
	AchVm_Sample(&sampleVm, ring + head * frameMem);
	ringHead = next;
	u16 lines = linesSince(start); // (the report's l=: what the checker costs the VBlank)
	if (lines > stats.maxLines) stats.maxLines = lines;
}

int ProbeAch_Push(u32 id, u32 when) {
	u8 head = pushHead, next = (head + 1) & (ACH_PUSHED - 1);
	if (stage == STAGE_OFF || next == pushTail) return 0;
	pushId[head] = id;
	pushWhen[head] = when;
	pushHead = next;
	return 1;
}

// DSiRPC's unlocks: no longer checked, and earned in the menu's list (new
// to it, unless it's marked earned already)
static void takePushes(void) {
	while (pushTail != pushHead) {
		u8 tail = pushTail;
		u32 id = pushId[tail];
		AchVm_SetUnlocked(&vm, id);
		AchVm_SetUnlocked(&frameVm, id);
		DsirpcListEntry *e = listFind(id);
		if (e && !(e->flags & (DSIRPC_LIST_EARNED | DSIRPC_LIST_ON_CONSOLE))) {
			listMark(id, pushWhen[tail], ++unlockSeq, DSIRPC_LIST_EARNED);
			ACH_ANCHOR->unlocks = unlockSeq;
		}
		__asm__ volatile ("" ::: "memory"); // (done with the slot before the VBlank may reuse it)
		pushTail = (tail + 1) & (ACH_PUSHED - 1);
	}
}

// A turn of checking: DSiRPC's unlocks, then the frame lane's samples in
// order, then the pass lane, while more(ud) says so. The pass lane also
// stops for a new sample (the idle side can get one in the middle).
static int (*turnMore)(void *ud);
static int passMore(void *ud) {
	return ringTail == ringHead && turnMore(ud);
}

static void checkTurn(int (*more)(void *ud), void *ud) {
	turnMore = more;
	takePushes();
	do {
		u8 tail = ringTail;
		if (tail != ringHead) {
			AchVm_RunSampled(&frameVm, ring + tail * frameMem, onTriggered, 0);
			ringTail = (tail + 1) & (ACH_FRAME_SLOTS - 1);
			stats.frames++;
		} else if (!vm.nAch) {
			return;
		} else if (AchVm_Run(&vm, passMore, onTriggered, ud)) {
			stats.passes++;
		}
	} while (more(ud));
}

void ProbeAch_Tick(u16 tickStart, int idleAlive) {
	ProbeAch_MenuClosed(); // the VBlank ticks only run while the menu is closed
	clockTried = 0;
	idleLines = 0;
	clockPart += 1000;
	if (clockPart >= ACH_VBLANKS_X1000) {
		clockPart -= ACH_VBLANKS_X1000;
		clockSeconds++;
	}
	if (stage == STAGE_OFF) return;
	stats.idle = (u8)idleAlive;
	// The idle side checks; this is only for a game whose swiHalt
	// nds-bootstrap couldn't hook (and never in the middle of an idle turn).
	if (stage == STAGE_RUNNING && (idleAlive || busy)) return;
	// Whatever else this tick did comes first; skip a turn if it took long.
	if (linesSince(tickStart) > RPCPROBE_ACH_SKIP_AFTER_LINES) return;

	u16 start = ACH_REG_VCOUNT & 0x1FF;
	if (stage == STAGE_CHECKING) checkStamp(start);
	else checkTurn(keepGoing, &start);
	u16 lines = linesSince(start);
	if (lines > stats.maxLines) stats.maxLines = lines;
}

// The idle side's budget: RPCPROBE_ACH_IDLE_LINES_PER_VISIT scanlines a
// visit, RPCPROBE_ACH_IDLE_LINES_PER_FRAME a frame, and never while an ARM9
// ROM read waits
typedef struct {
	u16 start;
	int (*romWaiting)(void);
} IdleTurn;

static int idleMore(void *ud) {
	const IdleTurn *t = (const IdleTurn *)ud;
	u16 used = linesSince(t->start);
	return used < RPCPROBE_ACH_IDLE_LINES_PER_VISIT && idleLines + used < RPCPROBE_ACH_IDLE_LINES_PER_FRAME &&
	       !t->romWaiting();
}

int ProbeAch_Idle(int (*romWaiting)(void)) {
	if (stage != STAGE_RUNNING || busy) return 0;
	IdleTurn t = { ACH_REG_VCOUNT & 0x1FF, romWaiting };
	if (!idleMore(&t)) return romWaiting();
	busy = 1;
	checkTurn(idleMore, &t);
	busy = 0;
	idleLines += linesSince(t.start);
	return romWaiting();
}

void ProbeAch_TakeStats(ProbeAchStats *out) {
	*out = stats;
	u8 idle = stats.idle;
	ProbeAchStats zero = { 0 };
	stats = zero;
	stats.idle = idle;
}

int ProbeAch_SavePending(void) {
	return pendHead != pendTail;
}

void ProbeAch_SaveOne(void) {
	u8 tail = pendTail;
	if (tail == pendHead) return;
	if (!unlockNext || unlockNext >= ACH_UNLOCK_SLOTS) {
		probeAchSaveFailed++; // RPCUNLK.BIN is full until the launcher hands it to DSiRPC
	} else {
		// id, game code (from the set's header), when, sequence number, check
		u32 slot[4];
		slot[0] = pendId[tail];
		slot[1] = rd32((const u8 *)DSIRPC_ACH_LOCATION + 8);
		slot[2] = pendWhen[tail];
		slot[3] = unlockNext;
		slot[3] |= (u32)slotCheck((const u8 *)slot) << 16;
		if (fileWrite((const char *)slot, &unlockFile, unlockNext * ACH_UNLOCK_SLOT,
		              ACH_UNLOCK_SLOT) == ACH_UNLOCK_SLOT) {
			probeAchSaved++;
		} else {
			probeAchSaveFailed++;
		}
		unlockNext++;
	}
	pendTail = (tail + 1) & (ACH_PENDING - 1);
}

int ProbeAch_RecentIds(u32 *ids, int max) {
	int n = (recentCount < max) ? recentCount : max;
	int first = (recentNext + ACH_RECENT - n) % ACH_RECENT;
	for (int i = 0; i < n; i++) ids[i] = recent[(first + i) % ACH_RECENT];
	return n;
}
