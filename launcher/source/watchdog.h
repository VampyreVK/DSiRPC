// SPDX-License-Identifier: MIT
//
// The watchdog: if the ARM7 stops (its VBlanks stop coming) or the music
// stops moving while a song should play, the bottom screen shows what the
// ARM7 was doing (arm7watch.h), for a photo, instead of a silent freeze. It
// checks at every VBlank, from the interrupt, so it works however stuck the
// launcher's own code is.

#ifndef WATCHDOG_H__
#define WATCHDOG_H__

#include <stdbool.h>

// Hands the ARM7 its record and starts the checks, paused (call once, after
// ui_init())
void watchdog_start(void);

// Paused while the ARM7 may rightly stop or take its time: while the
// launcher connects, as a game starts, as it leaves
void watchdog_pause(bool paused);

#endif // WATCHDOG_H__
