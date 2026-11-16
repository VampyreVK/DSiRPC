// Host stand-in for libnds' nds/system.h. The registers are at their real
// addresses: the host maps the DS's memory and I/O there (igm_host.c).
#pragma once
#include <nds/ndstypes.h>
#define REG_VCOUNT      (*(vu16 *)0x04000006)
#define REG_POWERCNT    (*(vu16 *)0x04000304)
#define POWER_SWAP_LCDS BIT(15)
#define REG_SCFG_CLK    (*(vu16 *)0x04004004)
#define REG_SCFG_EXT    (*(vu32 *)0x04004008)
#define REG_SCFG_ROM    (*(vu16 *)0x04004000)
