// dsirpc_state7.c - DSiRPC: the ARM7 half of the save states (dsirpc_state.h).
//
// ARM code for the ARM7 (the Makefile builds this file alone for ARMv4T),
// in the in-game menu's window in main RAM, so it costs the ARM7 cardengine
// (which is nearly full) only its SSTE command and its services table. The
// ARM9 half (dsirpc_state.c) asks for one step at a time in dssReq; the ARM7
// cardengine's menu loop runs it from its SSTE command: dss7Entry(services).
//
// Plain C with no library calls (no memcpy, no division: the IGM's libraries
// are ARM9 code). The save and the load run on stack7 (the load writes over
// the ARM7's own stacks); the other steps are file reads and writes, as the
// ARM7 cardengine's own menu commands do, on the stack they're called on.

#ifndef B4DS

#include <nds/ndstypes.h>
#include "dsirpc_state.h"
#include "locations.h"
#include "cardengine_header_arm7.h"
#include "../../arm7/source/rpcprobe/probe_ach_vm.h"

#define REG8(a)  (*(vu8 *)(a))
#define REG16(a) (*(vu16 *)(a))
#define REG32(a) (*(vu32 *)(a))

#define IPC_FIFO_CR    0x04000184
#define IPC_FIFO_SEND  0x04000188
#define IPC_FIFO_RECV  0x04100000
#define FIFO_SEND_FULL BIT(1)
#define FIFO_SEND_CLR  BIT(3)
#define FIFO_RECV_EMPT BIT(8)
#define FIFO_ERROR     BIT(14)
#define FIFO_ENABLE    BIT(15)
#define FIFO_KEEP      (BIT(2) | BIT(10) | BIT(15)) // its IRQ enables and its enable

#define EXT_SIZE       0x40000                      // the staging buffer
#define EXT_PAGE       0x540000                     // its backup in pagefile.sys (as the screenshot's)

typedef u32 (*FileIoFn)(char *buffer, void *file, u32 startOffset, u32 length);

#define BOOTSTRAP_ON_FLASHCARD BIT(19) // the ARM7 cardengine's valueBits
#define FAT_CARD2              BIT(2)  // an aFile's fatTableSettings (my_fat.h)

extern DssRequest dssReq; // dsirpc_state.c
extern int dss_setjmp(u32 *ctx) __attribute__((returns_twice));
extern void dss_longjmp(const u32 *ctx) __attribute__((noreturn));
extern u32 dss_call_on_stack(u32 (*fn)(u32), u32 arg, void *stackTop);
extern void *dss_swap_svc_sp(void *sp);

extern u8 bgBak[]; // (inGameMenu.c) the scratch, DssScratch: only a save and a load use it
#define STACK7    (((DssScratch *)bgBak)->stack7 + 0x400)
#define SVCSTACK7 (((DssScratch *)bgBak)->svcStack7 + 0x80)
static const u32 *svc;

#define fileRead(b, f, o, l)  ((FileIoFn)svc[DSS_SVC_FILE_READ])((char *)(b), (f), (o), (l))
#define fileWrite(b, f, o, l) ((FileIoFn)svc[DSS_SVC_FILE_WRITE])((char *)(b), (f), (o), (l))
#define saveFile ((void *)(dssReq.arm7Nwram ? SAV_FILE_LOCATION : SAV_FILE_LOCATION_ALT)) // (the ARM7 cardengine's, or its ALTERNATIVE's)

// The ARM7 cardengine's header, from where its services table is (inside it)
static const cardengineArm7 *ce7(void) {
	const u32 s = (u32)svc;
	return (const cardengineArm7 *)((s >= CARDENGINEI_ARM7_LOCATION_DLDI) ? CARDENGINEI_ARM7_LOCATION_DLDI
		: (s >= 0x037C0000) ? CARDENGINEI_ARM7_LOCATION
		: (s >= CARDENGINEI_ARM7_LOCATION_ALT_DLDI) ? CARDENGINEI_ARM7_LOCATION_ALT_DLDI : CARDENGINEI_ARM7_LOCATION_ALT);
}

// An aFile (my_fat.h's: firstCluster, currentCluster, currentOffset,
// fatTableSettings, then no FAT cache), as getFileFromCluster() makes one
static void makeFile(u32 *w, u32 cluster, u32 settings) {
	w[0] = cluster;
	w[1] = cluster;
	w[2] = 0;
	w[3] = settings;
	w[4] = 0;
	w[5] = 0;
}

