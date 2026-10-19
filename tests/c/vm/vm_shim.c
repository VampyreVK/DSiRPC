// Test shim: the console's checker (rpcprobe/probe_ach_vm.c) on the PC, for
// tests/test_checker_vm.py (ctypes): up to 4 checkers side by side.
#include <stdint.h>
#include <string.h>
#include "probe_ach_vm.h"

#define NVM 4
static AchVm vms[NVM];
static uint8_t states[NVM][1 << 20];
static uint32_t trig[4096];
static int ntrig;

static void onTrig(uint32_t id, void *ud) { (void)ud; if (ntrig < 4096) trig[ntrig++] = id; }

int shim_load(int k, const uint8_t *program, uint32_t size, const uint8_t *ram, uint32_t ramSize) {
	uint32_t need = AchVm_StateSize(program, size);
	if (!need || need > sizeof(states[k])) return -100;
	return AchVm_Load(&vms[k], program, size, states[k], need, ram, ramSize);
}
static uint32_t budget, left;
static int keep(void *ud) { (void)ud; if (!budget) return 1; if (left == 0) { left = budget; return 0; } left--; return 1; }
// A whole pass (stopping every `stopEvery` time checks if set). Returns triggers.
int shim_pass(int k, uint32_t stopEvery, uint32_t *out) {
	ntrig = 0; budget = stopEvery; left = stopEvery;
	while (!AchVm_Run(&vms[k], keep, onTrig, 0)) {}
	memcpy(out, trig, ntrig * 4);
	return ntrig;
}
int shim_sample(int k, uint32_t *values) { AchVm_Sample(&vms[k], values); return vms[k].nPlain + vms[k].nMod; }
int shim_run_sampled(int k, const uint32_t *values, uint32_t *out) {
	ntrig = 0;
	AchVm_RunSampled(&vms[k], values, onTrig, 0);
	memcpy(out, trig, ntrig * 4);
	return ntrig;
}
int shim_state(int k, int i) { return vms[k].achState[i]; }
uint32_t shim_id(int k, int i) { return AchVm_AchievementId(&vms[k], i); }
int shim_count(int k) { return vms[k].nAch; }
int shim_unlock(int k, uint32_t id) { return AchVm_SetUnlocked(&vms[k], id); }
