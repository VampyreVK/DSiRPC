// dsirpc_shadow3d.c - DSiRPC: the ARM9 cardengine's half of the copy of the
// 3D engine's write-only setup registers that the in-game menu's save states
// keep (common/include/dsirpc_shadow3d.h says why and how). The bootloader
// (bootloaderi/source/arm7/dsirpc_patch3d.c) makes the game's SDK setters
// come here; each one does what the SDK's does, and keeps a copy in
// dsirpcShadow3d.regs.
//
// Only the variants for DS-mode games on the SD card carry it (plain and
// GSDD, the ones the save states run with). The DLDI and TWLSDK variants
// compile this file to nothing, and the bootloader then never finds the block
// and patches nothing.

#include <nds/ndstypes.h>

#if !defined(TWLSDK) && !defined(DLDI)

#include "dsirpc_shadow3d.h"

void dsirpcSh3dTable(void);
void dsirpcSh3dClearColor(void);
void dsirpcSh3dFog(void);
void dsirpcSh3dInitTable(void);

DsirpcShadow3d dsirpcShadow3d __attribute__((aligned(32))) = {
	.magic0 = DSIRPC_SH3D_MAGIC0,
	.magic1 = DSIRPC_SH3D_MAGIC1,
	.version = DSIRPC_SH3D_VERSION,
	.hookTable = (u32)dsirpcSh3dTable,
	.hookClearColor = (u32)dsirpcSh3dClearColor,
	.hookFog = (u32)dsirpcSh3dFog,
	.hookInitTable = (u32)dsirpcSh3dInitTable,
};

#define XSTR(x) STR(x)
#define STR(x) #x

// All ARM code, called from the SDK's (ARM) code with the SDK's arguments,
// and returning to its caller (bx lr, so a Thumb caller too). Only r0-r3 and
// r12 change, as in the SDK's own.
asm(
"	.pushsection .text\n"
"	.syntax unified\n"
"	.arm\n"
"	.align 2\n"

// G3X_SetEdgeColorTable, G3X_SetFogTable and G3X_SetToonTable tail-call
// this in place of the SDK's copy routine: r0 = the table, r1 = its
// registers (0x04000330 the 8 edge colors, 0x04000360 the 32 fog densities,
// 0x04000380 the 32 toon colors). Halfwords, since a GXRgb table only has to
// be halfword-aligned.
"	.global dsirpcSh3dTable\n"
"	.type	dsirpcSh3dTable, %function\n"
"dsirpcSh3dTable:\n"
"	ldr	r12, =0x04000330\n"
"	sub	r2, r1, r12\n"                // where in the window
"	cmp	r2, #0x30\n"
"	movlo	r3, #16\n"
"	moveq	r3, #32\n"
"	movhi	r3, #64\n"
"	ldr	r12, =dsirpcShadow3d + " XSTR(DSIRPC_SH3D_REGS_OFS) "\n"
"	add	r12, r12, r2\n"
"1:	ldrh	r2, [r0], #2\n"
"	strh	r2, [r1], #2\n"
"	strh	r2, [r12], #2\n"
"	subs	r3, r3, #2\n"
"	bne	1b\n"
"	bx	lr\n"

// G3X_SetClearColor(color, alpha, depth, polygonID, fog), patched to jump
// here: CLEAR_COLOR = color | alpha << 16 | polygonID << 24 | (fog: 0x8000),
// CLEAR_DEPTH = depth
"	.global dsirpcSh3dClearColor\n"
"	.type	dsirpcSh3dClearColor, %function\n"
"dsirpcSh3dClearColor:\n"
"	orr	r0, r0, r1, lsl #16\n"
"	orr	r0, r0, r3, lsl #24\n"
"	ldr	r1, [sp]\n"
"	cmp	r1, #0\n"
"	orrne	r0, r0, #0x8000\n"
"	ldr	r1, =0x04000350\n"
"	str	r0, [r1]\n"
"	strh	r2, [r1, #4]\n"
"	ldr	r1, =dsirpcShadow3d + " XSTR(DSIRPC_SH3D_REGS_OFS) " + 0x20\n"
"	str	r0, [r1]\n"
"	strh	r2, [r1, #4]\n"
"	bx	lr\n"

// G3X_SetFog(enable, fogMode, fogSlope, fogOffset), patched to jump here.
// Off: DISP3DCNT loses its fog bit (and never acks either error bit). On:
// FOG_OFFSET = fogOffset, then DISP3DCNT's fog bits are fogSlope << 8 |
// fogMode << 6 | the fog bit.
"	.global dsirpcSh3dFog\n"
"	.type	dsirpcSh3dFog, %function\n"
"dsirpcSh3dFog:\n"
"	ldr	r12, =0x04000060\n"
"	cmp	r0, #0\n"
"	ldrh	r0, [r12]\n"
"	biceq	r0, r0, #0x3080\n"
"	strheq	r0, [r12]\n"
"	bxeq	lr\n"
"	bic	r0, r0, #0x3F40\n"
"	orr	r0, r0, r2, lsl #8\n"
"	orr	r0, r0, r1, lsl #6\n"
"	orr	r0, r0, #0x80\n"
"	add	r1, r12, #0x2FC\n"           // FOG_OFFSET, 0x0400035C
"	strh	r3, [r1]\n"
"	strh	r0, [r12]\n"
"	ldr	r1, =dsirpcShadow3d + " XSTR(DSIRPC_SH3D_REGS_OFS) " + 0x2C\n"
"	strh	r3, [r1]\n"
"	bx	lr\n"

// G3X_InitTable(), patched to jump here: it zeroes the edge colors and the
// fog and toon tables (and the shininess table), so the copy of them is
// zeroed too, then the SDK's own goes on (its first two instructions in
// initTramp, then a jump back to its third)
"	.global dsirpcSh3dInitTable\n"
"	.type	dsirpcSh3dInitTable, %function\n"
"dsirpcSh3dInitTable:\n"
"	ldr	r12, =dsirpcShadow3d + " XSTR(DSIRPC_SH3D_REGS_OFS) "\n"
"	mov	r0, #0\n"
"	mov	r1, #0x10\n"
"1:	subs	r1, r1, #4\n"
"	str	r0, [r12, r1]\n"
"	bne	1b\n"
"	add	r12, r12, #0x30\n"
"	mov	r1, #0x60\n"
"2:	subs	r1, r1, #4\n"
"	str	r0, [r12, r1]\n"
"	bne	2b\n"
"	ldr	pc, =dsirpcShadow3d + " XSTR(DSIRPC_SH3D_TRAMP_OFS) "\n"

"	.ltorg\n"
"	.thumb\n"
"	.popsection\n"
);

#endif