// The slot file (on the SD card: its save's there), and pagefile.sys (where
// nds-bootstrap is), made once a menu opening
static void filesReady(void) {
	DssRequest *r = &dssReq;
	if (r->fileReady) return;
	const cardengineArm7 *c = ce7();
	makeFile(r->fileWords, r->cluster, 0);
	makeFile(r->pageWords, c->pageFileCluster, (c->valueBits & BOOTSTRAP_ON_FLASHCARD) ? FAT_CARD2 : 0);
	r->fileReady = 1;
}

static void *slotFile(void) {
	filesReady();
	return dssReq.fileWords;
}

#define pageFile (filesReady(), (void *)dssReq.pageWords)

static u32 slotBase(void) {
	return dssReq.slot * DSS_SLOT_SIZE;
}

// The game's save size now (0 if a state can't carry it)
static u32 saveSize(void) {
	const u32 size = dssReq.saveSize;
	return (size <= DSS_SAVE_MAX) ? size : 0;
}

// -- the hardware ---------------------------------------------------------------

// The FIFO words this CPU has received and not read (up to DSS_FIFO_MAX kept)
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

// The other CPU's words back in its receive FIFO
static void feedFifo(const u32 *in, u32 n) {
	if (!(REG16(IPC_FIFO_CR) & FIFO_ENABLE)) return;
	for (u32 i = 0; i < n && i < DSS_FIFO_MAX; i++) {
		for (int t = 0; t < 100000 && (REG16(IPC_FIFO_CR) & FIFO_SEND_FULL); t++);
		REG32(IPC_FIFO_SEND) = in[i];
	}
}

// io7[] (DssHeader): 0 IE, 1 IPCSYNC, 2 IPCFIFOCNT, 3 DISPSTAT, 4 KEYCNT,
// 5 RCNT, 6 POWCNT2, 7 SOUNDCNT, 8 SOUNDBIAS, 9-16 timers (counter,
// control), 17 SNDCAPCNT, 18 WIFIWAITCNT, 19 WRAMSTAT, 20-23 DMA controls
static void captureIo7(u32 *io) {
	io[0] = REG32(0x04000210);
	io[1] = REG16(0x04000180);
	io[2] = REG16(IPC_FIFO_CR);
	io[3] = REG16(0x04000004);
	io[4] = REG16(0x04000132);
	io[5] = REG16(0x04000134);
	io[6] = REG16(0x04000304);
	io[7] = REG16(0x04000500);
	io[8] = REG16(0x04000504);
	for (int t = 0; t < 4; t++) {
		io[9 + t * 2] = REG16(0x04000100 + t * 4);
		io[10 + t * 2] = REG16(0x04000102 + t * 4);
	}
	io[17] = REG16(0x04000508);
	io[18] = REG16(0x04000206);
	io[19] = REG8(0x04000241);
	for (int d = 0; d < 4; d++) io[20 + d] = REG32(0x040000B8 + d * 12);
}

// SOUNDCNT's output selection: the speakers fed from channels 1 and 3, not
// the mixer, and those two kept out of the mixer
#define SND_ROUTE 0x3F00

// The SDK's capture effect (reverb, surround): the two captures record the
// mix and channels 1 and 3 play it to the speakers. Their addresses can't be
// read, so they can't be started again after a load. When this session has
// the same effect running (the same output selection and captures, both
// channels playing), it's the one the state has: games set it up once, at
// boot (Mario Kart DS), so it keeps running through the load.
static int keepEffect(const u32 *io) {
	return (io[7] & SND_ROUTE) && (REG16(0x04000500) & SND_ROUTE) == (io[7] & SND_ROUTE)
		&& (io[17] & 0x8080) && REG16(0x04000508) == io[17]
		&& (REG32(0x04000410) & BIT(31)) && (REG32(0x04000430) & BIT(31));
}

// What could read or write memory while it's put back: the sound channels
// and captures, the DMAs, the timers (but not the capture effect when it's
// kept: it only writes its own buffer)
static void stopHardware7(int keep) {
	for (int ch = 0; ch < 16; ch++) {
		if (!keep || (ch != 1 && ch != 3)) REG32(0x04000400 + ch * 16) = 0;
	}
	if (!keep) {
		REG8(0x04000508) = 0;
		REG8(0x04000509) = 0;
	}
	for (int d = 0; d < 4; d++) REG32(0x040000B8 + d * 12) = 0;
	for (int t = 0; t < 4; t++) REG16(0x04000102 + t * 4) = 0;
}

