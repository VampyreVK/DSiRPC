// probe_ach.h - offline play's achievement checker, in game. Loads the
// game's set (sd:/RPCSET.BIN, which the DSiRPC launcher puts there) on the
// first VBlank, then checks it with probe_ach_vm.c, the interpreter for the
// program DSiRPC builds with rcheevos. A set has up to two programs: the
// frame lane (achievements that need every frame: sampled at the start of
// every VBlank, checked frame by frame) and the pass lane (the rest: passes
// over them, one after another). The checking runs while the game's ARM7
// idles (ProbeAch_Idle(), from nds-bootstrap's swiHalt hook), or in the
// VBlank for a game whose swiHalt couldn't be hooked. Each unlock is saved
// to sd:/RPCUNLK.BIN (one slot, the format in DSiRPC's core/offline.py) for
// the launcher to hand to DSiRPC later. See probe_ach.c.

#ifndef PROBE_ACH_H
#define PROBE_ACH_H

#include <nds/ndstypes.h>

// What probeAchLoaded says when it isn't the number of achievements
#define PROBE_ACH_NONE       0   // no RPCSET.BIN (no set, or not started from the launcher)
#define PROBE_ACH_E_HEADER  -1   // RPCSET.BIN isn't a version 2, 3 or 4 set
#define PROBE_ACH_E_GAME    -2   // it's another game's set
#define PROBE_ACH_E_SIZE    -3   // too big for the memory set aside for it
#define PROBE_ACH_E_PROGRAM -4   // a program doesn't add up
#define PROBE_ACH_E_STAMP   -5   // damaged (its CRC-32 doesn't match)

extern s16 probeAchLoaded;      // achievements being checked (both lanes), or PROBE_ACH_*
extern u16 probeAchFrameLane;   // of those, checked every frame
extern u32 probeAchStamp;       // the set's stamp (DSiRPC knows which set it built by it)
extern u16 probeAchTriggered;   // achievements unlocked since the game started
extern u16 probeAchSaved;       // of those, saved to RPCUNLK.BIN
extern u16 probeAchLost;        // not saved: no RPCUNLK.BIN, or too many waiting (counted in the VBlank)
extern u16 probeAchSaveFailed;  // not saved: RPCUNLK.BIN full, or the write failed (counted when saving)
extern u16 probeAchWaiting;     // this game's unlocks already in RPCUNLK.BIN at the start (not checked again)

// First VBlank only (it reads the SD card). ndsHeader: the running game's.
void ProbeAch_Load(const void *ndsHeader);

// The console's clock when the launcher started the game, in seconds since
// 2000-01-01 (RPCHAND.TXT's time=; 0 = unknown). Unlocks are dated by the
// console's clock, read when they happen; when it can't be read just then,
// by its last reading (or this) plus the VBlanks counted since.
void ProbeAch_SetTime(u32 secondsSince2000);

// Every VBlank, as early as possible: the frame lane's sample of this frame.
void ProbeAch_Sample(void);

// Every VBlank, last. tickStart: the scanline the VBlank tick started on.
// idleAlive: ProbeAch_Idle() has run lately; if not, the checking happens
// here instead, in what's left of the VBlank budget.
void ProbeAch_Tick(u16 tickStart, int idleAlive);

// Outside interrupts, whenever the game's ARM7 idles (cardengine.c's swiHalt
// hook): the checking, for a while. romWaiting() says nds-bootstrap has an
// ARM9 ROM read to serve; the checking stops for it. Returns 1 if it stopped
// for that (serve it, then call again).
int ProbeAch_Idle(int (*romWaiting)(void));

// Saving unlocks. Outside interrupts (cardengine.c's swiHalt hook), with
// nds-bootstrap's SD card lock held: if ProbeAch_SavePending() says there's
// an unlock to save, ProbeAch_SaveOne() writes the oldest one.
int ProbeAch_SavePending(void);
void ProbeAch_SaveOne(void);

// DSiRPC unlocked an achievement itself ('U', probe_req.c): the in-game
// menu shows it as earned (when: seconds since 2000 by the console's clock)
// and the console stops checking it. From the VBlank; it's done at the next
// turn of checking. Returns 0 if there's no set or no room just now.
int ProbeAch_Push(u32 id, u32 when);

// For the reports, since the last call
typedef struct {
	u16 passes;    // complete passes over the pass lane
	u16 maxLines;  // the longest the checker took in one VBlank, in scanlines
	u16 frames;    // frame lane samples checked
	u16 dropped;   // frames the frame lane couldn't sample (its checking fell behind)
	u16 unclean;   // samples taken without the ARM9 writing its cache back first
	u8  idle;      // 1 if the checking ran in the idle time, 0 in the VBlank
} ProbeAchStats;
void ProbeAch_TakeStats(ProbeAchStats *s);

// The ids of the latest unlocks, oldest first (at most max). Returns how many.
int ProbeAch_RecentIds(u32 *ids, int max);

// nds-bootstrap's in-game menu opened (from probe_hook.c's
// Probe_MenuOpened()): the anchor says it's open and which unlocks are new
// to it (dsirpc_ach_menu.h). ProbeAch_MenuClosed() says it's closed again;
// ProbeAch_Tick() does that too, since the ticks stop while it's open.
void ProbeAch_MenuOpened(void);
void ProbeAch_MenuClosed(void);

#endif // PROBE_ACH_H
