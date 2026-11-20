// dsirpc_patch3d.c - DSiRPC: patches the game's SDK 3D setters so the ARM9
// cardengine keeps a copy of the 3D engine's write-only setup registers, for
// the in-game menu's save states (common/include/dsirpc_shadow3d.h says why).
//
// Only when the game has save state slots (the in-game menu's text in the
// pagefile says how many) and its ARM9 cardengine has the copy's block
// (the plain and GSDD variants). Each setter is found by what it is made of
// (the registers in its literal pool, and the instructions around them), in
// the forms NitroSDK 3 (Mario Kart DS) and 4 (Pokemon Platinum) build them
// in, and only patched if every part is there: a setter that isn't found
// keeps the SDK's own code and its bit stays out of the block's valid, so a
// load leaves those registers as they are. The same goes for the 2D
// engines' rotate/zoom setter, G2x_SetBGyAffine_ (found by its code alone:
// its registers are an argument).

#include <stddef.h>
#include <nds/ndstypes.h>
#include "nds_header.h"
#include "cardengine_header_arm9.h"
#include "debug_file.h"
#include "my_fat.h"
#include "igm_text.h"
#include "locations.h"
#include "dsirpc_shadow3d.h"

extern u32 iUncompressedSize;

#define W(a) (*(vu32 *)(a))

#define BX_LR        0xE12FFF1E
#define BX_IP        0xE12FFF1C
#define LDR_PC_PC_M4 0xE51FF004 // ldr pc, [pc, #-4]: jump to the next word

static DsirpcShadow3d *findBlock(const cardengineArm9 *ce9) {
	for (u32 a = (u32)ce9; a < (u32)ce9 + 0x3000; a += 32) { // (it's 32-byte aligned)
		if (W(a) == DSIRPC_SH3D_MAGIC0 && W(a + 4) == DSIRPC_SH3D_MAGIC1
		 && ((DsirpcShadow3d *)a)->version == DSIRPC_SH3D_VERSION) {
			return (DsirpcShadow3d *)a;
		}
	}
	return NULL;
}

// Whether the word before a function's first instruction ends the one before
// it (bx lr, or a pop with pc) or is a literal (an address: no instruction a
// function would end on). Keeps a patch from landing part way into one.
static bool startsFunction(u32 a) {
	const u32 w = W(a - 4);
	return w == BX_LR || (w & 0xFFFF8000) == 0xE8BD8000 || (w >= 0x01FF8000 && w < 0x08000000);
}

static void jumpTo(u32 at, u32 to) {
	W(at + 4) = to;
	W(at) = LDR_PC_PC_M4;
}

// G3X_SetEdgeColorTable, G3X_SetFogTable, G3X_SetToonTable, at their
// register's literal (a): ldr ip, =copy; ldr r1, =reg; (mov r2, #bytes;)
// bx ip; .word copy; .word reg. The copy's word becomes the cardengine's.
static bool tableSetter(u32 a, u32 reg, DsirpcShadow3d *b) {
	const u32 bytes = (reg == 0x04000330) ? 16 : (reg == 0x04000360) ? 32 : 64;
	if (W(a - 8) != BX_IP) return false;
	if (!(W(a - 16) == 0xE59FC004 && W(a - 12) == 0xE59F1004)
	 && !(W(a - 20) == 0xE59FC008 && W(a - 16) == 0xE59F1008 && W(a - 12) == (0xE3A02000 | bytes))) {
		return false;
	}
	const u32 copy = W(a - 4);
	if (copy < 0x01FF8000 || copy >= 0x02400000) return false; // (the SDK's copy routine: ITCM or main RAM)
	W(a - 4) = b->hookTable;
	return true;
}

