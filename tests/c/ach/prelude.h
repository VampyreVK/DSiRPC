// Force-included into the offline checker test (-include): the PC's stand-ins
// for main RAM, VCOUNT and the clock that the ACH_* overrides point at.
#include <stdint.h>
extern uint8_t hostRam[0x400000];
uint16_t hostVcount(void);
int hostRtc(uint8_t *t);
