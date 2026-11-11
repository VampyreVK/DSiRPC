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
#include <stdint.h>

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

// What DSiRPC said of a game's file at the last sync (games.idx's <ra>)
enum
{
    PICKER_RA_UNKNOWN,          // not asked yet (or DSiRPC couldn't ask)
    PICKER_RA_SET,              // RetroAchievements has a set for it
    PICKER_RA_NOT_THIS_ROM,     // it has the game, but no set for this file (another region, revision or a hack)
    PICKER_RA_NO_GAME,          // it doesn't have the game (or the file can't be hashed its way)
};

// The first-time setup at boot: every game's RetroAchievements hash, once
typedef struct
{
    const char *games_dir;
    const char *index_dir;
    // As it goes: game (0-based) of games, its name, and its bytes hashed of total
    void (*progress)(int game, int games, const char *title, uint32_t done, uint32_t total, void *ctx);
    bool (*cancelled)(void);    // true to stop (the rest are hashed next time); may be NULL
    void *ctx;
} PickerSetup;

// Reads and hashes the games that are new or changed since games.idx (by
// file name, size and time), and saves it. Returns how many it went through
// (0: nothing new, and nothing was shown through progress), with how many
// were hashed in *hashed (the rest couldn't be: not tried again).
int picker_setup(const PickerSetup *setup, int *hashed);

// The games' hashes for the sync with DSiRPC, from games.idx (every file
// hashed, with a game code or not): malloc'd records of PICKER_ROM_RECORD
// bytes (code[4], four zero bytes for none, md5[16], flags u8 with
// PICKER_ROM_STARTED for the file at `started` (may be NULL), the name's
// length u8, 2 bytes 0), each followed by the file's name (without its
// folder or ".nds", PICKER_ROM_NAME_MAX at most). Returns how many (*out
// NULL for none), their bytes in *size.
#define PICKER_ROM_RECORD    24
#define PICKER_ROM_STARTED   1
#define PICKER_ROM_NAME_MAX  63
int picker_rom_hashes(const char *index_dir, const char *started, uint8_t **out, size_t *size);

// What DSiRPC said of the hashes: n PICKER_STATUS_RECORD-byte records
// (md5[16], PICKER_RA_* u8, 3 bytes 0), kept in games.idx. A game code
// whose every file has no set loses its set in sets_dir. Returns how many
// sets were removed.
#define PICKER_STATUS_RECORD 20
int picker_store_status(const char *index_dir, const char *sets_dir, const uint8_t *status, int n);

#endif // PICKER_H__
