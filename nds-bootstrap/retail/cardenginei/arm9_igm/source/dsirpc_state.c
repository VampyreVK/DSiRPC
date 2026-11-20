// dsirpc_state.c - DSiRPC: the ARM9 half of the save states (dsirpc_state.h),
// and what the in-game menu calls (dsirpc_state_menu.h).
//
// The ARM9 owns the plan: it lays out the slot, takes its own registers,
// I/O and memory (the TCMs, VRAM, palettes, OAM, its view of shared WRAM)
// through the staging buffer, and asks the ARM7 half (dsirpc_state7.c) for
// the rest, one step at a time (request()). State_Save() and State_Load()
// run after the menu has put the game's screens back, so what they see is
// the game's.

#ifndef B4DS

#include <stddef.h>
#include <nds/ndstypes.h>
#include <nds/bios.h>

#include "igm_text.h"
#include "locations.h"
#include "cardengine_header_arm9.h"
#include "dsirpc_state.h"
#include "dsirpc_state_menu.h"

void DC_InvalidateRange(const void *base, u32 size);
void DC_FlushRange(const void *base, u32 size);

extern struct IgmText igmText;
extern vu32* volatile sharedAddr;

extern int dss_setjmp(u32 *ctx) __attribute__((returns_twice));
extern void dss_longjmp(const u32 *ctx) __attribute__((noreturn));
extern u32 dss_call_on_stack(u32 (*fn)(u32), u32 arg, void *stackTop);
extern void *dss_swap_svc_sp(void *sp);
extern void dss_copy32(void *dst, const void *src, u32 bytes);
extern void dss_dc_flush_all(void);
extern void dss_ic_invalidate_all(void);
extern void dss_cp15_read(u32 *out);
extern void dss_cp15_write_mpu(const u32 *in);
extern void dss7Entry(const u32 *services); // dsirpc_state7.c
extern VoidFn changeMpu; // (card_engine_header.s) the MPU opened up to all of 0-0x07FFFFFF, and back
extern VoidFn revertMpu;

#define REG8(a)  (*(vu8 *)(a))
#define REG16(a) (*(vu16 *)(a))
#define REG32(a) (*(vu32 *)(a))

#define IPC_FIFO_CR    0x04000184
#define IPC_FIFO_SEND  0x04000188
#define IPC_FIFO_RECV  0x04100000
#define FIFO_SEND_FULL BIT(1)
#define FIFO_SEND_CLR  BIT(3)
#define FIFO_RECV_EMPT BIT(8)
#define FIFO_RECV_IRQ  BIT(10)
#define FIFO_ERROR     BIT(14)
#define FIFO_ENABLE    BIT(15)
#define FIFO_KEEP      (BIT(2) | BIT(10) | BIT(15))

#define EXT            ((u8 *)INGAME_MENU_EXT_LOCATION)
#define EXT_SIZE       0x40000

#define CMD_SSTE       0x45545353
#define RESULT_PENDING 0x7FFFFFFF

// ce9->valueBits a state has to have been made with (the memory map and
// where the ROM is): ROMinRAM, eSdk2, isSdk5, overlaysCached, useSharedWram,
// cloneboot, isDlp
#define VB_ROMINRAM    BIT(1)
#define VB_ESDK2       BIT(2)
#define VB_ISSDK5      BIT(5)
#define VB_SHAREDWRAM  BIT(13)
#define VB_LAYOUT      (BIT(1) | BIT(2) | BIT(5) | BIT(6) | BIT(13) | BIT(14) | BIT(15))

DssRequest dssReq __attribute__((aligned(32)));
extern u8 bgBak[]; // (inGameMenu.c) the scratch, DssScratch
#define scratch   ((DssScratch *)bgBak)
#define CTX9      (scratch->ctx9)
#define STACK9    (scratch->stack9 + sizeof(scratch->stack9) / sizeof(u32))
#define SVCSTACK9 (scratch->svcStack9 + sizeof(scratch->svcStack9) / sizeof(u32))
static cardengineArm9 *ce9;
static u32 readBusy;

// -- the slot and the request ---------------------------------------------------

static u32 dss_check(const DssHeader *h) {
	const u32 *w = (const u32 *)h;
	u32 c = 0x811C9DC5;
	for (u32 i = 0; i < offsetof(DssHeader, check) / 4; i++) c = (c ^ w[i]) * 0x01000193;
	return c;
}

