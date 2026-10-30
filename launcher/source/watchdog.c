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

static const char *irq_name(uint32_t n, char *buf)
{
    static const char *const NAMES[64] = {
        [0] = "VBlank", [1] = "HBlank", [2] = "VCount", [3] = "timer0 (music)", [4] = "timer1",
        [5] = "timer2 (Wi-Fi)", [6] = "timer3 (clock)", [7] = "RTC", [12] = "keys", [16] = "IPC sync",
        [17] = "FIFO send", [18] = "FIFO recv", [22] = "lid", [23] = "SPI", [24] = "Wi-Fi",
        [32 + 5] = "headphone", [32 + 6] = "I2C", [32 + 8] = "SD", [32 + 9] = "SD data", [32 + 10] = "SDIO",
        [32 + 11] = "SDIO data", [32 + 12] = "AES", [32 + 14] = "mic",
    };
    if (n < 64 && NAMES[n] != NULL)
        return NAMES[n];
    snprintf(buf, 12, n < 32 ? "IRQ %lu" : "AUX %lu", (unsigned long)(n % 32));
    return buf;
}

static void show(const Arm7Watch *w, const char *what)
{
    shown = true;
    consoleDemoInit();
    BG_PALETTE_SUB[0] = 0;
    consoleClear();
    char buf[12];
    printf("DSiRPC: %s\n\n", what);
    printf("A photo of this helps find out\nwhy. Then hold POWER.\n\n");
    printf("ARM7 VBlanks: %lu\n", (unsigned long)w->beats);
    printf("Running now:\n");
    int any = 0;
    for (uint32_t n = 0; n < 64; n++)
    {
        if (w->running[n])
        {
            printf(" %s x%u\n", irq_name(n, buf), w->running[n]);
            any++;
        }
    }
    if (!any)
        printf(" no handler\n");
    printf("Last: %s at %lu\n", irq_name(w->last, buf), (unsigned long)w->last_beat);
    printf("Depth %lu, at most %lu\n", (unsigned long)w->depth, (unsigned long)w->depth_max);
    if (w->stack_low != 0xFFFFFFFF)
        printf("Stack: %lu B free at least\n", (unsigned long)(w->stack_low - w->stack_floor));
    printf("IE %08lX AUX %08lX\n", (unsigned long)w->ie, (unsigned long)w->ie_aux);
    printf("Timers %04X %04X %04X %04X\n", w->timers[0], w->timers[1], w->timers[2], w->timers[3]);
    printf("Music: pattern %u, row %u\n", (unsigned)mmGetPosition(), (unsigned)mmGetPositionRow());
    printf("Started: VBl %lu mus %lu\n Wi-Fi %lu FIFO %lu SDIO %lu\n", (unsigned long)w->started[0],
           (unsigned long)w->started[3], (unsigned long)w->started[5], (unsigned long)w->started[18],
           (unsigned long)(w->started[32 + 10] + w->started[32 + 11]));
}

static void check(void)
{
    if (paused || shown)
        return;
    const Arm7Watch *w = memUncached(&record);
    if (w->stack_floor == 0)
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
    record.stack_low = 0xFFFFFFFF;
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
