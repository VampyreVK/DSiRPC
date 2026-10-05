// dsirpc_watch.c - DSiRPC's per-frame capture, the ARM9 half. See
// common/include/dsirpc_watch_block.h for why it exists and how a round
// works; the ARM7 half is cardenginei/arm7/source/rpcprobe/probe_watch.c.
//
// Only the plain cardenginei_arm9 (retail games in DS mode, the variant
// that loads next to rpcprobe's cardenginei_arm7) carries it. The DLDI,
// GSDD and TWLSDK variants compile this file to nothing, and the ARM7 then
// never finds the block and reads by itself.

#include <nds/ndstypes.h>

#if !defined(TWLSDK) && !defined(DLDI) && !defined(GSDD)

#include <nds/arm9/cache.h>
#include "dsirpc_watch_block.h"

#define MAINRAM_LO 0x02000000u
#define MAINRAM_HI 0x02400000u

// Four whole cache lines of their own, so cleaning or invalidating them
// never touches anything else.
DsirpcWatchBlock dsirpcWatchBlock __attribute__((aligned(32))) = {
	.magic0 = DSIRPC_WATCH_MAGIC0,
	.magic1 = DSIRPC_WATCH_MAGIC1,
	.version = DSIRPC_WATCH_VERSION,
};

// Called from myIrqHandlerIPC on every IPC sync interrupt. Cheap when there
// is nothing to do: two cache-line invalidates and a compare.
void dsirpcWatchService(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;

	// The ARM7 writes the first two lines straight to RAM; drop any copy the
	// cache still holds. Never dirty here, since this side never writes them.
	DC_InvalidateRange(b, 0x40);
	u32 req = b->req;
	if (req == 0 || req == b->ack) return;

	u32 n = b->count;
	if (n > DSIRPC_WATCH_MAX) n = DSIRPC_WATCH_MAX;
	u8 *v = b->values;
	u8 *end = b->values + sizeof(b->values);
	for (u32 i = 0; i < n; i++) {
		u32 a = b->addrs[i];
		u32 s = b->sizes[i];
		if ((s != 1 && s != 2 && s != 4) || v + s > end) break;
		if (a < MAINRAM_LO || a >= MAINRAM_HI || s > MAINRAM_HI - a) {
			for (u32 k = 0; k < s; k++) v[k] = 0;
		} else if (s == 4 && !(a & 3)) {
			u32 x = *(vu32 *)a;
			v[0] = x; v[1] = x >> 8; v[2] = x >> 16; v[3] = x >> 24;
		} else if (s == 2 && !(a & 1)) {
			u16 x = *(vu16 *)a;
			v[0] = x; v[1] = x >> 8;
		} else {
			for (u32 k = 0; k < s; k++) v[k] = *(vu8 *)(a + k);
		}
		v += s;
	}

	// Values out to RAM first, then the ack, so an ARM7 that sees the new
	// ack also sees the values that go with it.
	DC_FlushRange(b->values, sizeof(b->values));
	b->vcount = *(vu16 *)0x04000006; // REG_VCOUNT
	b->ack = req;
	DC_FlushRange(&b->ack, 0x20);
}

#endif