// One step by the ARM7 half, from its menu loop (one a frame at most). The
// ARM7 loop can miss a command that comes just as it puts MENU back (it
// writes over it), so a step that didn't run (its result still pending) is
// asked for again.
static s32 request(u32 op) {
	DssRequest *r = &dssReq;
	for (int tries = 0; tries < 8; tries++) {
		r->op = op;
		r->result = RESULT_PENDING;
		DC_FlushRange(r, sizeof(*r));
		sharedAddr[0] = (u32)dss7Entry;
		sharedAddr[4] = CMD_SSTE;
		while (sharedAddr[4] == CMD_SSTE) swiDelay(100);
		DC_InvalidateRange(r, sizeof(*r));
		if (r->result != RESULT_PENDING) return r->result;
	}
	return DSS_E_IO;
}

static const u8 *ndsHeader(void) {
	return (const u8 *)((ce9->valueBits & VB_ISSDK5) ? 0x02FFFE00 : 0x027FFE00);
}

static u32 sharedWramSize(u32 wramcnt, int arm7) {
	switch (wramcnt & 3) {
		case 0: return arm7 ? 0 : 0x8000;
		case 3: return arm7 ? 0x8000 : 0;
		default: return 0x4000;
	}
}

static void addRegion(DssHeader *h, u32 *offset, u32 addr, u32 size, u32 kind) {
	DssRegion *g = &h->region[h->regionCount++];
	g->addr = addr;
	g->size = size;
	g->offset = *offset;
	g->kind = kind;
	*offset += (size + 0x1FF) & ~0x1FF;
}

// VRAM banks A-I as the LCDC sees them
static const u32 vramLcdc[9] = { 0x06800000, 0x06820000, 0x06840000, 0x06860000, 0x06880000, 0x06890000, 0x06894000, 0x06898000, 0x068A0000 };
static const u32 vramSize[9] = { 0x20000, 0x20000, 0x20000, 0x20000, 0x10000, 0x4000, 0x4000, 0x8000, 0x4000 };
static vu8 *vramCnt(int bank) { return (vu8 *)(bank < 7 ? 0x04000240 + bank : 0x04000241 + bank); }

// The slot's layout (the same for a save and the load that checks it)
static void buildRegions(DssHeader *h) {
	const u32 vb = h->valueBits;
	u32 offset = DSS_DATA_OFFSET;
	h->regionCount = 0;

	// Main RAM as the game uses it (dumpRam()'s map in the ARM7 cardengine)
	if (vb & VB_ISSDK5) {
		addRegion(h, &offset, 0x02000000, 0x3E0000, DSS_KIND_MAIN);
		addRegion(h, &offset, (h->unitCode == 2) ? 0x02FE0000 : 0x027E0000, 0x1F000, DSS_KIND_MAIN);
		addRegion(h, &offset, 0x02FFF000, 0x1000, DSS_KIND_MAIN);
	} else if (!(vb & VB_ESDK2)) {
		addRegion(h, &offset, 0x02000000, 0x3E0000, DSS_KIND_MAIN);
		addRegion(h, &offset, 0x027E0000, 0x20000, DSS_KIND_MAIN);
	} else {
		addRegion(h, &offset, 0x02000000, 0x3C0000, DSS_KIND_MAIN);
		addRegion(h, &offset, 0x027C0000, 0x40000, DSS_KIND_MAIN);
	}

	// The ARM7's WRAM, and its view of shared WRAM (through its mirror below
	// 0x03800000, where the game's ARM7 sees it: 0x03000000 can be the DSi's
	// WRAM, the cardengine's). With the ARM7 cardengine in WRAM-A at
	// 0x037C0000, that view is WRAM-A, not shared WRAM (which can be the ROM
	// cache's then): its 32 KB, whatever WRAMCNT says.
	addRegion(h, &offset, 0x03800000, 0x10000, DSS_KIND_ARM7);
	u32 shared7;
	if (h->flags & DSS_FLAG_ARM7_NWRAM) shared7 = 0x8000;
	else shared7 = (h->flags & DSS_FLAG_SHARED_WRAM_SKIPPED) ? 0 : sharedWramSize(h->wramcnt, 1);
	if (shared7) addRegion(h, &offset, 0x03800000 - shared7, shared7, DSS_KIND_ARM7);

	// The save (room for the biggest; the ARM7 fills in how much)
	addRegion(h, &offset, 0, DSS_SAVE_MAX, DSS_KIND_SAVE);

	// The ARM9's own
	const u32 itcmSize = 0x200 << ((h->itcmReg >> 1) & 0x1F);
	addRegion(h, &offset, 0, itcmSize < 0x8000 ? itcmSize : 0x8000, DSS_KIND_ARM9);
	addRegion(h, &offset, h->dtcmReg & 0xFFFFF000, 0x4000, DSS_KIND_ARM9);
	addRegion(h, &offset, 0x05000000, 0x800, DSS_KIND_ARM9);
	addRegion(h, &offset, 0x07000000, 0x800, DSS_KIND_ARM9);
	for (int b = 0; b < 9; b++) addRegion(h, &offset, vramLcdc[b], vramSize[b], DSS_KIND_ARM9);
	const u32 shared9 = (h->flags & DSS_FLAG_SHARED_WRAM_SKIPPED) ? 0 : sharedWramSize(h->wramcnt, 0);
	if (shared9) addRegion(h, &offset, 0x03000000, shared9, DSS_KIND_ARM9);

	h->dataSize = offset;
}

