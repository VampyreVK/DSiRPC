// SPDX-License-Identifier: MIT
//
// The top screen: DSiRPC's pixel DSi, as on the desktop app's waiting
// screen, with its Wi-Fi sign lighting up arc by arc while the launcher
// connects and turning green once it's connected.
//
// In the modern look (top_modern()), the bar has a status chip and the
// battery instead of the signal meter, the DSi is smaller with a note under
// it, and the game picker and the save sync show the picked game's or
// save's details in its place.

#ifndef TOPSCREEN_H__
#define TOPSCREEN_H__

#include <stdbool.h>
#include <stdint.h>

#include "ui.h"

typedef enum
{
    TOP_CONNECTING,     // the Wi-Fi sign's arcs light up one by one
    TOP_CONNECTED,      // green
    TOP_FAILED,         // red: it couldn't connect
    TOP_OFFLINE,        // dark: playing offline
} TopState;

// A save's state, for its banner's color
typedef enum
{
    TONE_GREEN,
    TONE_CYAN,
    TONE_AMBER,
    TONE_RED,
    TONE_GREY,
} TopTone;

// The game picker's game
typedef struct
{
    const UiBanner *icon;       // or NULL
    const char *title;
    const char *publisher;      // or ""
    const char *code;           // "CPUE", or ""
    int version;                // the ROM's revision
    int earned, total;          // achievements (total 0: no set on the SD card)
    uint32_t playtime;          // seconds DSiRPC saw it played (0: none)
    uint32_t last_played;       // seconds since 2000 (0: never)
    uint32_t now;               // the console's clock, seconds since 2000
    bool favorite;
} TopGame;

// The save sync's save
typedef struct
{
    const char *name;
    const char *size;           // "512 KB"
    const char *status;         // what the sync does with it
    TopTone tone;
    const char *console;        // "DSi" or "3DS"
    const char *here;           // when this console's was saved, or NULL
    const char *there;          // when the PC's was, or NULL
    const char *from;           // the console the PC's came from, or ""
    int versions;               // the versions DSiRPC keeps (live and backups)
} TopSave;

// An achievement, in the game picker's list
typedef struct
{
    const char *game;
    const char *title;
    const char *description;
    int points;
    int state;                  // 0 to earn, 1 earned, 2 unlocked here (waiting for DSiRPC)
    uint32_t when;              // when it was earned, seconds since 2000 (0: not known)
} TopCheevo;

// Draws it and starts the animation (a cothread that runs whenever the
// launcher waits for a frame). Call once, after consoleDemoInit().
void top_init(void);

void top_set(TopState state);

// The animation's frame (60ths of a second since it started): the drifting
// diamonds and the Wi-Fi sign. Its cothread calls it every frame.
void top_animate(unsigned frame);

// The modern look on or off (the classic look's screen when off)
void top_modern(bool on);

// The modern look's note under the DSi: two lines (NULL or "" for none)
void top_note(const char *line1, const char *line2);

// What the modern look shows: the DSi (and its note), a game, a save
void top_dsi(void);
void top_game(const TopGame *game);
void top_save(const TopSave *save);
void top_cheevo(const TopCheevo *cheevo);

#endif // TOPSCREEN_H__
