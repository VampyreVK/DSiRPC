// SPDX-License-Identifier: MIT
//
// The menu music (Music in the launcher's settings, in the modern look): two
// songs made on a Dirtywave M8 (music/*.m8s), turned into XM modules
// (audio/*.xm, by tools/make_music.py) and played by maxmod on the ARM7, so
// they keep time whatever the launcher is busy with. The menu sounds keep
// channels 12-15 to themselves (MUSIC_UI_CHANNELS); the songs use the rest.

#ifndef MUSIC_H__
#define MUSIC_H__

typedef enum
{
    MUSIC_OFF,
    MUSIC_BRIGHT,               // the default: an airy Eb major loop
    MUSIC_SUBTLE,               // a quiet lounge loop
    MUSIC_CHOICES,
} MusicChoice;

#define MUSIC_UI_FIRST_CHANNEL  12
#define MUSIC_UI_CHANNELS       0xF000

// Once, after soundEnable(): starts maxmod with the songs, and keeps the
// menu sounds' channels away from it.
void music_init(void);

// Plays that song (looping), or stops for MUSIC_OFF; the song already
// playing carries on.
void music_play(MusicChoice choice);

// Fades the song out over a few frames and stops it (before starting a
// game, or leaving).
void music_stop(void);

#endif // MUSIC_H__