// -- the ARM9's hardware --------------------------------------------------------

// io9[] (DssHeader): 0 DISPCNT, 1 DISPSTAT, 2-5 BG0-3CNT, 6 WININ, 7 WINOUT,
// 8 BLDCNT, 9 BLDALPHA, 10 DISP3DCNT, 11 DISPCAPCNT, 12 MASTER_BRIGHT,
// 13-22 the same for the sub engine (no 3D or capture), 23-26 DMA fills,
// 27-34 timers (counter, control), 35 KEYCNT, 36 IPCSYNC, 37 IPCFIFOCNT,
// 38 EXMEMCNT, 39 IE, 40-48 VRAMCNT A-I, 49 WRAMCNT, 50 DIVCNT, 51-54
// DIV numerator, denominator, 55 SQRTCNT, 56-57 SQRT param, 58 POWCNT1,
// 59 GXSTAT, 60-63 DMA controls
static void captureIo9(u32 *io) {
	io[0] = REG32(0x04000000);
	io[1] = REG16(0x04000004);
	for (int i = 0; i < 4; i++) io[2 + i] = REG16(0x04000008 + i * 2);
	io[6] = REG16(0x04000048);
	io[7] = REG16(0x0400004A);
	io[8] = REG16(0x04000050);
	io[9] = REG16(0x04000052);
	io[10] = REG16(0x04000060);
	io[11] = REG32(0x04000064);
	io[12] = REG16(0x0400006C);
	io[13] = REG32(0x04001000);
	for (int i = 0; i < 4; i++) io[14 + i] = REG16(0x04001008 + i * 2);
	io[18] = REG16(0x04001048);
	io[19] = REG16(0x0400104A);
	io[20] = REG16(0x04001050);
	io[21] = REG16(0x04001052);
	io[22] = REG16(0x0400106C);
	for (int d = 0; d < 4; d++) io[23 + d] = REG32(0x040000E0 + d * 4);
	for (int t = 0; t < 4; t++) {
		io[27 + t * 2] = REG16(0x04000100 + t * 4);
		io[28 + t * 2] = REG16(0x04000102 + t * 4);
	}
	io[35] = REG16(0x04000132);
	io[36] = REG16(0x04000180);
	io[37] = REG16(IPC_FIFO_CR);
	io[38] = REG16(0x04000204);
	io[39] = REG32(0x04000210);
	for (int b = 0; b < 9; b++) io[40 + b] = *vramCnt(b);
	io[49] = REG8(0x04000247);
	io[50] = REG16(0x04000280);
	io[51] = REG32(0x04000290);
	io[52] = REG32(0x04000294);
	io[53] = REG32(0x04000298);
	io[54] = REG32(0x0400029C);
	io[55] = REG16(0x040002B0);
	io[56] = REG32(0x040002B8);
	io[57] = REG32(0x040002BC);
	io[58] = REG16(0x04000304);
	io[59] = REG32(0x04000600);
	for (int d = 0; d < 4; d++) io[60 + d] = REG32(0x040000B8 + d * 12);
}

