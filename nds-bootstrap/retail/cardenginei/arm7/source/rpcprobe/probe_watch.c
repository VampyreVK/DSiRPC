// probe_watch.c - see probe_watch.h.

#include <nds/ndstypes.h>
#include "rpcprobe_build.h"

#if RPCPROBE_REQUESTS

#include "probe_watch.h"
#include "dsirpc_watch_block.h"
#include "locations.h"

// Same limits as 'R' (probe_req.c): main RAM only, since the ARM7 has no
// MMU and a bad read can hang the console.
#define MAINRAM_LO 0x02000000u
#define MAINRAM_HI 0x02400000u

#define REC_HEADER 4 // tick u16 + vcount u16

// Where the ARM9 half's block can be: inside the plain ARM9 cardengine,
// which is linked at CARDENGINEI_ARM9_LOCATION and is 12 KB long.
#ifndef PW_ARM9_SCAN_START
#define PW_ARM9_SCAN_START CARDENGINEI_ARM9_LOCATION
#endif
#define PW_ARM9_SCAN_END   (PW_ARM9_SCAN_START + 0x3000)

#ifndef PW_REG_IPC_SYNC
#define PW_REG_IPC_SYNC (*(vu16 *)0x04000180)
#endif
#define PW_IPC_SYNC_IRQ_REQUEST (1 << 13)
#define PW_DOORBELL 3 // nds-bootstrap's own DMA doorbell; the ARM9 does nothing else for it

u8 probeWatchArm9 = 0; // 1 once the ARM9 half was found (reported in the hellos)

static volatile DsirpcWatchBlock *arm9Block = 0;
static u8 useArm9 = 0;      // this watch list may use the ARM9 (the PC can say no)
static u32 reqCounter = 0;  // last request number sent, never 0 once used
static u32 pendingReq = 0;  // the request the ARM9 is answering, 0 = none

typedef struct {
	u32 addr;
	u8 size;
} Watch;

static Watch watches[WATCH_MAX];
static u8 watchCount = 0;
static u8 recSize = 0;    // REC_HEADER + the watches' sizes
static u16 ringSlots = 0; // WATCH_RING_BYTES / recSize
static u32 written = 0;   // records written since the last 'W'
static u16 tick = 0;      // VBlanks sampled since the last 'W'
static u8 ring[WATCH_RING_BYTES] __attribute__((aligned(4)));

static u16 get16(const u8 *p) { return (u16)((p[0] << 8) | p[1]); }
static u32 get32(const u8 *p) { return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3]; }
static void put16(u8 *p, u16 v) { p[0] = v >> 8; p[1] = v & 0xFF; }

void ProbeWatch_Init(void) {
	arm9Block = 0;
	for (u32 a = PW_ARM9_SCAN_START; a + sizeof(DsirpcWatchBlock) <= PW_ARM9_SCAN_END; a += 32) {
		volatile DsirpcWatchBlock *b = (volatile DsirpcWatchBlock *)a;
		if (b->magic0 == DSIRPC_WATCH_MAGIC0 && b->magic1 == DSIRPC_WATCH_MAGIC1
		 && b->version == DSIRPC_WATCH_VERSION) {
			arm9Block = b;
			break;
		}
	}
	probeWatchArm9 = arm9Block ? 1 : 0;
}

// Ring the ARM9, but only over our own doorbell value or none: any other
// value is a command of nds-bootstrap's (screen swap, colour LUT, reset,
// in-game menu) that the ARM9 may not have read yet, and it must not be
// replaced. Its interrupt serves our request as well.
static void ringArm9(void) {
	u16 sync = PW_REG_IPC_SYNC;
	u8 out = (sync >> 8) & 0xF;
	if (out == 0 || out == PW_DOORBELL) {
		PW_REG_IPC_SYNC = (sync & 0xF0FF) | (PW_DOORBELL << 8) | PW_IPC_SYNC_IRQ_REQUEST;
	}
}

