// probe_ach.h - offline play's achievement checker, in game. Loads the
// game's set (sd:/RPCSET.BIN, which the DSiRPC launcher puts there) on the
// first VBlank, then runs it a little every VBlank with probe_ach_vm.c, the
// interpreter for the program DSiRPC builds with rcheevos. See probe_ach.c.

#ifndef PROBE_ACH_H
#define PROBE_ACH_H

#include <nds/ndstypes.h>

// What probeAchLoaded says when it isn't the number of achievements
#define PROBE_ACH_NONE       0   // no RPCSET.BIN (no set, or not started from the launcher)
#define PROBE_ACH_E_HEADER  -1   // RPCSET.BIN isn't a version 2 set
#define PROBE_ACH_E_GAME    -2   // it's another game's set
#define PROBE_ACH_E_SIZE    -3   // too big for the memory set aside for it
#define PROBE_ACH_E_PROGRAM -4   // the program doesn't add up
#define PROBE_ACH_E_STAMP   -5   // damaged (its CRC-32 doesn't match)

extern s16 probeAchLoaded;      // achievements being checked, or PROBE_ACH_*
extern u16 probeAchTriggered;   // achievements unlocked since the game started

// First VBlank only (it reads the SD card). ndsHeader: the running game's.
void ProbeAch_Load(const void *ndsHeader);

// Every VBlank. tickStart: the scanline the VBlank tick started on; the
// checker only uses what's left of its budget.
void ProbeAch_Tick(u16 tickStart);

// For the hellos: complete passes and the longest checker tick (in
// scanlines) since the last call.
void ProbeAch_TakeStats(u16 *passes, u16 *maxLines);

// The ids of the latest unlocks, oldest first (at most max). Returns how many.
int ProbeAch_RecentIds(u32 *ids, int max);

#endif // PROBE_ACH_H
