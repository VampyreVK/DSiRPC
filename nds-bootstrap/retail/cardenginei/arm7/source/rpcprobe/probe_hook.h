// probe_hook.h - prototype for the single entry point cardengine.c's
// myIrqHandlerVBlank() calls once per real VBlank. See probe_hook.c.

#ifndef PROBE_HOOK_H
#define PROBE_HOOK_H

// ndsHeader: the running game's NDS header (cardengine.c's ndsHeader). Read
// once, on the first call, for the game code, ROM version and header CRC
// the hellos report; never written.
void Probe_VBlankTick(const void *ndsHeader);

#endif // PROBE_HOOK_H
