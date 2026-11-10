// Host stand-in for libnds' nds/arm9/video.h: display control, VRAM banks
// and palettes, at their real addresses (igm_host.c).
#pragma once
#include <nds/ndstypes.h>
#define RGB15(r, g, b)  ((r) | ((g) << 5) | ((b) << 10))
#define RGB5(r, g, b)   RGB15(r, g, b)
#define ARGB16(a, r, g, b) (((a) << 15) | RGB15(r, g, b))
#define REG_DISPCNT     (*(vu32 *)0x04000000)
#define REG_DISPCNT_SUB (*(vu32 *)0x04001000)
#define MODE_0_2D       0x10000
#define MODE_5_2D       0x10005
#define DISPLAY_BG0_ACTIVE BIT(8)
#define DISPLAY_BG1_ACTIVE BIT(9)
#define DISPLAY_BG2_ACTIVE BIT(10)
#define DISPLAY_BG3_ACTIVE BIT(11)
#define VRAM_A_CR       (*(vu8 *)0x04000240)
#define VRAM_B_CR       (*(vu8 *)0x04000241)
#define VRAM_C_CR       (*(vu8 *)0x04000242)
#define VRAM_D_CR       (*(vu8 *)0x04000243)
#define VRAM_E_CR       (*(vu8 *)0x04000244)
#define VRAM_F_CR       (*(vu8 *)0x04000245)
#define VRAM_G_CR       (*(vu8 *)0x04000246)
#define VRAM_H_CR       (*(vu8 *)0x04000248)
#define VRAM_I_CR       (*(vu8 *)0x04000249)
#define VRAM_ENABLE     0x80
#define VRAM_A_LCD      0
#define VRAM_B_LCD      0
#define VRAM_C_LCD      0
#define VRAM_D_LCD      0
#define VRAM_C_SUB_BG   4
#define VRAM_H_SUB_BG   1
#define VRAM_H_LCD      0
#define BG_PALETTE      ((u16 *)0x05000000)
#define BG_PALETTE_SUB  ((u16 *)0x05000400)
#define VRAM_A          ((u16 *)0x06800000)
#define VRAM_B          ((u16 *)0x06820000)
#define VRAM_C          ((u16 *)0x06840000)
#define VRAM_D          ((u16 *)0x06860000)
#define VRAM_H          ((u16 *)0x06898000)
#define REG_DISPCAPCNT  (*(vu32 *)0x04000064)
#define DCAP_MODE_A       0
#define DCAP_MODE_B       1
#define DCAP_SIZE_256x192 3
#define DCAP_BANK(n)      ((n) << 16)
#define DCAP_SIZE(n)      ((n) << 20)
#define DCAP_MODE(n)      ((n) << 29)
#define DCAP_ENABLE       BIT(31)