static void restoreIo9(const u32 *io) {
	REG16(0x04000304) = io[58];
	REG16(0x04000204) = io[38];
	REG32(0x04000000) = io[0];
	REG16(0x04000004) = io[1] & 0xFFB8;
	for (int i = 0; i < 4; i++) REG16(0x04000008 + i * 2) = io[2 + i];
	REG16(0x04000048) = io[6];
	REG16(0x0400004A) = io[7];
	REG16(0x04000050) = io[8];
	REG16(0x04000052) = io[9];
	REG16(0x04000060) = io[10];
	REG32(0x04000064) = io[11];
	REG32(0x04001000) = io[13];
	for (int i = 0; i < 4; i++) REG16(0x04001008 + i * 2) = io[14 + i];
	REG16(0x04001048) = io[18];
	REG16(0x0400104A) = io[19];
	REG16(0x04001050) = io[20];
	REG16(0x04001052) = io[21];
	for (int d = 0; d < 4; d++) REG32(0x040000E0 + d * 4) = io[23 + d];
	REG16(0x04000132) = io[35];
	REG16(0x04000180) = io[36] & 0x4F00;
	REG16(IPC_FIFO_CR) = (io[37] & FIFO_KEEP) | FIFO_ERROR;
	REG32(0x04000210) = io[39];
	// (writing the operands starts the hardware again: its results come back)
	REG16(0x04000280) = io[50] & 3;
	REG32(0x04000290) = io[51];
	REG32(0x04000294) = io[52];
	REG32(0x04000298) = io[53];
	REG32(0x0400029C) = io[54];
	REG16(0x040002B0) = io[55] & 1;
	REG32(0x040002B8) = io[56];
	REG32(0x040002BC) = io[57];
	REG32(0x04000600) = io[59] & 0xC0000000;
}

static void setVramCnt(const u32 *io) {
	for (int b = 0; b < 9; b++) *vramCnt(b) = io[40 + b];
}

static void vramToLcdc(void) {
	for (int b = 0; b < 9; b++) *vramCnt(b) = 0x80;
}

static void stopHardware9(void) {
	for (int d = 0; d < 4; d++) REG32(0x040000B8 + d * 12) = 0;
	for (int t = 0; t < 4; t++) REG16(0x04000102 + t * 4) = 0;
}

static void startTimers(const u32 *io) { // (dsirpc_state7.c's)
	for (int t = 0; t < 4; t++) {
		REG16(0x04000100 + t * 4) = io[t * 2];
		REG16(0x04000102 + t * 4) = io[t * 2 + 1];
		REG16(0x04000100 + t * 4) = 0;
	}
}

static u32 drainFifo(u32 *out) {
	u32 n = 0;
	if (!(REG16(IPC_FIFO_CR) & FIFO_ENABLE)) return 0;
	for (int i = 0; i < 32 && !(REG16(IPC_FIFO_CR) & FIFO_RECV_EMPT); i++) {
		const u32 v = REG32(IPC_FIFO_RECV);
		if (out && n < DSS_FIFO_MAX) out[n++] = v;
	}
	REG16(IPC_FIFO_CR) = (REG16(IPC_FIFO_CR) & FIFO_KEEP) | FIFO_ERROR;
	return n;
}

static void feedFifo(const u32 *in, u32 n) {
	if (!(REG16(IPC_FIFO_CR) & FIFO_ENABLE)) return;
	for (u32 i = 0; i < n && i < DSS_FIFO_MAX; i++) {
		for (int t = 0; t < 100000 && (REG16(IPC_FIFO_CR) & FIFO_SEND_FULL); t++);
		REG32(IPC_FIFO_SEND) = in[i];
	}
}

// Both screens black (the master brightness) while the VRAM is the LCDC's
static void blank(int on, const u32 *io) {
	REG16(0x0400006C) = on ? (2 << 14) | 16 : io[12];
	REG16(0x0400106C) = on ? (2 << 14) | 16 : io[22];
}

// The ARM9 cardengine's copy of the 3D engine's write-only setup registers
// (dsirpc_shadow3d.h), or 0 if its variant has none
static DsirpcShadow3d *shadow3d(void) {
	for (u32 a = (u32)ce9; a < (u32)ce9 + 0x3000; a += 32) {
		const DsirpcShadow3d *b = (const DsirpcShadow3d *)a;
		if (b->magic0 == DSIRPC_SH3D_MAGIC0 && b->magic1 == DSIRPC_SH3D_MAGIC1 && b->version == DSIRPC_SH3D_VERSION) return (DsirpcShadow3d *)a;
	}
	return 0;
}