static void restoreIo7(const u32 *io, int keep) {
	REG16(0x04000304) = io[6];
	// (an effect that isn't running any more: the speakers from the mixer, or
	// they'd play nothing until the game sets it up again)
	REG16(0x04000500) = keep ? io[7] : (io[7] & ~SND_ROUTE);
	REG16(0x04000504) = io[8];
	REG16(0x04000132) = io[4];
	REG16(0x04000134) = io[5];
	REG16(0x04000206) = io[18];
	// the IRQ enables; the VCount setting stays (the cardengine's refresh
	// rate option sets it)
	REG16(0x04000004) = (REG16(0x04000004) & 0xFF80) | (io[3] & 0x38);
	REG16(0x04000180) = io[1] & 0x4F00;
	REG16(IPC_FIFO_CR) = (io[2] & FIFO_KEEP) | FIFO_ERROR;
	REG32(0x04000210) = io[0];
	REG32(0x04000214) = 0xFFFFFFFF; // nothing pending (it can't be set)
}

// A timer from its counter: the counter as the reload value, started, then
// the reload value 0 (what it reloads from after that isn't readable: most
// games' timers reload from 0, and the ones that don't set it again from
// their IRQ)
static void startTimers(const u32 *io) {
	for (int t = 0; t < 4; t++) {
		REG16(0x04000100 + t * 4) = io[t * 2];
		REG16(0x04000102 + t * 4) = io[t * 2 + 1];
		REG16(0x04000100 + t * 4) = 0;
	}
}

// -- the achievement checker ----------------------------------------------------

// After a load, the checker's memory of the game is from another time: every
// achievement that hasn't triggered goes back to waiting with no hits (it
// has to be false once before it can trigger), as rcheevos' rc_runtime_reset()
// does after a state load, and a pass stopped part way through an
// achievement starts that one again.
static void resetVm(AchVm *vm) {
	if (!vm || !vm->nAch || !vm->achState) return;
	for (u32 i = 0; i < vm->nAch; i++) {
		if ((vm->achState[i] & 3) != ACHVM_TRIGGERED) vm->achState[i] = ACHVM_WAITING;
	}
	if (vm->hits) for (u32 i = 0; i < vm->nConds; i++) vm->hits[i] = 0;
	vm->cur.inAchievement = 0;
}

static void resetChecker(void) {
	for (int i = 0; i < 3; i++) resetVm((AchVm *)svc[DSS_SVC_ACH_VM + i]);
	if (svc[DSS_SVC_ACH_SHADOW]) resetVm(*(AchVm **)svc[DSS_SVC_ACH_SHADOW]);
}

// The RTC's date and time, as clock.c's rtcGetTimeAndDate() reads them (its
// own copy: the services table is 4 bytes shorter for it), with a loop for
// its delays: year (from 2000), month, day, weekday, hours, minutes, seconds
#define RTC_CR8 (*(vu8 *)0x04000138)
#define RTC_CS_0  BIT(6)
#define RTC_CS_1  (BIT(6) | BIT(2))
#define RTC_SCK_0 BIT(5)
#define RTC_SCK_1 (BIT(5) | BIT(1))
#define RTC_SIO_1 (BIT(4) | BIT(0))
#define RTC_SIO_OUT BIT(4)
#define RTC_SIO_IN  BIT(0)

static void rtcWait(void) {
	for (vu32 i = 0; i < 48; i++) {} // (longer than clock.c's swiDelay(48): fine for the RTC)
}

static void rtcRead(u32 command, u8 *out, u32 length) {
	RTC_CR8 = RTC_CS_0 | RTC_SCK_1 | RTC_SIO_1;
	rtcWait();
	RTC_CR8 = RTC_CS_1 | RTC_SCK_1 | RTC_SIO_1;
	rtcWait();
	for (int bit = 7; bit >= 0; bit--) { // the command, high bit first
		const u32 b = (command >> bit) & 1;
		RTC_CR8 = RTC_CS_1 | RTC_SCK_0 | RTC_SIO_OUT | b;
		rtcWait();
		RTC_CR8 = RTC_CS_1 | RTC_SCK_1 | RTC_SIO_OUT | b;
		rtcWait();
	}
	for (; length; length--) { // the result, low bit first
		u32 data = 0;
		for (int bit = 0; bit < 8; bit++) {
			RTC_CR8 = RTC_CS_1 | RTC_SCK_0;
			rtcWait();
			RTC_CR8 = RTC_CS_1 | RTC_SCK_1;
			rtcWait();
			if (RTC_CR8 & RTC_SIO_IN) data |= 1 << bit;
		}
		*out++ = data;
	}
	RTC_CR8 = RTC_CS_0 | RTC_SCK_1;
	rtcWait();
}

