// Force-included into every file of the watch test (-include): what the
// -D overrides of probe_watch.c's hardware macros refer to (watch_test.c
// defines them).
#include <stdint.h>
#include <nds/ndstypes.h>
#include "dsirpc_watch_block.h"
extern DsirpcWatchBlock dsirpcWatchBlock;
extern u16 fakeIpc;
extern u32 fakeScanStart;
u16 *vcountReg(void);
extern u8 fakeRing[];