// (word by word: dss_copy32() goes in 32-byte steps, past the block's end)
static void copy3d(u8 *dst, const u8 *src) {
	for (u32 i = 0; i < DSIRPC_SH3D_SIZE; i += 4) *(u32 *)(dst + i) = *(const u32 *)(src + i);
}

// Each DSIRPC_SH3D_* bit's part of the registers: where, and how many bytes
static const u8 g3dParts[5][2] = { { 0x00, 0x10 }, { 0x20, 6 }, { 0x2C, 2 }, { 0x30, 0x20 }, { 0x50, 0x40 } };

// The state's copy back to the registers (the parts both it and this boot's
// cardengine keep), and to the cardengine's copy, which a load doesn't put
// back (it's in the cardengine)
static void restore3d(const DssHeader *h) {
	DsirpcShadow3d *b = shadow3d();
	if (!b) return;
	const u32 valid = h->g3dValid & b->valid;
	for (int p = 0; p < 5; p++) {
		if (!(valid & BIT(p))) continue;
		for (u32 o = g3dParts[p][0], end = o + g3dParts[p][1]; o < end; ) {
			if (!(o & 3) && o + 4 <= end) {
				REG32(DSIRPC_SH3D_BASE + o) = *(const u32 *)(h->g3d + o);
				o += 4;
			} else {
				REG16(DSIRPC_SH3D_BASE + o) = *(const u16 *)(h->g3d + o);
				o += 2;
			}
		}
	}
	copy3d(b->regs, h->g3d);
}

// -- save -------------------------------------------------------------------------

static void fillHeader(DssHeader *h) {
	const u8 *nds = ndsHeader();
	h->version = DSS_VERSION;
	h->headerSize = DSS_HEADER_SIZE;
	for (int i = 0; i < 12; i++) h->title[i] = nds[i];
	for (int i = 0; i < 4; i++) h->gameCode[i] = nds[0x0C + i];
	h->unitCode = nds[0x12];
	h->romVersion = nds[0x1E];
	h->headerCrc = *(const u16 *)(nds + 0x15E);
	h->stamp = igmText.stateStamp;
	h->valueBits = ce9->valueBits;
	h->dtcmReg = h->cp15[14];
	h->itcmReg = h->cp15[15];
	h->wramcnt = h->io9[49];
	if (ce9->valueBits & VB_SHAREDWRAM) h->flags |= DSS_FLAG_SHARED_WRAM_SKIPPED;
	if (dssReq.arm7Nwram) h->flags |= DSS_FLAG_ARM7_NWRAM; // (from the BEGIN before this)
	const DsirpcShadow3d *b = shadow3d();
	if (b) {
		h->g3dValid = b->valid;
		copy3d(h->g3d, b->regs);
	}
}

// The ARM9's regions to the slot, through the staging buffer
static s32 writeArm9Regions(DssHeader *h) {
	DssRequest *r = &dssReq;
	vramToLcdc();
	s32 res = DSS_OK;
	for (u32 i = 0; i < h->regionCount && res == DSS_OK; i++) {
		const DssRegion *g = &h->region[i];
		if (g->kind != DSS_KIND_ARM9) continue;
		for (u32 done = 0; done < g->size && res == DSS_OK; done += EXT_SIZE) {
			const u32 n = (g->size - done < EXT_SIZE) ? g->size - done : EXT_SIZE;
			dss_copy32(EXT, (const void *)(g->addr + done), n);
			DC_FlushRange(EXT, n);
			r->offset = g->offset + done;
			r->len = n;
			res = request(DSS_OP_WRITE);
		}
	}
	setVramCnt(h->io9);
	return res;
}