// G3X_SetClearColor, at its CLEAR_COLOR literal (a): it starts with
// ldr ip, [sp] and orr rN, r0, r1, lsl #16 (in either order) and ends with
// bx lr just before its literals, with a strh r2 (the depth) in between
static bool clearColorSetter(u32 a, DsirpcShadow3d *b) {
	if (W(a - 4) != BX_LR) return false;
	for (u32 s = a - 48; s <= a - 24; s += 4) {
		const u32 x = W(s), y = W(s + 4);
		if (!((x == 0xE59DC000 && (y & 0xFFFF0FFF) == 0xE1800801) || ((x & 0xFFFF0FFF) == 0xE1800801 && y == 0xE59DC000))) continue;
		if (!startsFunction(s)) return false;
		bool depth = false;
		for (u32 i = s; i < a; i += 4) if ((W(i) & 0xFFF0FFF0) == 0xE1C020B0) depth = true;
		if (!depth) return false;
		jumpTo(s, b->hookClearColor);
		return true;
	}
	return false;
}

// G3X_SetFog, at its FOG_OFFSET literal (a), with DISP3DCNT's and 0xCF7F in
// the same pool: it starts with cmp r0, #0 (its only one), and has strh r3
// (the offset), bic #0x3F40 and orr #0x80 (DISP3DCNT's fog bits)
static bool fogSetter(u32 a, DsirpcShadow3d *b) {
	bool disp = false, mask = false;
	for (u32 i = a - 8; i <= a + 8; i += 4) {
		if (W(i) == 0x04000060) disp = true;
		if (W(i) == 0x0000CF7F) mask = true;
	}
	if (!disp || !mask) return false;
	u32 s = 0;
	for (u32 i = a - 4; i >= a - 128; i -= 4) {
		if (W(i) == 0xE3500000) {
			s = i;
			break;
		}
	}
	if (!s || !startsFunction(s)) return false;
	bool offset = false, bic = false, orr = false;
	for (u32 i = s; i < a; i += 4) {
		const u32 w = W(i);
		if ((w & 0xFFF0FFFF) == 0xE1C030B0) offset = true;
		if ((w & 0xFFF00FFF) == 0xE3C00DFD) bic = true;
		if ((w & 0xFFF00FFF) == 0xE3800080) orr = true;
	}
	if (!offset || !bic || !orr) return false;
	jumpTo(s, b->hookFog);
	return true;
}

// G3X_InitTable, at the last of its pool's 0x04000330, 0x04000360,
// 0x040004D0 (a): it starts with a push that has lr, then sub sp, sp, #n
// (neither one reads pc, so both run as well from initTramp)
static bool initTable(u32 a, DsirpcShadow3d *b) {
	if (W(a - 4) != 0x04000360 || W(a - 8) != 0x04000330) return false;
	u32 s = 0;
	for (u32 i = a - 12; i >= a - 0x100; i -= 4) {
		if ((W(i) & 0xFFFF4000) == 0xE92D4000) {
			s = i;
			break;
		}
	}
	if (!s || (W(s + 4) & 0xFFFFF000) != 0xE24DD000 || !startsFunction(s)) return false;
	b->initTramp[0] = W(s);
	b->initTramp[1] = W(s + 4);
	b->initTramp[2] = LDR_PC_PC_M4;
	b->initTramp[3] = s + 8;
	jumpTo(s, b->hookInitTable);
	return true;
}

