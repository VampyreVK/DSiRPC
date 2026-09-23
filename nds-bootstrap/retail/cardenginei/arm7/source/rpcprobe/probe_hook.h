// probe_hook.h - prototype for the single entry point cardengine.c's
// myIrqHandlerVBlank() calls once per real VBlank. See probe_hook.c.

#ifndef PROBE_HOOK_H
#define PROBE_HOOK_H

void Probe_VBlankTick(void);

#endif // PROBE_HOOK_H