static u32 saveBody(u32 slot) {
	DssRequest *r = &dssReq;
	DssHeader *h = &r->hdr;
	u32 *w = (u32 *)h;
	for (u32 i = 0; i < sizeof(DssHeader) / 4; i++) w[i] = 0;

	captureIo9(h->io9);
	dss_cp15_read(h->cp15);
	// The game's MPU leaves some of its own memory out (ITCM at 0, where the
	// region list reads it), so open it up for the save. After the read
	// above: a load puts back the game's own.
	(*changeMpu)();
	h->fifo9Count = drainFifo(h->fifo9);
	blank(1, h->io9);

	// (first: it says where the ARM7's cardengine is, for the layout)
	r->slot = slot;
	r->arg = 1;
	s32 res = request(DSS_OP_BEGIN);

	fillHeader(h);
	buildRegions(h);
	for (int i = 0; i < DSS_CTX_WORDS; i++) h->ctx9[i] = CTX9[i];

	// The game's memory out of the data cache, for the ARM7
	dss_dc_flush_all();

	if (res == DSS_OK) res = request(DSS_OP_SAVE7);
	if (res == DSS_OK) res = writeArm9Regions(h);
	if (res == DSS_OK) {
		h->magic = DSS_MAGIC;
		h->check = dss_check(h);
		res = request(DSS_OP_COMMIT);
	}

	// The staging buffer back, and each CPU's FIFO words back in it
	r->arg = 1;
	request(DSS_OP_END);
	feedFifo(h->fifo7, h->fifo7Count);

	dss_dc_flush_all();
	blank(0, h->io9);
	(*revertMpu)();
	return (u32)res;
}

// -- load -------------------------------------------------------------------------

static void addExcl(u32 start, u32 end) {
	DssRequest *r = &dssReq;
	r->excl[r->exclCount][0] = start;
	r->excl[r->exclCount][1] = end;
	r->exclCount++;
}

static u32 loadBody(u32 slot) {
	DssRequest *r = &dssReq;
	DssHeader *h = &r->hdr;
	(void)slot;

	// What stays as it is: this cardengine (its code and the ROM cache's
	// state), its shared area with the ARM7 (the menu's commands go
	// through it), the ROM cache's tables (early SDK 2)
	const u32 ce9Base = (u32)ce9;
	r->exclCount = 0;
	addExcl(ce9Base, ce9Base + 0x3000);
	addExcl(((u32)sharedAddr & ~0xFF), ((u32)sharedAddr & ~0xFF) + 0x40);
	if (ce9->valueBits & VB_ESDK2) addExcl(CACHE_ADDRESS_TABLE_LOCATION2, CACHE_ADDRESS_TABLE_LOCATION2 + 0x6000);

	r->arg = 0;
	if (request(DSS_OP_BEGIN) != DSS_OK) return DSS_E_IO;

	// From here on there's no going back
	blank(1, h->io9);
	dss_swap_svc_sp(SVCSTACK9);
	stopHardware9();
	REG16(IPC_FIFO_CR) = (REG16(IPC_FIFO_CR) & FIFO_KEEP) | FIFO_SEND_CLR | FIFO_ERROR;
	drainFifo(0);
	if (!(h->flags & DSS_FLAG_SHARED_WRAM_SKIPPED)) REG8(0x04000247) = h->wramcnt;
	dss_dc_flush_all();

	// The ARM7: main RAM, its own memory and registers, the save
	request(DSS_OP_LOAD7);

	// (the MPU opened up as for a save; dss_cp15_write_mpu() below puts the
	// state's own back)
	(*changeMpu)();

	// The ARM9's own, through the staging buffer
	vramToLcdc();
	for (u32 i = 0; i < h->regionCount; i++) {
		const DssRegion *g = &h->region[i];
		if (g->kind != DSS_KIND_ARM9) continue;
		for (u32 done = 0; done < g->size; done += EXT_SIZE) {
			const u32 n = (g->size - done < EXT_SIZE) ? g->size - done : EXT_SIZE;
			r->offset = g->offset + done;
			r->len = n;
			request(DSS_OP_READ);
			DC_InvalidateRange(EXT, n);
			dss_copy32((void *)(g->addr + done), EXT, n);
		}
	}
	setVramCnt(h->io9);

	r->arg = 0;
	request(DSS_OP_END);

	restoreIo9(h->io9);
	restore3d(h);
	REG32(0x04000214) = 0xFFFFFFFF; // nothing pending (it can't be set)
	feedFifo(h->fifo7, h->fifo7Count);
	// the ARM7's words came while this IRQ was pending and cleared just now:
	// switching its IRQ off and on raises it again if they're there
	REG16(IPC_FIFO_CR) = ((h->io9[37] & FIFO_KEEP) & ~FIFO_RECV_IRQ) | FIFO_ERROR;
	REG16(IPC_FIFO_CR) = (h->io9[37] & FIFO_KEEP) | FIFO_ERROR;

	dss_dc_flush_all();
	dss_cp15_write_mpu(h->cp15);
	dss_dc_flush_all();
	dss_ic_invalidate_all();

	startTimers(h->io9 + 27);
	blank(0, h->io9);
	dss_longjmp(h->ctx9); // (into the save's dss_setjmp() in stateSave(): its frames are back)
	return DSS_E_IO;
}

