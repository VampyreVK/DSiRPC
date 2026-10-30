// SPDX-License-Identifier: MIT
//
// What the ARM7 is doing, for the watchdog (watchdog.c): the ARM9 hands the
// ARM7 this block's address (FIFO_USER_01), and the launcher's ARM7 core
// (arm7/source/main.c) runs every interrupt handler through a stub that
// counts it in here. If the ARM7 stops, the ARM9 shows what it was in.

#ifndef ARM7WATCH_H__
#define ARM7WATCH_H__

#include <stdint.h>

#define ARM7WATCH_MAGIC  0x44573741u     // "A7WD"
#define ARM7WATCH_FIFO   FIFO_USER_01

typedef struct
{
    uint32_t magic;
    uint32_t beats;             // the ARM7's VBlanks
    uint32_t depth, depth_max;  // handlers running inside each other
    uint32_t stack_low;         // the lowest stack pointer a handler started with
    uint32_t stack_floor;       // where the stack would run into the ARM7's data
    uint32_t last;              // the last handler started: its IRQ bit, + 32 for an AUX one
    uint32_t last_beat;         // and when
    uint32_t ie, ie_aux;        // REG_IE and REG_AUXIE, at the last VBlank
    uint16_t timers[4];         // the timers' TIMER_CR, at the last VBlank
    uint16_t running[64];       // handlers running now, by IRQ bit (32-63: AUX)
    uint32_t started[64];       // how many times each has started
} Arm7Watch;

#endif // ARM7WATCH_H__
