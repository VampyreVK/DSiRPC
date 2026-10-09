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

// With no ARM9 snapshot to record for this many VBlanks in a row, ring the
// ARM9 to put its hook (back) in, and again once a second while it lasts.
#define PW_STALL_RING 2
#define PW_RING_EVERY 60

// Reported in the hellos as a9=: 0 = no ARM9 half, 1 = found, 2 or more =
// found and its VBlank hook in (1 + the number of hooks it has put in).
u8 probeWatchArm9 = 0;

static volatile DsirpcWatchBlock *arm9Block = 0;
static u8 useArm9 = 0;    // this watch list may use the ARM9 (the PC can say no)
static u32 gen = 0;       // number of the current list in the block, never 0 once used
static u32 want = 0;      // number of the next ARM9 snapshot to record, 0 = not in step yet
static u16 stall = 0;     // VBlanks in a row with no ARM9 snapshot to record

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
// The records, in main RAM (the ARM7 cardengine's own is full)
#ifndef PW_RING // (the PC tests have their own)
#define PW_RING ((u8 *)DSIRPC_WATCH_RING_LOCATION)
#endif
#define ring PW_RING
_Static_assert(WATCH_RING_BYTES == DSIRPC_WATCH_RING_SIZE, "the ring's size");

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
	probeWatchArm9 = arm9Block ? (u8)(1 + arm9Block->hooks) : 0;
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

void ProbeWatch_Clean(void) {
	volatile DsirpcWatchBlock *b = arm9Block;
	if (!b) return;
	b->clean = 1;
	ringArm9();
}

u32 ProbeWatch_Cleaned(void) {
	volatile DsirpcWatchBlock *b = arm9Block;
	return b ? b->cleaned : 0;
}

// Copies the next ARM9 snapshot's values (n bytes) to `v` and its scanline
// to *vc. Returns 1 if there was one to record.
static int takeArm9(volatile DsirpcWatchBlock *b, u8 *v, int n, u16 *vc) {
	u32 latest = b->latest;
	if (!latest) return 0; // the hook hasn't run yet
	s32 ahead = (s32)(latest - want);
	int fresh = 0;
	if (!want || ahead >= 2 || ahead < -1) {
		// Not in step (just started, or VBlanks went by without us): start
		// one behind the newest. The ARM9's VBlank and ours start at almost
		// the same moment, so the newest may or may not be this VBlank's
		// yet, but the one before it is always there.
		want = latest > 1 ? latest - 1 : 1;
		fresh = 1;
	}
	while ((s32)(latest - want) >= 0) {
		volatile DsirpcWatchSlot *s = &b->slots[want % DSIRPC_WATCH_SLOTS];
		if (s->seq != want) { want = 0; return 0; }        // already overwritten
		if (s->gen != gen) { want++; fresh = 1; continue; }    // taken with an older list
		// Coming into step, never start on the newest (for the reason
		// above): wait a VBlank, and it's the one before the newest.
		if (fresh && want == latest) return 0;
		for (int k = 0; k < n; k++) v[k] = s->values[k];
		*vc = s->vcount;
		if (s->seq != want) { want = 0; return 0; } // overwritten while copying
		want++;
		return 1;
	}
	// None newer yet: the ARM9's VBlank interrupt is late this time, or there
	// are no snapshots for now (the hook is out, or the game has interrupts
	// off). When they come back, recording carries on from the next one,
	// which may then be the newest each time (this VBlank's rather than the
	// one before); the first time the ARM9 is late again, the ARM7 fills in
	// once and is one behind from then on. Waiting for one behind right
	// away instead (one more fill-in every time) can skip a snapshot when the
	// ARM9 is late just then; one fill-in now and then is the better trade.
	return 0;
}

void ProbeWatch_Sample(u16 vcount) {
	if (!watchCount) return;
	u8 *rec = &ring[(written % ringSlots) * recSize];
	put16(&rec[0], tick);
	u8 *v = &rec[REC_HEADER];
	volatile DsirpcWatchBlock *b = arm9Block;
	u16 vc9;
	if (b && useArm9 && takeArm9(b, v, recSize - REC_HEADER, &vc9)) {
		// The ARM9's snapshot from the start of a VBlank (normally the one
		// before this), read through its cache before the game's own VBlank
		// code ran. Its scanline, flag clear.
		put16(&rec[2], vc9 & WATCH_REC_VCOUNT);
		stall = 0;
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
		// No snapshot: the hook isn't in yet, or the game replaced its
		// VBlank handler (or had interrupts off for a while). Ask the ARM9
		// to put it (back) in.
		if (b && useArm9 && ++stall % PW_RING_EVERY == PW_STALL_RING) ringArm9();
	}
	if (b) probeWatchArm9 = (u8)(1 + b->hooks);
	written++;
	tick++;
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
	// Valid: replace the list and start the ring over. The ARM9 stops
	// first (count 0), and the new list gets a new number, so snapshots of
	// the old one are never recorded.
	watchCount = 0;
	want = 0;
	stall = 0;
	volatile DsirpcWatchBlock *b = arm9Block;
	if (b) b->count = 0;
	for (int i = 0; i < n; i++) {
		const u8 *w = &req[4 + 5 * i];
		watches[i].addr = get32(w);
		watches[i].size = w[4];
		if (b) {
			b->addrs[i] = watches[i].addr;
			b->sizes[i] = watches[i].size;
		}
	}
	useArm9 = !(raw & WATCH_ARM7_ONLY);
	if (b) {
		if (++gen == 0) gen = 1;
		b->gen = gen;
		b->count = useArm9 ? n : 0; // ARM7-only: the ARM9 takes no snapshots at all
	}
	recSize = size;
	ringSlots = WATCH_RING_BYTES / size;
	written = 0;
	tick = 0;
	watchCount = n;
	// Have the ARM9 put its VBlank hook in now, rather than after the
	// first VBlanks without snapshots.
	if (b && useArm9 && n) ringArm9();
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
