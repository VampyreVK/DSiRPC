// probe_ach.c - see probe_ach.h.
//
// Memory: the set and the checker's state live in DSIRPC_ACH_LOCATION (main
// RAM that the bootloader keeps the ROM cache out of; locations.h). The set
// file is copied there whole: its 64-byte header, then the program. The
// state (memory values, hit counts) follows it. The last 4 KB are kept free
// (DSiRPC builds sets to fit ACH_SET_SPACE) to read RPCUNLK.BIN into when
// the game starts.
//
// Time: everything happens in the VBlank interrupt, so the checker gets a
// budget of RPCPROBE_ACH_LINES_PER_VBLANK scanlines a tick and carries on
// next tick where it stopped. One pass over every achievement may take a few
// frames with a big set; each pass reads the game's memory once, at its
// start, so rcheevos' "frame" is a pass here. Before the first pass the set's
// CRC-32 is checked, a slice a tick.
//
// Unlocks: each one waits in a small queue until ProbeAch_SaveOne() writes
// it to its own RPCUNLK.BIN slot, outside interrupts with nds-bootstrap's SD
// card lock held (probe_hook.c's SD card rule). The slot's time is the
// launcher's clock (RPCHAND.TXT's time=) plus the VBlanks since, so time
// spent asleep (lid closed) isn't counted. Achievements already in
// RPCUNLK.BIN when the game starts aren't checked again.

#include <nds/ndstypes.h>
#include "rpcprobe_build.h"
#include "locations.h"
#include "my_fat.h"
#include "probe_ach.h"
#include "probe_ach_vm.h"

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
#define ACH_SET_SPACE       (DSIRPC_ACH_SIZE - ACH_UNLOCK_FILE) // DSiRPC's offline.ACH_MEMORY
#define ACH_PENDING         8          // unlocks waiting to be saved (a power of 2)
#define ACH_VBLANKS_X1000   59826      // VBlanks in 1000 s (59.8261 Hz)

enum { STAGE_OFF, STAGE_CHECKING, STAGE_RUNNING };

s16 probeAchLoaded = PROBE_ACH_NONE;
u16 probeAchTriggered = 0;
u16 probeAchSaved = 0;
u16 probeAchLost = 0;
u16 probeAchSaveFailed = 0;
u16 probeAchWaiting = 0;

static u8 stage = STAGE_OFF;
static AchVm vm;
static u32 bodySize, crcPos, crc, crcWanted;
static u16 passes, maxLines;
static u32 recent[ACH_RECENT];
static u8 recentCount, recentNext;

// Saving: the VBlank side adds at pendHead, the saving side takes from
// pendTail, each only moving its own index.
static aFile unlockFile;
static u16 unlockNext;                 // the next free slot (0: no RPCUNLK.BIN to save to)
static u32 pendId[ACH_PENDING], pendWhen[ACH_PENDING];
static volatile u8 pendHead, pendTail;
static u32 clockStart, clockSeconds;   // the launcher's time; seconds of VBlanks since
static u32 clockPart;                  // the part second, in 1/1000 VBlanks

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

static void loadFailed(s16 why) {
	probeAchLoaded = why;
	stage = STAGE_OFF;
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
		u32 id = rd32(s);
		if (id | rd32(s + 4) | rd32(s + 8) | rd32(s + 12)) next = i + 1;
		if (id && rd32(s + 4) == game && slotCheck(s) == (s[14] | (s[15] << 8)) &&
		    AchVm_SetUnlocked(&vm, id)) {
			probeAchWaiting++;
		}
	}
	unlockNext = next;
}

void ProbeAch_Load(const void *ndsHeader) {
	aFile file;
	getBootFileCluster(&file, "RPCSET.BIN", 0);
	if (file.firstCluster == CLUSTER_FREE) return; // no set: nothing to do

	u8 *base = (u8 *)DSIRPC_ACH_LOCATION;
	fileRead((char *)base, &file, 0, ACH_HEADER_SIZE);

	// "DRSE", version 2, header size 64, game code, RA game id, stamp,
	// achievements, flags, program size, state size
	if (base[0] != 'D' || base[1] != 'R' || base[2] != 'S' || base[3] != 'E' ||
	    (base[4] | (base[5] << 8)) != 2 || (base[6] | (base[7] << 8)) != ACH_HEADER_SIZE) {
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
	bodySize = rd32(base + 24);
	u32 stateSize = rd32(base + 28);
	u32 stateOffset = (ACH_HEADER_SIZE + bodySize + 3) & ~3u;
	if (bodySize > ACH_SET_SPACE || stateSize > ACH_SET_SPACE ||
	    stateOffset + stateSize > ACH_SET_SPACE) {
		loadFailed(PROBE_ACH_E_SIZE);
		return;
	}

	fileRead((char *)base + ACH_HEADER_SIZE, &file, ACH_HEADER_SIZE, bodySize);
	if (AchVm_Load(&vm, base + ACH_HEADER_SIZE, bodySize, base + stateOffset, stateSize,
	               ACH_RAM, ACH_RAM_SIZE) != ACHVM_OK) {
		loadFailed(PROBE_ACH_E_PROGRAM);
		return;
	}
	loadUnlocks(rd32(base + 8));

	crcWanted = rd32(base + 16);
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

	// Queued for ProbeAch_SaveOne(), with when it happened
	u8 head = pendHead, next = (head + 1) & (ACH_PENDING - 1);
	if (!unlockNext || next == pendTail) { // nowhere to save it, or nothing has saved for a while
		probeAchLost++;
		return;
	}
	pendId[head] = id;
	pendWhen[head] = clockStart ? clockStart + clockSeconds : 0;
	pendHead = next;
}

static int keepGoing(void *ud) {
	return linesSince(*(const u16 *)ud) < RPCPROBE_ACH_LINES_PER_VBLANK;
}

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
	probeAchLoaded = (s16)vm.nAch;
	stage = STAGE_RUNNING;
}

void ProbeAch_SetTime(u32 secondsSince2000) {
	clockStart = secondsSince2000;
}

void ProbeAch_Tick(u16 tickStart) {
	clockPart += 1000;
	if (clockPart >= ACH_VBLANKS_X1000) {
		clockPart -= ACH_VBLANKS_X1000;
		clockSeconds++;
	}
	if (stage == STAGE_OFF) return;
	// Whatever else this tick did comes first; skip a turn if it took long.
	if (linesSince(tickStart) > RPCPROBE_ACH_SKIP_AFTER_LINES) return;

	u16 start = ACH_REG_VCOUNT & 0x1FF;
	if (stage == STAGE_CHECKING) {
		checkStamp(start);
	} else if (AchVm_Run(&vm, keepGoing, onTriggered, &start)) {
		passes++;
	}
	u16 lines = linesSince(start);
	if (lines > maxLines) maxLines = lines;
}

void ProbeAch_TakeStats(u16 *passesOut, u16 *maxLinesOut) {
	*passesOut = passes;
	*maxLinesOut = maxLines;
	passes = 0;
	maxLines = 0;
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
