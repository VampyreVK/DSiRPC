// Host stand-in for libnds' nds/bios.h (see ../../../igm_host.c): swiDelay()
// is where the host's clock moves on.
#pragma once
#include <nds/ndstypes.h>
void swiDelay(u32 duration);
void swiWaitForVBlank(void);
