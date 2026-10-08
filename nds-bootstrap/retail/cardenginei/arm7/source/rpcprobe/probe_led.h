// probe_led.h - the console's LEDs, through the DSi's BPTWL chip (I2C): the
// achievement LED, and the Wi-Fi chip's power (both live in BPTWL[30h]).
// See probe_led.c. Everything here is called from the VBlank interrupt
// (or nds-bootstrap's in-game menu, which runs in its place).

#ifndef PROBE_LED_H
#define PROBE_LED_H

#include <nds/ndstypes.h>

// Every VBlank but the first. `unread`: achievements unlocked this game
// that haven't been seen in the in-game menu yet; the LED pulses while there
// are any. `lidClosed`: the LED shows its normal state (the console is
// about to sleep).
void ProbeLed_Tick(int unread, int lidClosed);

// The lid closed while the launcher's connection was up: turns the Wi-Fi
// chip's SDIO power off (BPTWL[30h] bit 4) and the Wi-Fi LED off.
void ProbeLed_WifiPowerOff(void);

#endif // PROBE_LED_H
