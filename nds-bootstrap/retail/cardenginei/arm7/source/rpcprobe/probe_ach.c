// probe_ach.c - see probe_ach.h.
//
// Memory: the set and the checker's state live in DSIRPC_ACH_LOCATION (main
// RAM that the bootloader keeps the ROM cache out of; locations.h). The set
// file is copied there whole: its 64-byte header, then the program. The
// state (memory values, hit counts) follows it.
//
// Time: everything happens in the VBlank interrupt, so the checker gets a
// budget of RPCPROBE_ACH_LINES_PER_VBLANK scanlines a tick and carries on
// next tick where it stopped. One pass over every achievement may take a few
// frames with a big set; each pass reads the game's memory once, at its
// start, so rcheevos' "frame" is a pass here. Before the first pass the set's
// CRC-32 is checked, a slice a tick.
//
// The SD card is only touched on the first VBlank (see probe_hook.c's SD
// card rule).

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

enum { STAGE_OFF, STAGE_CHECKING, STAGE_RUNNING };

s16 probeAchLoaded = PROBE_ACH_NONE;
u16 probeAchTriggered = 0;

static u8 stage = STAGE_OFF;
static AchVm vm;
static u32 bodySize, crcPos, crc, crcWanted;
static u16 passes, maxLines;
static u32 recent[ACH_RECENT];
static u8 recentCount, recentNext;

static u16 linesSince(u16 start) {
	u16 now = ACH_REG_VCOUNT & 0x1FF;
	return (now >= start) ? now - start : now + ACH_LINES_PER_FRAME - start;
}

static u32 rd32(const u8 *p) {
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24);
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
	if (bodySize > DSIRPC_ACH_SIZE || stateSize > DSIRPC_ACH_SIZE ||
	    stateOffset + stateSize > DSIRPC_ACH_SIZE) {
		loadFailed(PROBE_ACH_E_SIZE);
		return;
	}

	fileRead((char *)base + ACH_HEADER_SIZE, &file, ACH_HEADER_SIZE, bodySize);
	if (AchVm_Load(&vm, base + ACH_HEADER_SIZE, bodySize, base + stateOffset, stateSize,
	               ACH_RAM, ACH_RAM_SIZE) != ACHVM_OK) {
		loadFailed(PROBE_ACH_E_PROGRAM);
		return;
	}

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

void ProbeAch_Tick(u16 tickStart) {
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

int ProbeAch_RecentIds(u32 *ids, int max) {
	int n = (recentCount < max) ? recentCount : max;
	int first = (recentNext + ACH_RECENT - n) % ACH_RECENT;
	for (int i = 0; i < n; i++) ids[i] = recent[(first + i) % ACH_RECENT];
	return n;
}
