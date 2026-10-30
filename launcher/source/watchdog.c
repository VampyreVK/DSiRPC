// SPDX-License-Identifier: MIT
//
// The watchdog (see watchdog.h). The record lives in main RAM; the ARM7
// writes it (it has no cache) and the ARM9 reads it through the uncached
// mirror.

#include <stdio.h>

#include <nds.h>
#include <maxmod9.h>

#include "arm7watch.h"
#include "music.h"
#include "watchdog.h"

#define STALE_FRAMES (4 * 60)   // 4 s without a sign of life

static Arm7Watch record __attribute__((aligned(32)));
static volatile bool paused = true;
static bool shown;
static uint32_t last_beats, last_pos, beats_stale, music_stale;

static void show(const Arm7Watch *w, const char *what)
{
    shown = true;
    consoleDemoInit();
    BG_PALETTE_SUB[0] = 0;
    consoleClear();
    printf("DSiRPC: %s\n\n", what);
    printf("A photo of this helps find out\nwhy. Then hold POWER.\n\n");
    printf("ARM7 VBlanks: %lu\n", (unsigned long)w->beats);
    printf("IRQ stack: %lu of %lu B used\n", (unsigned long)w->irq_used, (unsigned long)w->irq_size);
    printf("SVC stack: %lu of %lu B used\n", (unsigned long)w->svc_used, (unsigned long)w->svc_size);
    printf("Music ticks that waited: %lu\n", (unsigned long)w->music_waits);
    printf("IE %08lX AUX %08lX\n", (unsigned long)w->ie, (unsigned long)w->ie_aux);
    printf("Timers %04X %04X %04X %04X\n", w->timers[0], w->timers[1], w->timers[2], w->timers[3]);
    printf("Music: pattern %u, row %u\n", (unsigned)mmGetPosition(), (unsigned)mmGetPositionRow());
}

static void check(void)
{
    if (paused || shown)
        return;
    const Arm7Watch *w = memUncached(&record);
    if (w->irq_size == 0)
        return;     // an ARM7 that doesn't keep the record
    if (keysHeld() & KEY_LID)
    {
        beats_stale = music_stale = 0;      // closed: the ARM7 may sleep
        return;
    }
    if (w->beats != last_beats)
    {
        last_beats = w->beats;
        beats_stale = 0;
    }
    else if (++beats_stale == STALE_FRAMES)
    {
        show(w, "the ARM7 stopped");
        return;
    }
    if (!music_on())
    {
        music_stale = 0;
        return;
    }
    uint32_t pos = (mmGetPosition() << 8) | mmGetPositionRow();
    if (pos != last_pos)
    {
        last_pos = pos;
        music_stale = 0;
    }
    else if (++music_stale == STALE_FRAMES)
    {
        show(w, "the music stopped");
    }
}

void watchdog_start(void)
{
    record.magic = ARM7WATCH_MAGIC;
    DC_FlushRange(&record, sizeof(record));
    fifoSendAddress(ARM7WATCH_FIFO, &record);
    irqSet(IRQ_VBLANK, check);
    irqEnable(IRQ_VBLANK);
}

void watchdog_pause(bool on)
{
    beats_stale = music_stale = 0;
    paused = on;
}