static void rtcTime(u8 *t) {
	u8 status;
	rtcRead(0x65, t, 7);     // READ_TIME_AND_DATE
	rtcRead(0x61, &status, 1); // READ_STATUS_REG1
	const u32 pm = t[4] & 0x40;
	t[4] &= 0x3F;
	for (int i = 0; i < 7; i++) t[i] = (t[i] & 0xF) + (t[i] >> 4) * 10; // (BCD)
	if (!(status & 0x02) && pm) t[4] += 12; // (12-hour mode)
}

// -- the steps ------------------------------------------------------------------

// Main RAM back from the slot, but for the ranges that stay as they are
static int readMain(void *f, u32 addr, u32 size, u32 offset) {
	DssRequest *r = &dssReq;
	u32 cur = addr;
	const u32 end = addr + size;
	while (cur < end) {
		int skipped = 0;
		for (u32 i = 0; i < r->exclCount; i++) {
			if (cur >= r->excl[i][0] && cur < r->excl[i][1]) {
				cur = r->excl[i][1];
				skipped = 1;
			}
		}
		if (skipped) continue;
		u32 stop = end;
		for (u32 i = 0; i < r->exclCount; i++) {
			if (r->excl[i][0] > cur && r->excl[i][0] < stop) stop = r->excl[i][0];
		}
		if (fileRead(cur, f, offset + (cur - addr), stop - cur) != stop - cur) return 0;
		cur = stop;
	}
	return 1;
}

// The save, through the staging buffer (both are files)
static int copySave(void *from, u32 fromOff, void *to, u32 toOff, u32 size) {
	for (u32 done = 0; done < size; done += EXT_SIZE) {
		const u32 n = (size - done < EXT_SIZE) ? size - done : EXT_SIZE;
		if (fileRead(INGAME_MENU_EXT_LOCATION, from, fromOff + done, n) != n) return 0;
		if (fileWrite(INGAME_MENU_EXT_LOCATION, to, toOff + done, n) != n) return 0;
	}
	return 1;
}

static u32 save7(u32 unused) {
	(void)unused;
	DssRequest *r = &dssReq;
	DssHeader *h = &r->hdr;
	void *f = slotFile();
	const u32 base = slotBase();

	captureIo7(h->io7);
	h->fifo7Count = drainFifo(h->fifo7);
	rtcTime(h->time);
	h->saveSize = saveSize();
	if (h->saveSize) h->flags |= DSS_FLAG_SAVE_INCLUDED;

	r->result = DSS_E_IO;
	for (u32 i = 0; i < h->regionCount; i++) {
		const DssRegion *g = &h->region[i];
		if (g->kind == DSS_KIND_MAIN || g->kind == DSS_KIND_ARM7) {
			if (fileWrite(g->addr, f, base + g->offset, g->size) != g->size) return 0;
		} else if (g->kind == DSS_KIND_SAVE) {
			if (!copySave(saveFile, 0, f, base + g->offset, h->saveSize)) return 0;
		}
	}
	r->result = DSS_OK;
	return 0;
}

static u32 load7(u32 unused) {
	(void)unused;
	DssRequest *r = &dssReq;
	DssHeader *h = &r->hdr;
	void *f = slotFile();
	const u32 base = slotBase();

	if (h->magic != DSS_MAGIC) {
		r->result = DSS_E_EMPTY;
		return 0;
	}

	// From here on there's no going back: the BIOS calls' stack off the
	// game's WRAM, then nothing running that reads or writes memory
	dss_swap_svc_sp(SVCSTACK7);
	const int keep = keepEffect(h->io7);
	stopHardware7(keep);
	REG16(IPC_FIFO_CR) = (REG16(IPC_FIFO_CR) & FIFO_KEEP) | FIFO_SEND_CLR | FIFO_ERROR;
	drainFifo(0);

	for (u32 i = 0; i < h->regionCount; i++) {
		const DssRegion *g = &h->region[i];
		if (g->kind == DSS_KIND_MAIN) {
			readMain(f, g->addr, g->size, base + g->offset);
		} else if (g->kind == DSS_KIND_ARM7) {
			fileRead(g->addr, f, base + g->offset, g->size);
		} else if (g->kind == DSS_KIND_SAVE) {
			const u32 now = saveSize(); // (the save file can't grow)
			copySave(f, base + g->offset, saveFile, 0, (h->saveSize < now) ? h->saveSize : now);
		}
	}

	restoreIo7(h->io7, keep);
	feedFifo(h->fifo9, h->fifo9Count);
	resetChecker();
	startTimers(h->io7 + 9);

	r->result = DSS_OK;
	dss_longjmp(h->ctx7); // (into save7's dss_setjmp() in dss7Entry: the frames it took are back)
	return 0;
}

