// Host stand-in for libnds' nds/arm9/background.h: the sub engine's
// background registers and memory, at their real addresses (igm_host.c).
#pragma once
#include <nds/ndstypes.h>
#define REG_BG0CNT      (*(vu16 *)0x04000008)
#define REG_BG1CNT      (*(vu16 *)0x0400000A)
#define REG_BG2CNT      (*(vu16 *)0x0400000C)
#define REG_BG3CNT      (*(vu16 *)0x0400000E)
#define REG_BG0CNT_SUB  (*(vu16 *)0x04001008)
#define REG_BG1CNT_SUB  (*(vu16 *)0x0400100A)
#define REG_BG2CNT_SUB  (*(vu16 *)0x0400100C)
#define REG_BG3CNT_SUB  (*(vu16 *)0x0400100E)
#define REG_BG0HOFS_SUB (*(vu16 *)0x04001010)
#define REG_BG0VOFS_SUB (*(vu16 *)0x04001012)
#define REG_BG1HOFS_SUB (*(vu16 *)0x04001014)
#define REG_BG1VOFS_SUB (*(vu16 *)0x04001016)
#define REG_BG2HOFS_SUB (*(vu16 *)0x04001018)
#define REG_BG2VOFS_SUB (*(vu16 *)0x0400101A)
#define REG_BG3HOFS_SUB (*(vu16 *)0x0400101C)
#define REG_BG3VOFS_SUB (*(vu16 *)0x0400101E)
#define REG_BG3HOFS     (*(vu16 *)0x0400001C)
#define REG_BG3VOFS     (*(vu16 *)0x0400001E)
#define BG_MAP_BASE(n)  ((n) << 8)
#define BG_TILE_BASE(n) ((n) << 2)
#define BG_PRIORITY(n)  (n)
#define BG_COLOR_256    0x80
#define BG_COLOR_16     0x00
#define BgSize_T_256x256 0
#define BG_GFX          ((u16 *)0x06000000)
#define BG_GFX_SUB      ((u16 *)0x06200000)
#define BG_MAP_RAM(n)     ((u16 *)(0x06000000 + (n) * 0x800))
#define BG_MAP_RAM_SUB(n) ((u16 *)(0x06200000 + (n) * 0x800))
#define BG_TILE_RAM(n)     ((u16 *)(0x06000000 + (n) * 0x4000))
#define BG_TILE_RAM_SUB(n) ((u16 *)(0x06200000 + (n) * 0x4000))
#define REG_MOSAIC_SUB   (*(vu16 *)0x0400104C)
#define REG_BLDCNT_SUB   (*(vu16 *)0x04001050)
#define REG_BLDALPHA_SUB (*(vu16 *)0x04001052)
#define REG_BLDY_SUB     (*(vu16 *)0x04001054)
