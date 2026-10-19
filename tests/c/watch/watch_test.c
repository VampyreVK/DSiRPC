// Host test of the idle-time write-back's two halves, on fake memory at the
// DS's addresses: rpcprobe's OS_Halt search, asking, freshness and capture
// ring (cardenginei/arm7/source/rpcprobe/probe_watch.c) with the ARM9 half's
// patching (cardenginei/arm9/source/dsirpc_watch.c, its assembly routine
// swapped for a stand-in). tests/test_watch_idle.py builds it and runs one
// case per process:
//   watch_test <case>   prints "ok" and exits 0 when the case passes
//   watch_test --list   prints the cases

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <nds/ndstypes.h>
#include "dsirpc_watch_block.h"
#include "probe_watch.h"

extern DsirpcWatchBlock dsirpcWatchBlock;
void dsirpcIdle(void);
void dsirpcWatchService(void);
void dsirpcWatchReset(void);

// The hardware probe_watch.c touches (watch_decls.h and the -D overrides
// point it here): VCOUNT moves a line per read, IPC_SYNC is a variable, and
// the ARM9 cardengine it looks for the block in starts at the block (or at
// fakeCardengine, 12 KB without one)
u16 fakeVcount, fakeIpc;
u32 fakeScanStart;
static u8 fakeCardengine[0x3000] __attribute__((aligned(32)));
u16 *vcountReg(void) { fakeVcount = (fakeVcount + 1) % 263; return &fakeVcount; }
u8 fakeRing[WATCH_RING_BYTES];
static int icInvalidates;
void DC_FlushRange(const void *b, unsigned s) { (void)b; (void)s; }
void DC_InvalidateRange(const void *b, unsigned s) { (void)b; (void)s; }
void IC_InvalidateRange(const void *b, unsigned s) { (void)b; (void)s; icInvalidates++; }

#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); exit(1); } } while (0)
#define W(a) (*(volatile u32 *)(uintptr_t)(a))

// The game: its ARM9 binary at 0x02004000, 512 KB as stored (compressed)
// but 1 MB of static code once decompressed (its module params' autoload
// start), OS_Halt twice past the stored size, a look-alike, and a copy past
// the static code that isn't the game's
#define BIN    0x02004000u
#define STORED 0x80000u
#define CODE   0x100000u
#define HALT1  (BIN + 0x90000)
#define HALT2  (BIN + 0xF0000)
#define LOOKALIKE (BIN + 0x1000)
#define BEYOND (BIN + CODE + 0x100)
static u8 header[0x200];

static void putHalt(u32 a) { W(a) = DSIRPC_OS_HALT_0; W(a + 4) = DSIRPC_OS_HALT_1; W(a + 8) = DSIRPC_OS_HALT_2; }
static int isHalt(u32 a) { return W(a) == DSIRPC_OS_HALT_0 && W(a + 4) == DSIRPC_OS_HALT_1 && W(a + 8) == DSIRPC_OS_HALT_2; }
static int patched(u32 a) { return W(a) == 0xE51FF004u && W(a + 4) == (u32)(uintptr_t)dsirpcIdle; }

