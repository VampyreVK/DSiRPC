// SPDX-License-Identifier: MIT
//
// Offline play: the launcher's half of the sync with DSiRPC. DSiRPC does all
// the work (finding sets, talking to RetroAchievements); the launcher only
// carries files. The formats are described in DSiRPC's core/offline.py.

#ifndef SYNC_H__
#define SYNC_H__

#include <stdbool.h>
#include <stddef.h>

#define SYNC_PORT        4245
#define UNLOCKS_PATH     "sd:/RPCUNLK.BIN"   // unlocks waiting for DSiRPC
#define STAGED_SET_PATH  "sd:/RPCSET.BIN"    // the started game's set
#define SETS_FOLDER      "sets"              // in the launcher's folder: CODE.DRS

typedef struct
{
    const char *sets_dir;       // where the sets are kept ("sd:/DSiRPC/sets")
    const char *unlocks_path;   // UNLOCKS_PATH
    char game[5];               // the game being started ("CPUE"), or ""
    void (*say)(const char *text);   // progress for the screen (may be NULL)
    bool (*cancelled)(void);         // true to stop waiting (may be NULL)
} SyncJob;

typedef struct
{
    int unlocks_sent;           // unlocks DSiRPC took (the file was cleared)
    int sets_received;
    char server[20];            // DSiRPC's IP
} SyncResult;

// Makes sure the unlock file exists with the right size and header, so the
// in-game side never has to make it. Returns how many unlocks wait in it,
// or -1 if it can't be made.
int unlocks_prepare(const char *path);

// Looks for DSiRPC on the network (1.5 s) and, if it answers, hands over the
// waiting unlocks and saves the sets it sends. Returns 1 if it synced (msg
// may still hold a warning, or ""), 0 if DSiRPC didn't answer or the job was
// cancelled, -1 if something failed. msg always says what happened, except
// after a clean sync.
int sync_with_dsirpc(const SyncJob *job, SyncResult *result, char *msg, size_t msgsz);

// Copies the game's set to dest (STAGED_SET_PATH), or removes dest if there
// isn't one, so the in-game side never sees another game's set. Returns
// true if there was a set.
bool stage_set(const char *sets_dir, const char *game, const char *dest);

// The 4-letter game code from an .nds file's header ("" if unreadable).
void read_game_code(const char *nds_path, char code[5]);

#endif // SYNC_H__
