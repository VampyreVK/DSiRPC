// probe_hook.h - the entry points cardengine.c calls: once per real VBlank
// from myIrqHandlerVBlank(), and from its swiHalt hook (and inGameMenu.c,
// when the menu opens and before its sleep). See probe_hook.c.

#ifndef PROBE_HOOK_H
#define PROBE_HOOK_H

// ndsHeader: the running game's NDS header (cardengine.c's ndsHeader). Read
// once, on the first call, for the game code, ROM version and header CRC
// the hellos report; never written. sdMutex: nds-bootstrap's SD card lock
// (cardengine.c's saveMutex), or NULL while a ROM read is under way; only
// used if Probe_HaltTick() never runs (see probe_hook.c).
void Probe_VBlankTick(const void *ndsHeader, int *sdMutex);

// cardengine.c's runCardEngineCheckHalt() calls this every time the game's
// ARM7 idles (swiHalt), outside interrupts: it saves the achievement
// checker's unlocks to the SD card when sdMutex (saveMutex) is free.
void Probe_HaltTick(int *sdMutex);

// The lid closed on a DSi: turns rpcprobe's Wi-Fi off for the rest of the
// game (see probe_hook.c's lid rule). Probe_VBlankTick() calls it itself;
// nds-bootstrap's in-game menu calls it before its own sleep, since the
// VBlank ticks stop while the menu is open.
void Probe_LidClosed(void);

// nds-bootstrap's in-game menu opened: the achievements unlocked so far
// count as seen, so the achievement LED stops pulsing (probe_hook.c), and
// the menu can show them (probe_ach.c, dsirpc_ach_menu.h).
void Probe_MenuOpened(void);

// The in-game menu is resetting or quitting the game, so no VBlank tick
// will say it closed (probe_ach.c's ProbeAch_MenuClosed()).
void Probe_MenuClosed(void);

#endif // PROBE_HOOK_H
