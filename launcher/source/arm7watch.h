// SPDX-License-Identifier: MIT
//
// What the ARM7 is doing, for the watchdog (watchdog.c): the ARM9 hands the
// ARM7 this block's address (FIFO_USER_01), and the launcher's ARM7 core
// (arm7/source/main.c) keeps it up to date. If the ARM7 stops, the ARM9 shows
// what's in it.

#ifndef ARM7WATCH_H__
#define ARM7WATCH_H__

#include <stdint.h>

#define ARM7WATCH_MAGIC  0x44573742u     // "B7WD"
#define ARM7WATCH_FIFO   FIFO_USER_01

typedef struct
{
    uint32_t magic;
    uint32_t beats;                 // the ARM7's VBlanks
    uint32_t ie, ie_aux;            // REG_IE and REG_AUXIE, at the last VBlank
    uint16_t timers[4];             // the timers' TIMER_CR, at the last VBlank
    uint32_t irq_used, irq_size;    // the most of the IRQ stack used so far (bytes), of how much
    uint32_t svc_used, svc_size;    // and of the SVC stack (the BIOS's calls)
    uint32_t music_waits;           // music ticks that came while the last one ran
} Arm7Watch;

#endif // ARM7WATCH_H__
