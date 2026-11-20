// dsirpc_shadow3d.h - DSiRPC: a copy of the 3D engine's write-only setup
// registers, for the in-game menu's save states (dsirpc_state.h).
//
// The 3D engine's edge colors, clear color and depth, fog offset, fog table
// and toon table (0x04000330-0x040003BF) can only be written, and a game
// usually sets them once per scene, so a state has no way to read them back
// and a load would come back with whatever the game had set since (the title
// screen's, after Save State & Quit). So nds-bootstrap's bootloader
// (bootloaderi/source/arm7/dsirpc_patch3d.c) finds the SDK functions that set
// them in the game's ARM9 binary as it boots, and makes them write here as
// well as to the hardware: G3X_SetEdgeColorTable, G3X_SetFogTable and
// G3X_SetToonTable copy their table through dsirpcSh3dTable instead of the
// SDK's copy routine (one word in each one's literal pool), and
// G3X_SetClearColor, G3X_SetFog and G3X_InitTable jump to their own copy
// (dsirpcSh3d*, cardenginei/arm9/source/dsirpc_shadow3d.c) as they start.
// A save copies regs[] into its header, and a load writes it back to the
// hardware (and here) before the game goes on.
//
// What this can't see: anything a game writes to these registers with its own
// code instead of the SDK's functions (the fog color and the alpha test
// reference always are: the SDK's setters for those are inline), and a game
// whose SDK build of these functions doesn't look like the ones the
// bootloader knows. valid says which of them the bootloader patched in.
//
// The block lives in the ARM9 cardengine's .data, in the variants for
// DS-mode games on the SD card (plain and GSDD). The bootloader and the
// in-game menu find it by its magic words in that cardengine's 12 KB.

#ifndef DSIRPC_SHADOW3D_H
#define DSIRPC_SHADOW3D_H

#ifndef __ASSEMBLER__
#include <nds/ndstypes.h>
#endif

#define DSIRPC_SH3D_MAGIC0   0x43505244u // "DRPC"
#define DSIRPC_SH3D_MAGIC1   0x44334853u // "SH3D"
#define DSIRPC_SH3D_VERSION  1
#define DSIRPC_SH3D_BASE     0x04000330u // regs[0]
#define DSIRPC_SH3D_SIZE     0x90        // to 0x040003BF

// valid: the setters patched to write here too (each one's part of regs[])
#define DSIRPC_SH3D_EDGE     BIT(0) // 0x00-0x0F edge colors (G3X_SetEdgeColorTable)
#define DSIRPC_SH3D_CLEAR    BIT(1) // 0x20-0x25 clear color and depth (G3X_SetClearColor)
#define DSIRPC_SH3D_FOG      BIT(2) // 0x2C-0x2D fog offset (G3X_SetFog; the rest of it is DISP3DCNT, which can be read)
#define DSIRPC_SH3D_FOGTABLE BIT(3) // 0x30-0x4F fog table (G3X_SetFogTable)
#define DSIRPC_SH3D_TOON     BIT(4) // 0x50-0x8F toon table (G3X_SetToonTable)
#define DSIRPC_SH3D_INIT     BIT(5) // G3X_InitTable, which zeroes the edge colors and both tables (no part of its own)

// For dsirpc_shadow3d.c's assembly
#define DSIRPC_SH3D_TRAMP_OFS 0x20
#define DSIRPC_SH3D_REGS_OFS  0x30

#ifndef __ASSEMBLER__

typedef struct {
	u32 magic0;          // 0x00
	u32 magic1;          // 0x04
	u16 version;         // 0x08
	u16 pad;             // 0x0A
	u32 valid;           // 0x0C DSIRPC_SH3D_*: set by the bootloader as it patches each setter
	u32 hookTable;       // 0x10 the cardengine's routines, for the bootloader
	u32 hookClearColor;  // 0x14
	u32 hookFog;         // 0x18
	u32 hookInitTable;   // 0x1C
	u32 initTramp[4];    // 0x20 G3X_InitTable's first two instructions, then a jump to its third (the bootloader writes these)
	u8 regs[DSIRPC_SH3D_SIZE]; // 0x30 0x04000330-0x040003BF as the patched setters last wrote them
} DsirpcShadow3d;        // 0xC0

#ifndef __cplusplus
_Static_assert(sizeof(DsirpcShadow3d) == 0xC0, "DsirpcShadow3d layout");
_Static_assert(__builtin_offsetof(DsirpcShadow3d, initTramp) == DSIRPC_SH3D_TRAMP_OFS, "DsirpcShadow3d layout");
_Static_assert(__builtin_offsetof(DsirpcShadow3d, regs) == DSIRPC_SH3D_REGS_OFS, "DsirpcShadow3d layout");
#endif

#endif // __ASSEMBLER__

#endif // DSIRPC_SHADOW3D_H
