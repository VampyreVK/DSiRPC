// SPDX-License-Identifier: MIT
//
// The modern look's game picker (the classic look's is browser.c): every
// game in the games folder (subfolders too) with its banner icon and name,
// in the order Y and L/R pick (the games last started first, by name, or the
// favorites first), its achievements (X: the list, from its set on the SD
// card) and, on the top screen, its details and playtime.
//
// games.idx (in the launcher's folder) keeps each game's name, publisher and
// code as read from its banner, by the file's size and time, so only new or
// changed games are read, and the favorites and when each game was last
// started from the launcher.

#ifndef PICKER_H__
#define PICKER_H__

#include <stdbool.h>
#include <stddef.h>

#include "settings.h"
#include "ui.h"

#define PICKER_INDEX  "games.idx"

// The orders (settings.h's game_sort, launcher.ini's GAME_SORT)
enum
{
    SORT_RECENT,
    SORT_NAME,
    SORT_FAVORITES,
    SORTS,
};

typedef struct
{
    const char *games_dir;          // where the games are
    const char *index_dir;          // the launcher's folder (games.idx, stats.idx)
    const char *sets_dir;           // the achievement sets
    const char *unlocks_path;       // RPCUNLK.BIN: unlocks waiting for DSiRPC
    const char *last;               // the game last started (START), or NULL
    LauncherSettings *settings;     // its game_sort, saved when it changes
    const char *settings_path;
} PickerUi;

// Lets the user pick a game. true with its path in out, false if they backed
// out (B).
bool pick_game(const PickerUi *ui, char *out, size_t outsz);

// Notes in games.idx that a game is being started (for the Recent order).
void picker_started(const char *index_dir, const char *path);

// A game's banner: its icon, and its name and publisher in English (either
// may be NULL). false if it has none.
bool picker_banner(const char *path, UiBanner *icon, char *title, size_t tsz, char *publisher, size_t psz);

#endif // PICKER_H__