static void loadGame(void) {
	void *ram = mmap((void *)0x02000000, 0x400000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
	CHECK(ram == (void *)0x02000000);
	CHECK((uintptr_t)&dsirpcWatchBlock < 0x100000000u && (uintptr_t)dsirpcIdle < 0x100000000u);
	fakeScanStart = (u32)(uintptr_t)&dsirpcWatchBlock & ~31u;
	for (u32 a = BIN; a < BIN + CODE + 0x10000; a += 4) W(a) = 0xE1A00000u ^ (a * 2654435761u); // junk "code"
	u32 params = BIN + 0x7E4;
	W(params + 0x08) = BIN + CODE;                 // autoload start
	W(params + 0x1C) = 0xDEC00621u; W(params + 0x20) = 0x2106C0DEu;
	putHalt(HALT1); putHalt(HALT2);
	W(LOOKALIKE) = DSIRPC_OS_HALT_0; W(LOOKALIKE + 4) = DSIRPC_OS_HALT_1; W(LOOKALIKE + 8) = 0xE12FFF1Fu; // bx pc
	putHalt(BEYOND);
	u32 bin = BIN, stored = STORED;
	memcpy(&header[0x28], &bin, 4); memcpy(&header[0x2C], &stored, 4);
}

static int romWaitingCalls;
static int romWaitingYes(void) { romWaitingCalls++; return 1; }

// rpcprobe starts and searches in its idle visits, a VBlank after each,
// until it asks for the patch. Returns the visits it took.
static int search(void) {
	loadGame();
	ProbeWatch_Init();
	CHECK(probeWatchArm9 == 1);                    // the block found, nothing patched
	ProbeWatch_Game(header);
	int visits = 0;
	for (; visits < 100000 && !dsirpcWatchBlock.ask; visits++) {
		ProbeWatch_Idle(4, NULL);
		ProbeWatch_Tick();
	}
	return visits;
}

// Up to `max` VBlanks until rpcprobe asks again; returns how many it took
static int ticksUntilAsk(int max) {
	u16 ask = dsirpcWatchBlock.ask;
	int ticks = 0;
	while (dsirpcWatchBlock.ask == ask && ticks < max) { ProbeWatch_Tick(); ticks++; }
	return ticks;
}

// Finds every copy of OS_Halt in the static code, past the stored size,
// in small steps, and nothing else; stops at once for a ROM read
static void caseSearch(void) {
	loadGame();
	ProbeWatch_Init();
	ProbeWatch_Game(header);
	CHECK(ProbeWatch_Idle(4, romWaitingYes) == 1 && romWaitingCalls == 1);
	int visits = search();
	printf("search done after %d visits\n", visits);
	CHECK(visits > 10);                            // spread over many visits of 4 scanlines
	CHECK(dsirpcWatchBlock.ask == 1);
	CHECK(dsirpcWatchBlock.haltAt[0] == HALT1 && dsirpcWatchBlock.haltAt[1] == HALT2);
	CHECK(dsirpcWatchBlock.haltAt[2] == 0 && dsirpcWatchBlock.haltAt[3] == 0);
	CHECK((fakeIpc & 0x0F00) == 0x0300 && (fakeIpc & (1 << 13)));   // rang the doorbell
	// The ARM9 hasn't answered: asks again after 60 VBlanks, not sooner
	CHECK(ticksUntilAsk(1000) == 61 && dsirpcWatchBlock.ask == 2);
}

// A header whose ARM9 binary isn't in main RAM starts no search, and the
// real game's header still does
static void caseBadHeader(void) {
	loadGame();
	ProbeWatch_Init();
	u8 bad[0x200] = {0};
	u32 dst = 0x01FF8000, size = 0x1000;
	memcpy(&bad[0x28], &dst, 4); memcpy(&bad[0x2C], &size, 4);
	ProbeWatch_Game(bad);
	for (int i = 0; i < 2000; i++) CHECK(ProbeWatch_Idle(4, romWaitingYes) == 0);
	CHECK(romWaitingCalls == 0 && ticksUntilAsk(200) == 200 && dsirpcWatchBlock.ask == 0);
	CHECK(search() > 10 && dsirpcWatchBlock.ask == 1 && dsirpcWatchBlock.haltAt[0] == HALT1);
}

// The ARM9's IPC interrupt patches both copies, once
static void casePatch(void) {
	search();
	dsirpcWatchService();
	CHECK(patched(HALT1) && patched(HALT2));
	CHECK(W(HALT1 + 8) == DSIRPC_OS_HALT_2 && W(HALT2 + 8) == DSIRPC_OS_HALT_2);
	CHECK(dsirpcWatchBlock.hooked == 2 && icInvalidates == 2);
	CHECK(W(LOOKALIKE) == DSIRPC_OS_HALT_0 && W(LOOKALIKE + 4) == DSIRPC_OS_HALT_1);
	CHECK(isHalt(BEYOND));
	dsirpcWatchService();                          // nothing new asked: no work
	CHECK(icInvalidates == 2);
	ProbeWatch_Tick();
	CHECK(probeWatchArm9 == 3);                    // a9=3: two copies patched
	CHECK(ticksUntilAsk(500) == 500 && dsirpcWatchBlock.ask == 1);   // and no more asks
}

// The ARM9 half only ever writes over OS_Halt itself, in main RAM
static void caseGuard(void) {
	loadGame();
	DsirpcWatchBlock *b = &dsirpcWatchBlock;
	W(0x02100000) = 0x12345678u;                   // not OS_Halt
	b->haltAt[0] = 0x01FFFFF0;                     // below main RAM
	b->haltAt[1] = 0x023FFFF8;                     // its third word past the end
	b->haltAt[2] = HALT1 + 2;                      // misaligned
	b->haltAt[3] = 0x02100000;
	b->ask++;
	dsirpcWatchService();
	CHECK(b->hooked == 0 && icInvalidates == 0);
	CHECK(W(0x02100000) == 0x12345678u && isHalt(HALT1));
}

// Fresh means a write-back came since the VBlank before
static void caseFresh(void) {
	search();
	dsirpcWatchService();
	ProbeWatch_Tick();
	CHECK(!ProbeWatch_Fresh());
	dsirpcWatchBlock.cleaned++; ProbeWatch_Tick(); CHECK(ProbeWatch_Fresh());
	ProbeWatch_Tick(); CHECK(!ProbeWatch_Fresh());
	dsirpcWatchBlock.cleaned += 5; ProbeWatch_Tick(); CHECK(ProbeWatch_Fresh());
	dsirpcWatchBlock.cleaned = 0; ProbeWatch_Tick(); CHECK(ProbeWatch_Fresh()); // (wrapped)
}

// A build without the ARM9 half: never fresh, never asks
static void caseNoArm9(void) {
	loadGame();
	fakeScanStart = (u32)(uintptr_t)fakeCardengine;
	ProbeWatch_Init();
	CHECK(probeWatchArm9 == 0);
	ProbeWatch_Game(header);
	for (int i = 0; i < 20000; i++) { ProbeWatch_Idle(4, NULL); ProbeWatch_Tick(); }
	dsirpcWatchBlock.cleaned++;
	ProbeWatch_Tick();
	CHECK(!ProbeWatch_Fresh() && dsirpcWatchBlock.ask == 0 && probeWatchArm9 == 0 && fakeIpc == 0);
}

// Capture records: values in order, marked when there was no write-back
static void caseCapture(void) {
	search();
	dsirpcWatchService();
	W(0x02100000) = 0x11223344u;
	u8 req[4 + 5] = { 'W', 0, 1, 1 | WATCH_ARM7_ONLY, 0x02, 0x10, 0x00, 0x00, 4 }; // an older PC's bit: ignored
	u8 count, status;
	ProbeWatch_Set(req, sizeof req, &count, &status);
	CHECK(status == 0);
	dsirpcWatchBlock.cleaned++; ProbeWatch_Tick(); ProbeWatch_Sample(192);
	ProbeWatch_Tick(); ProbeWatch_Sample(193);
	CHECK(fakeRing[0] == 0 && fakeRing[1] == 0);   // tick 0
	CHECK(fakeRing[2] == 0x00 && fakeRing[3] == 192);
	CHECK(fakeRing[4] == 0x44 && fakeRing[7] == 0x11);
	CHECK(fakeRing[8 + 1] == 1);                   // tick 1
	CHECK(fakeRing[8 + 2] == 0x80 && fakeRing[8 + 3] == 193);   // WATCH_REC_ARM7: maybe a frame late
}

static u16 get16(const u8 *p) { return (u16)((p[0] << 8) | p[1]); }

// 'W' and 'F': bad requests refused, the ring's records fetched in order,
// the ones overwritten counted as lost
static void caseFetch(void) {
	loadGame();
	ProbeWatch_Init();
	u8 count, status, out[192];
	u8 fetch[6] = { 'F', 0, 2, 0, 0, 0 };
	ProbeWatch_Fetch(fetch, sizeof fetch, out, sizeof out, &count, &status);
	CHECK(status == 3 && count == 0);              // no watches yet
	ProbeWatch_Fetch(fetch, 5, out, sizeof out, &count, &status);
	CHECK(status == 1);
	u8 badSize[9] = { 'W', 0, 1, 1, 0x02, 0x10, 0x00, 0x00, 3 };
	ProbeWatch_Set(badSize, sizeof badSize, &count, &status);
	CHECK(status == 1);
	u8 badAddr[9] = { 'W', 0, 1, 1, 0x03, 0x80, 0x00, 0x00, 4 };
	ProbeWatch_Set(badAddr, sizeof badAddr, &count, &status);
	CHECK(status == 2);
	u8 tooShort[8] = { 'W', 0, 1, 1, 0x02, 0x10, 0x00, 0x00 };
	ProbeWatch_Set(tooShort, sizeof tooShort, &count, &status);
	CHECK(status == 1);

	// Two watches (4 + 2 bytes): 10-byte records, 204 in the ring
	u8 req[4 + 10] = { 'W', 0, 1, 2, 0x02, 0x10, 0x00, 0x00, 4, 0x02, 0x10, 0x00, 0x10, 2 };
	ProbeWatch_Set(req, sizeof req, &count, &status);
	CHECK(status == 0 && count == 2);
	for (u32 i = 0; i < 300; i++) {
		W(0x02100000) = 0xA0000000u + i;
		*(volatile u16 *)(uintptr_t)0x02100010 = (u16)(0x5000 + i);
		ProbeWatch_Tick();
		ProbeWatch_Sample(192);
	}
	// From record 0: the first 96 were overwritten
	u16 n = ProbeWatch_Fetch(fetch, sizeof fetch, out, sizeof out, &count, &status);
	CHECK(status == 0 && get16(&out[0]) == 96 && get16(&out[2]) == 96 && out[4] == 10);
	CHECK(count == (sizeof out - 5) / 10 && n == 5 + count * 10);
	for (int k = 0; k < count; k++) {
		const u8 *r = &out[5 + 10 * k];
		u32 i = 96 + k;
		CHECK(get16(&r[0]) == i);                  // its tick
		CHECK(r[4] == (u8)i && r[7] == 0xA0);      // 0xA0000000 + i, little-endian
		CHECK(r[8] == (u8)(0x5000 + i) && r[9] == (u8)((0x5000 + i) >> 8));
	}
	// From record 290: the last 10
	fetch[4] = 290 >> 8; fetch[5] = 290 & 0xFF;
	ProbeWatch_Fetch(fetch, sizeof fetch, out, sizeof out, &count, &status);
	CHECK(status == 0 && get16(&out[0]) == 290 && get16(&out[2]) == 0 && count == 10);
	// Caught up: nothing
	fetch[4] = 300 >> 8; fetch[5] = 300 & 0xFF;
	ProbeWatch_Fetch(fetch, sizeof fetch, out, sizeof out, &count, &status);
	CHECK(status == 0 && count == 0 && get16(&out[0]) == 300);
	// A new list starts the ring over
	ProbeWatch_Set(req, sizeof req, &count, &status);
	fetch[4] = 0; fetch[5] = 0;
	ProbeWatch_Fetch(fetch, sizeof fetch, out, sizeof out, &count, &status);
	CHECK(status == 0 && count == 0 && get16(&out[2]) == 0);
}

// A soft reset loads the game again: rpcprobe asks again, and again while a
// copy isn't there yet
static void caseReset(void) {
	search();
	dsirpcWatchService();
	ProbeWatch_Tick();
	CHECK(dsirpcWatchBlock.hooked == 2);
	dsirpcWatchReset();
	CHECK(dsirpcWatchBlock.hooked == 0);
	putHalt(HALT1); putHalt(HALT2);
	W(HALT2 + 4) = 0;                              // the second copy not loaded yet
	int ticks = ticksUntilAsk(1000);
	printf("asked again after %d VBlanks\n", ticks);
	CHECK(dsirpcWatchBlock.ask == 2 && ticks <= 61);
	dsirpcWatchService();
	CHECK(patched(HALT1) && !patched(HALT2) && dsirpcWatchBlock.hooked == 1);
	ProbeWatch_Tick();
	CHECK(probeWatchArm9 == 2);
	W(HALT2 + 4) = DSIRPC_OS_HALT_1;               // now it is
	CHECK(ticksUntilAsk(1000) <= 61 && dsirpcWatchBlock.ask == 3);
	dsirpcWatchService();
	CHECK(patched(HALT1) && patched(HALT2) && dsirpcWatchBlock.hooked == 2);
}

// The doorbell is never rung over another of nds-bootstrap's commands
static void caseDoorbell(void) {
	search();
	dsirpcWatchService();
	dsirpcWatchReset();
	putHalt(HALT1); putHalt(HALT2);
	fakeIpc = 0x0500;                              // not read by the ARM9 yet
	ticksUntilAsk(1000);
	CHECK(dsirpcWatchBlock.ask == 2 && fakeIpc == 0x0500);   // asked, not rung
	dsirpcWatchService();                          // that command's interrupt serves the ask too
	CHECK(dsirpcWatchBlock.hooked == 2);
	// Over nothing, it rings, and keeps the ARM9's incoming value
	dsirpcWatchReset();
	putHalt(HALT1); putHalt(HALT2);
	fakeIpc = 0x0007;
	ticksUntilAsk(1000);
	CHECK(fakeIpc == (0x0007 | 0x0300 | (1 << 13)));
}

static const struct { const char *name; void (*run)(void); } cases[] = {
	{ "search", caseSearch },
	{ "bad-header", caseBadHeader },
	{ "patch", casePatch },
	{ "guard", caseGuard },
	{ "fresh", caseFresh },
	{ "no-arm9", caseNoArm9 },
	{ "capture", caseCapture },
	{ "fetch", caseFetch },
	{ "reset", caseReset },
	{ "doorbell", caseDoorbell },
};

int main(int argc, char **argv) {
	if (argc == 2 && !strcmp(argv[1], "--list")) {
		for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) printf("%s\n", cases[i].name);
		return 0;
	}
	for (size_t i = 0; argc == 2 && i < sizeof cases / sizeof cases[0]; i++) {
		if (!strcmp(argv[1], cases[i].name)) {
			cases[i].run();
			printf("ok\n");
			return 0;
		}
	}
	printf("usage: watch_test <case> | --list\n");
	return 2;
}