static u32 step7(u32 op) {
	DssRequest *r = &dssReq;
	void *f;
	u32 i, base;

	r->result = DSS_OK;
	switch (op) {
		case DSS_OP_HEADERS:
			f = slotFile();
			base = 0;
			for (i = 0; i < r->slots && i < DSS_MAX_SLOTS; i++, base += DSS_SLOT_SIZE) {
				DssSlotInfo *n = &r->info[i];
				n->magic = 0;
				// (into hdr, which only a save or a load needs)
				if (fileRead(&r->hdr, f, base, 0x200) != 0x200) continue;
				const DssHeader *h = &r->hdr;
				if (h->magic != DSS_MAGIC || h->version != DSS_VERSION) continue;
				n->magic = h->magic;
				for (int k = 0; k < 4; k++) n->gameCode[k] = h->gameCode[k];
				n->stamp = h->stamp;
				for (int k = 0; k < 8; k++) n->time[k] = h->time[k];
				n->headerCrc = h->headerCrc;
			}
			break;
		case DSS_OP_BEGIN:
			if (!r->extSaved) {
				if (fileWrite(INGAME_MENU_EXT_LOCATION, pageFile, EXT_PAGE, EXT_SIZE) != EXT_SIZE) {
					r->result = DSS_E_IO;
					break;
				}
				r->extSaved = 1;
			}
			if (r->arg) { // a save: the slot has no state until its header is back (zeros from the staging buffer, saved now)
				u32 *zero = (u32 *)INGAME_MENU_EXT_LOCATION;
				for (i = 0; i < 0x200 / 4; i++) zero[i] = 0;
				if (fileWrite(zero, slotFile(), slotBase(), 0x200) != 0x200) r->result = DSS_E_IO;
			}
			break;
		case DSS_OP_WRITE:
			if (fileWrite(INGAME_MENU_EXT_LOCATION, slotFile(), slotBase() + r->offset, r->len) != r->len) r->result = DSS_E_IO;
			break;
		case DSS_OP_READ:
			if (fileRead(INGAME_MENU_EXT_LOCATION, slotFile(), slotBase() + r->offset, r->len) != r->len) r->result = DSS_E_IO;
			break;
		case DSS_OP_COMMIT:
			if (fileWrite(&r->hdr, slotFile(), slotBase(), DSS_HEADER_SIZE) != DSS_HEADER_SIZE) r->result = DSS_E_IO;
			break;
		case DSS_OP_READHDR:
			if (fileRead(&r->hdr, slotFile(), slotBase(), DSS_HEADER_SIZE) != DSS_HEADER_SIZE) r->result = DSS_E_IO;
			break;
		case DSS_OP_END:
			if (r->extSaved) {
				fileRead(INGAME_MENU_EXT_LOCATION, pageFile, EXT_PAGE, EXT_SIZE);
				r->extSaved = 0;
			}
			if (r->arg) feedFifo(r->hdr.fifo9, r->hdr.fifo9Count); // after a save: the ARM9's words back
			break;
		case DSS_OP_LOAD7:
			load7(0); // (returns only if the slot is no good)
			break;
		default:
			r->result = DSS_E_IO;
			break;
	}
	return 0;
}

// The SSTE command (cardenginei/arm7 inGameMenu.c), in the ARM7 menu loop
void dss7Entry(const u32 *services) {
	svc = services;
	dssReq.arm7Nwram = (((u32)services) & 0xFFFC0000) == 0x037C0000;
	if (dssReq.op == DSS_OP_SAVE7) {
		// The registers a load comes back with. Nothing in this frame
		// changes between here and the memory going to the slot (that runs on
		// stack7), so the frame the load puts back is this one as it is now.
		if (dss_setjmp(dssReq.hdr.ctx7)) {
			return; // a load: back in the menu loop the save was made from
		}
		dss_call_on_stack(save7, 0, STACK7);
		return;
	}
	if (dssReq.op == DSS_OP_LOAD7) {
		dss_call_on_stack(step7, DSS_OP_LOAD7, STACK7);
		return;
	}
	step7(dssReq.op);
}

#endif // B4DS
