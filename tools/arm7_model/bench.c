// bench.c - the driver arm7_model.py runs on its ARM7 model: nds-bootstrap's
// achievement checker (rpcprobe/probe_ach_vm.c) on its own, built for the
// ARM7 with the cardengine's compiler flags. Like the cardengine, it gets
// memset/memcpy from devkitARM's C library and division from libgcc.
//
// The model puts the set where the console does (DSIRPC_ACH_LOCATION, with
// the program after the 64-byte header) and the game's memory at 0x02000000,
// then calls bench_load() once and bench_pass() for each pass.

#include <stdint.h>
#include "probe_ach_vm.h"

#define PROGRAM ((const uint8_t *)0x0CFB0040) // DSIRPC_ACH_LOCATION + 64
#define RAM     ((const uint8_t *)0x02000000) // RetroAchievements address 0
#define RAM_SIZE 0x400000

AchVm vm;
volatile uint32_t keepCalls;  // how often the checker asked whether to go on
volatile uint32_t keepEvery;  // set by the model: say "stop" every this many asks (0: never)
volatile uint32_t triggers;   // achievements that triggered
static uint32_t keepCount;

// probe_ach.c's keepGoing() asks the scanline counter; here it's "yes",
// or "no" every keepEvery asks, to see what stopping and carrying on costs
static int keepGoing(void *ud) {
	(void)ud;
	keepCalls++;
	if (keepEvery && ++keepCount >= keepEvery) {
		keepCount = 0;
		return 0;
	}
	return 1;
}

static void onTriggered(uint32_t id, void *ud) {
	(void)id;
	(void)ud;
	triggers++;
}

// Returns AchVm_Load()'s result (0 = ACHVM_OK)
int bench_load(uint32_t programSize, uint32_t stateAddress, uint32_t stateSize) {
	return AchVm_Load(&vm, PROGRAM, programSize, (void *)stateAddress, stateSize, RAM, RAM_SIZE);
}

// One whole pass over every memory value and achievement. Returns how many
// calls it took (more than 1 only with keepEvery).
int bench_pass(void) {
	int calls = 1;
	while (!AchVm_Run(&vm, keepGoing, onTriggered, 0)) calls++;
	return calls;
}
