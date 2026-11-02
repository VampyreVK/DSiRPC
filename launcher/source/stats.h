// SPDX-License-Identifier: MIT
//
// DSiRPC playtime, kept with DSiRPC on the PC. DSiRPC counts how long each
// game runs while it's watching (core/playtime.py, which describes the
// exchange); after its first sync, the launcher sends it the numbers it has
// and gets DSiRPC's, with the PC's name and whether it's signed in to
// RetroAchievements and connected to Discord. Each side keeps the higher of
// each number, so a game played with another PC still adds up. The
// launcher keeps them in stats.idx in its folder, so the modern look's game
// picker and achievement list have them offline too. Offline play counts
// too: the game's side keeps each start's playtime in the unlock file
// (PLAYTIME_ID), and the launcher adds it to stats.idx as it starts.
//
// The part without screens, so it also builds on a PC, where the tests run
// it against DSiRPC.

#ifndef STATS_H__
#define STATS_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "sync.h"

#define STATS_INDEX     "stats.idx"
#define STATS_MAX       1024
#define STATS_TEXT_LEN  33

typedef struct
{
    char code[5];
    uint32_t seconds;           // played through DSiRPC (online, or offline from the launcher)
    uint32_t last;              // when it last played, seconds since 2000 (the PC's local time)
} GameStats;

typedef struct
{
    GameStats *games;           // malloc'd, count of them
    int count;
    char pc[STATS_TEXT_LEN];    // the PC's name
    char ra_user[STATS_TEXT_LEN];   // who's signed in to RetroAchievements, or ""
    bool discord;               // Discord connected
} StatsList;

// Swaps numbers with DSiRPC (at server) and writes the higher of each to
// stats.idx in index_dir (the launcher's folder). 1: done, 0: DSiRPC is from
// before playtimes (or B), -1: failed (msg).
int stats_fetch(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                const char *index_dir, char *msg, size_t msgsz);

// Adds each start's playtime the game's side left in the unlock file
// (unlocks_path) to stats.idx, and clears those slots (first, so none is
// ever added twice). Returns how many were added, -1 if the files couldn't
// be written.
int stats_add_played(const char *index_dir, const char *unlocks_path);

// Reads stats.idx (nothing in it if there isn't one). false only if out of
// memory.
bool stats_load(const char *index_dir, StatsList *out);
void stats_free(StatsList *s);

// A game's numbers, or NULL
const GameStats *stats_find(const StatsList *s, const char *code);

#endif // STATS_H__