// -- what the menu calls --------------------------------------------------------

void State_Init(s32 *mainScreen, u32 busy) {
	ce9 = (cardengineArm9 *)((u8 *)mainScreen - offsetof(cardengineArm9, mainScreen));
	readBusy = busy;
	dssReq.cluster = igmText.stateCluster;
	dssReq.slots = igmText.stateSlots;
	dssReq.fileReady = 0;
	dssReq.extSaved = 0;
	dssReq.saveSize = ce9->saveSize;
}

int State_Slots(void) {
	return igmText.stateSlots;
}

int State_Busy(void) {
	return readBusy != 0;
}

s32 State_List(void) {
	if (!igmText.stateSlots) return DSS_E_NOSLOTS;
	return request(DSS_OP_HEADERS);
}

const DssSlotInfo *State_Info(int slot) {
	return &dssReq.info[slot];
}

// Whether a slot's state is this game's, from this build
s32 State_Usable(int slot) {
	const DssSlotInfo *n = &dssReq.info[slot];
	if (n->magic != DSS_MAGIC) return DSS_E_EMPTY;
	const u8 *nds = ndsHeader();
	for (int i = 0; i < 4; i++) if (n->gameCode[i] != (char)nds[0x0C + i]) return DSS_E_GAME;
	if (n->headerCrc != *(const u16 *)(nds + 0x15E) || n->stamp != igmText.stateStamp) return DSS_E_GAME;
	return DSS_OK;
}

// The slot's whole header, checked against this game and this console's setup
s32 State_Check(int slot) {
	DssRequest *r = &dssReq;
	DssHeader *h = &r->hdr;
	if (!igmText.stateSlots) return DSS_E_NOSLOTS;
	if (readBusy) return DSS_E_BUSY;
	r->slot = slot;
	s32 res = request(DSS_OP_READHDR);
	if (res != DSS_OK) return res;
	if (h->magic != DSS_MAGIC || h->version != DSS_VERSION) return DSS_E_EMPTY;
	if (h->check != dss_check(h)) return DSS_E_CORRUPT;

	const u8 *nds = ndsHeader();
	for (int i = 0; i < 4; i++) if (h->gameCode[i] != (char)nds[0x0C + i]) return DSS_E_GAME;
	if (h->headerCrc != *(const u16 *)(nds + 0x15E) || h->stamp != igmText.stateStamp
	 || ((h->valueBits ^ ce9->valueBits) & VB_LAYOUT)) return DSS_E_GAME;

	u32 cp15[16];
	dss_cp15_read(cp15);
	if (h->dtcmReg != cp15[14] || h->itcmReg != cp15[15]) return DSS_E_HARDWARE;
	if (!(h->flags & DSS_FLAG_ARM7_NWRAM) != !r->arm7Nwram) return DSS_E_HARDWARE; // (READHDR said where it is now)

	// The layout from what the header says the game had (the same build
	// made it, so it's the one it saved with), not from its region list
	const u32 regionCount = h->regionCount, dataSize = h->dataSize;
	buildRegions(h);
	if (h->regionCount != regionCount || h->dataSize != dataSize || dataSize > DSS_SLOT_SIZE) return DSS_E_CORRUPT;
	return DSS_OK;
}

// The registers a load comes back with, then the save on stack9. Nothing in
// this frame changes between the dss_setjmp() and the memory going to the
// slot, so the frame a load puts back is this one as it is now.
static s32 __attribute__((noinline)) stateSave(int slot) {
	if (dss_setjmp(CTX9)) {
		return DSS_RESUMED;
	}
	return (s32)dss_call_on_stack(saveBody, slot, STACK9);
}

// The scratch out of the data cache: the ARM7 uses its stack7, which the
// menu's backup of the tiles left there
static void scratchOut(void) {
	DC_FlushRange(scratch, sizeof(DssScratch));
}

s32 State_Save(int slot) {
	if (!igmText.stateSlots) return DSS_E_NOSLOTS;
	if (readBusy) return DSS_E_BUSY;
	scratchOut();
	return stateSave(slot);
}

s32 State_Load(int slot) {
	s32 res = State_Check(slot);
	if (res != DSS_OK) return res;
	scratchOut();
	return (s32)dss_call_on_stack(loadBody, slot, STACK9);
}

#endif // B4DS