// G2x_SetBGyAffine_(reg, mtx, centerX, centerY, x1, y1), at its first
// instruction (a): a push that has lr, then ldr rN, [r1, #n] (both run as
// well from affTramp); before its first return, mtx's four words read, two
// mla, x1 and y1 read from just past the push, and str to [r0], [r0, #4],
// [r0, #8] and [r0, #12] in that order, the last within 3 of a return. The
// one in Tetris DS, Mario Kart DS and Pokemon Platinum (NitroSDK 3 and 4).
static bool affineSetter(u32 a, u32 hi, DsirpcShadow3d *b) {
	const u32 p = W(a);
	if ((W(a + 4) & 0xFFFF0000) != 0xE5910000) return false;
	u32 pushed = 0;
	for (u32 r = p & 0xFFFF; r; r &= r - 1) pushed += 4;
	u32 stores = 0, mtx = 0, mla = 0, stack = 0, last = 0;
	for (u32 i = a + 4; i < a + 256 && i < hi; i += 4) {
		const u32 w = W(i);
		if ((w & 0xFFFF8000) == 0xE8BD8000 || w == BX_LR) return false;
		if ((w & 0xFFFF0000) == 0xE5910000 && (w & 0xFFF) <= 12 && !(w & 3)) mtx |= BIT((w & 0xFFF) >> 2);
		if ((w & 0x0FE000F0) == 0x00200090) mla++;
		if ((w & 0xFFFF0000) == 0xE59D0000) {
			if ((w & 0xFFF) == pushed) stack |= BIT(0);
			if ((w & 0xFFF) == pushed + 4) stack |= BIT(1);
		}
		if ((w & 0xFFFF0000) == 0xE5800000) {
			if ((w & 0xFFF) != stores * 4) return false;
			if (++stores == 4) {
				last = i;
				break;
			}
		}
	}
	if (!last || mtx != 0xF || mla < 2 || stack != 3 || !startsFunction(a)) return false;
	bool ret = false;
	for (u32 i = last + 4; i <= last + 12 && i < hi; i += 4) {
		if ((W(i) & 0xFFFF8000) == 0xE8BD8000 || W(i) == BX_LR) ret = true;
	}
	if (!ret) return false;
	b->affTramp[0] = W(a);
	b->affTramp[1] = W(a + 4);
	b->affTramp[2] = LDR_PC_PC_M4;
	b->affTramp[3] = a + 8;
	b->affValid = 0;
	jumpTo(a, b->hookAffine);
	return true;
}

void dsirpcPatch3d(const cardengineArm9 *ce9, const tNDSHeader *ndsHeader, u32 pageFileCluster, bool bootstrapOnFlashcard) {
	DsirpcShadow3d *b = findBlock(ce9);
	if (!b) return;

	// stateCluster, stateStamp, stateSlots (and its padding)
	u32 state[3] = {0};
	aFile pageFile;
	getFileFromCluster(&pageFile, pageFileCluster, bootstrapOnFlashcard);
	fileRead((char *)state, &pageFile, INGAME_MENU_PAGEFILE_OFFSET + offsetof(struct IgmText, stateCluster), sizeof(state));
	if ((state[2] & 0xFF) == 0) return;

	b->valid = 0;
	const u32 lo = (u32)ndsHeader->arm9destination + 0x20, hi = (u32)ndsHeader->arm9destination + iUncompressedSize - 8;
	for (u32 a = lo; a < hi; a += 4) {
		const u32 v = W(a);
		if ((v & 0xFFFF4000) == 0xE92D4000) {
			if (!(b->valid & DSIRPC_SH3D_AFFINE) && affineSetter(a, hi, b)) b->valid |= DSIRPC_SH3D_AFFINE;
			continue;
		}
		if ((v & 0xFFFFF000) != 0x04000000) continue;
		switch (v) {
			case 0x04000330:
				if (tableSetter(a, v, b)) b->valid |= DSIRPC_SH3D_EDGE;
				break;
			case 0x04000360:
				if (tableSetter(a, v, b)) b->valid |= DSIRPC_SH3D_FOGTABLE;
				break;
			case 0x04000380:
				if (tableSetter(a, v, b)) b->valid |= DSIRPC_SH3D_TOON;
				break;
			case 0x04000350:
				if (clearColorSetter(a, b)) b->valid |= DSIRPC_SH3D_CLEAR;
				break;
			case 0x0400035C:
				if (fogSetter(a, b)) b->valid |= DSIRPC_SH3D_FOG;
				break;
			case 0x040004D0:
				if (initTable(a, b)) b->valid |= DSIRPC_SH3D_INIT;
				break;
		}
	}

	dbg_printf("DSiRPC: 3D setters patched: ");
	dbg_hexa(b->valid);
	dbg_printf("\n");
}
