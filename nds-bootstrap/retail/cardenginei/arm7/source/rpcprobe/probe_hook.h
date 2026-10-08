// probe_hook.h - the entry points cardengine.c calls: once per real VBlank
// from myIrqHandlerVBlank(), and from its swiHalt hook. See probe_hook.c.

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

#endif // PROBE_HOOK_H