void ProbeWatch_Sample(u16 vcount) {
	if (!watchCount) return;
	u8 *rec = &ring[(written % ringSlots) * recSize];
	put16(&rec[0], tick);
	u8 *v = &rec[REC_HEADER];
	volatile DsirpcWatchBlock *b = arm9Block;
	if (b && pendingReq && b->ack == pendingReq) {
		// The ARM9 answered last VBlank's request: the values as the game
		// had them then, read through its cache. Its scanline, flag clear.
		for (int k = 0; k < recSize - REC_HEADER; k++) v[k] = b->values[k];
		put16(&rec[2], b->vcount & WATCH_REC_VCOUNT);
	} else {
		for (int i = 0; i < watchCount; i++) {
			u32 a = watches[i].addr;
			u8 n = watches[i].size;
			// One load per value when it's aligned, so a value the game is
			// writing at that moment can't be read half old, half new.
			if (n == 4 && !(a & 3)) {
				u32 x = *(vu32 *)a;
				v[0] = x; v[1] = x >> 8; v[2] = x >> 16; v[3] = x >> 24;
			} else if (n == 2 && !(a & 1)) {
				u16 x = *(vu16 *)a;
				v[0] = x; v[1] = x >> 8;
			} else {
				for (u8 k = 0; k < n; k++) v[k] = *(vu8 *)(a + k);
			}
			v += n;
		}
		// Read here, straight from main RAM: may be behind the ARM9's cache.
		put16(&rec[2], (vcount & WATCH_REC_VCOUNT) | WATCH_REC_ARM7);
	}
	written++;
	tick++;

	// Ask for the next frame's values.
	if (b && useArm9) {
		if (++reqCounter == 0) reqCounter = 1;
		pendingReq = reqCounter;
		b->req = pendingReq;
		ringArm9();
	} else {
		pendingReq = 0;
	}
}

u16 ProbeWatch_Set(const u8 *req, int len, u8 *count, u8 *status) {
	u8 raw = (len >= 4) ? req[3] : 0;
	u8 n = raw & ~WATCH_ARM7_ONLY;
	*count = raw;
	if (len < 4 || n > WATCH_MAX || len < 4 + 5 * n) {
		*status = 1;
		return 0;
	}
	u8 size = REC_HEADER;
	for (int i = 0; i < n; i++) {
		const u8 *w = &req[4 + 5 * i];
		u32 a = get32(w);
		u8 s = w[4];
		if (s != 1 && s != 2 && s != 4) { *status = 1; return 0; }
		if (a < MAINRAM_LO || a >= MAINRAM_HI || s > MAINRAM_HI - a) { *status = 2; return 0; }
		size += s;
	}
	// Valid: replace the list and start the ring over. Whatever the ARM9 is
	// answering was for the old list, so it's ignored from here on.
	watchCount = 0;
	pendingReq = 0;
	volatile DsirpcWatchBlock *b = arm9Block;
	for (int i = 0; i < n; i++) {
		const u8 *w = &req[4 + 5 * i];
		watches[i].addr = get32(w);
		watches[i].size = w[4];
		if (b) {
			b->addrs[i] = watches[i].addr;
			b->sizes[i] = watches[i].size;
		}
	}
	if (b) b->count = n;
	useArm9 = !(raw & WATCH_ARM7_ONLY);
	recSize = size;
	ringSlots = WATCH_RING_BYTES / size;
	written = 0;
	tick = 0;
	watchCount = n;
	*status = 0;
	return 0;
}

u16 ProbeWatch_Fetch(const u8 *req, int len, u8 *out, u16 maxOut, u8 *count, u8 *status) {
	*count = 0;
	if (len < 6) { *status = 1; return 0; }
	if (!watchCount) { *status = 3; return 0; }

	// Everything is counted in records; `from` is the low 16 bits of a
	// record number, so it's compared as a distance back from the newest.
	u32 have = written < ringSlots ? written : ringSlots; // records still in the ring
	u16 back = (u16)((u16)written - get16(&req[4]));      // records from `from` to the newest
	u32 lost = 0;
	if (back > have) {
		lost = back - have;
		back = (u16)have;
	}
	u32 first = written - back;

	u16 room = (u16)((maxOut - 5) / recSize);
	u16 k = back < room ? back : room;
	if (k > 255) k = 255;

	put16(&out[0], (u16)first);
	put16(&out[2], lost > 0xFFFF ? 0xFFFF : (u16)lost);
	out[4] = recSize;
	u8 *p = &out[5];
	for (u16 i = 0; i < k; i++) {
		const u8 *rec = &ring[((first + i) % ringSlots) * recSize];
		for (u8 b = 0; b < recSize; b++) p[b] = rec[b];
		p += recSize;
	}
	*count = (u8)k;
	*status = 0;
	return (u16)(5 + k * recSize);
}

#endif // RPCPROBE_REQUESTS
