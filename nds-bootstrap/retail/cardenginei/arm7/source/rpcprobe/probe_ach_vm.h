// probe_ach_vm.h - the achievement checker for offline play: runs the
// program DSiRPC builds from a game's RetroAchievements set (the CODE.DRS
// file the launcher copies to sd:/RPCSET.BIN; see DSiRPC's core/offline.py
// for the file and third_party/rcheevos/dsirpc_offline.c for the program).
//
// It is a port of rcheevos 12.5's evaluation (rc_runtime_do_frame,
// rc_evaluate_trigger, rc_test_condset, rc_test_condition, memrefs and
// modified memrefs) without floating point and without the measured
// values, which only matter for progress displays. rcheevos itself parsed
// the set on the PC, so nothing is parsed here.
//
// Plain C with no library calls, so the same file builds for the console
// and for the PC tests that check it against rcheevos frame by frame.

#ifndef PROBE_ACH_VM_H
#define PROBE_ACH_VM_H

#include <stdint.h>

#define ACHVM_PROGRAM_VERSION 2

// What AchVm_Load() can say
#define ACHVM_OK            0
#define ACHVM_E_FORMAT     -1   // not a version 2 program, or it doesn't add up
#define ACHVM_E_SPACE      -2   // the state doesn't fit in the space given

// Achievement states (rcheevos' WAITING, ACTIVE/PRIMED/PAUSED, TRIGGERED)
#define ACHVM_WAITING   0
#define ACHVM_ACTIVE    1
#define ACHVM_TRIGGERED 2

// rcheevos' rc_eval_state_t, the parts that decide triggers
typedef struct {
	int32_t addHits;
	uint8_t isTrue, isPaused, andNext, orNext, resetNext, stop, wasReset, hasHits;
} AchVm_Eval;

// Where AchVm_Run() is inside an achievement, so it can stop after any
// condition and carry on next time
typedef struct {
	AchVm_Eval ev;
	const uint8_t *cs;          // the condset being checked
	uint32_t *hits;             // its first hit count
	uint16_t off[6];            // where its pause, reset, hit target, measured and other
	                            // conditions start (in conditions), and its total
	uint16_t i;                 // the next condition in the current one of those
	uint8_t phase;              // which one (5: the condset is done)
	uint8_t set;                // the condset's number in the achievement
	uint8_t ret, sub;           // the core's result; any alt's
	uint8_t setResult;          // the condset's, once it's done
	uint8_t inAchievement;      // part way through one
} AchVm_Cursor;

typedef struct {
	// The program (read only)
	const uint8_t *plain;       // nPlain x 8 bytes
	const uint8_t *mod;         // nMod x 20 bytes
	const uint8_t *achStart;    // the achievements
	uint16_t nPlain, nMod, nAch;
	uint32_t nConds;

	// The state (zeroed by AchVm_Load)
	uint32_t *memValue;         // per memref: current value
	uint32_t *memPrior;         //   the value before the last change
	uint8_t  *memChanged;       //   1 if it changed in the last update
	uint32_t *hits;             // per condition: current hit count
	uint8_t  *achState;         // per achievement: ACHVM_* | 0x80 = had hits

	// Main RAM as RetroAchievements addresses it (0 = 0x02000000 on the DS);
	// reads at ramSize or past it are 0, like DSiRPC's own reads.
	const uint8_t *ram;
	uint32_t ramSize;

	// Where AchVm_Run() carries on
	const uint8_t *nextAch;
	uint32_t nextHit;
	uint16_t nextIndex;
	uint8_t passStage;          // 0 starting a pass, 1 reading memory values, 2 checking
	uint32_t memNext;           // the next memory value to read
	AchVm_Cursor cur;

	// Counters
	uint32_t rounds;            // complete passes over every achievement
	uint16_t triggered;         // achievements that triggered so far
} AchVm;

// Sets the VM up for a program (the set file's body). state gets the
// running state (AchVm_StateSize() bytes, zeroed here). Returns ACHVM_*.
int AchVm_Load(AchVm *vm, const void *program, uint32_t size, void *state, uint32_t stateSize,
               const uint8_t *ram, uint32_t ramSize);

// The bytes of state a program needs (0 if it isn't a valid program).
uint32_t AchVm_StateSize(const void *program, uint32_t size);

// Called for each achievement that triggers.
typedef void (*AchVm_Triggered)(uint32_t id, void *ud);

// Runs a pass: reads every memory value (rcheevos' memref update), then
// checks achievements in order. Asks keepGoing(ud) every 8 values or
// conditions and after each achievement; when it returns 0 (a time budget),
// stops there and carries on from there next time. Returns 1 if this call
// finished a pass.
int AchVm_Run(AchVm *vm, int (*keepGoing)(void *ud), AchVm_Triggered onTriggered, void *ud);

// The id and state of achievement i (for tests and status).
uint32_t AchVm_AchievementId(const AchVm *vm, uint16_t i);

// Marks achievement id as unlocked already (an earlier session saved it),
// so it isn't checked or reported again. Call it after AchVm_Load().
// Returns 1 if the program has that achievement.
int AchVm_SetUnlocked(AchVm *vm, uint32_t id);

#endif // PROBE_ACH_VM_H
