// SPDX-License-Identifier: MIT
//
// The menu music (see music.h). maxmod's soundbank (soundbank.bin, built by
// mmutil from audio/) is part of the launcher; a song is loaded when it
// starts and unloaded when another one replaces it.

#include <nds.h>
#include <maxmod9.h>

#include "music.h"
#include "soundbank.h"
#include "soundbank_bin.h"

// The songs' level against the menu sounds (1024 is maxmod's full level)
#define VOLUME      640
#define FADE_FRAMES 12

static const mm_word SONGS[MUSIC_CHOICES] = { [MUSIC_BRIGHT] = MOD_BRIGHT, [MUSIC_SUBTLE] = MOD_SUBTLE };

static bool ready;
static MusicChoice playing = MUSIC_OFF;

void music_init(void)
{
    ready = mmInitDefaultMem((mm_addr)soundbank_bin);
    if (ready)
        mmLockChannels(MUSIC_UI_CHANNELS);
}

static void halt(void)
{
    mmStop();
    mmUnload(SONGS[playing]);
    playing = MUSIC_OFF;
}

void music_play(MusicChoice choice)
{
    if (!ready || choice == playing || choice >= MUSIC_CHOICES)
        return;
    if (playing != MUSIC_OFF)
        halt();
    if (choice == MUSIC_OFF)
        return;
    mmLoad(SONGS[choice]);
    mmSetModuleVolume(VOLUME);
    mmStart(SONGS[choice], MM_PLAY_LOOP);
    playing = choice;
}

void music_stop(void)
{
    if (!ready || playing == MUSIC_OFF)
        return;
    for (int f = FADE_FRAMES - 1; f > 0; f--)
    {
        mmSetModuleVolume(VOLUME * f / FADE_FRAMES);
        cothread_yield_irq(IRQ_VBLANK);
    }
    halt();
}

bool music_on(void)
{
    return playing != MUSIC_OFF;
}
