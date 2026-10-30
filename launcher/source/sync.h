// SPDX-License-Identifier: MIT
//
// Offline play: the launcher's half of the sync with DSiRPC. DSiRPC does all
// the work (finding sets, talking to RetroAchievements); the launcher only
// carries files. The formats are described in DSiRPC's core/offline.py.

#ifndef SYNC_H__
#define SYNC_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SYNC_PORT        4245
// In the launcher's folder, where nds-bootstrap looks for them (beside itself)
#define UNLOCKS_FILE     "RPCUNLK.BIN"       // unlocks waiting for DSiRPC
#define STAGED_SET_FILE  "RPCSET.BIN"        // the started game's set
#define SETS_FOLDER      "sets"              // in the launcher's folder: CODE.DRS
// An unlock file slot with the playtime of one start of a game (the game's
// side writes it, rpcprobe/probe_ach.c), not an unlock: stats.c adds it up
#define PLAYTIME_ID      0xFFFFFFFFu

typedef struct
{
    const char *sets_dir;       // where the sets are kept ("sd:/roms/nds/DSiRPC/sets")
    const char *unlocks_path;   // UNLOCKS_FILE in the launcher's folder
    char game[5];               // the game being started ("CPUE"), or ""
    int console_model;          // console_model(), so DSiRPC can say "3DS"
    uint32_t server_addr;       // DSiRPC's IPv4 address (network order), or 0
                                // to look for it with a broadcast
    uint16_t port;              // DSiRPC's port, 0 for SYNC_PORT (tests use another)
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

// Copies the game's set to dest (STAGED_SET_FILE), or removes dest if there
// isn't one, so the in-game side never sees another game's set. Returns
// true if there was a set.
bool stage_set(const char *sets_dir, const char *game, const char *dest);

// The 4-letter game code from an .nds file's header ("" if unreadable).
void read_game_code(const char *nds_path, char code[5]);

// Where DSiRPC was last found (network order), or 0, and its TCP port: set
// by each search (the syncs, the save sync), even when DSiRPC is from
// another release, and cleared when one finds nothing.
extern uint32_t sync_found_addr;
extern uint16_t sync_found_port;

// Waits for the next frame. Every 5 s, it also tells DSiRPC (if it was
// found) that the launcher's still there, so DSiRPC can tell when it's gone:
// the launcher's screens wait with this while they wait for a key.
void sync_frame(void);

// Tells DSiRPC the launcher's leaving (SELECT, or exiting connected), and
// stops the "still there"s.
void sync_bye(void);

// The network side, shared with the save sync (savesync.c). Each returns 1
// when done, 0 if the job was cancelled (B), -1 if it failed (msg says why).
struct sockaddr_in;
int sync_find(const SyncJob *job, struct sockaddr_in *server, char *msg, size_t msgsz);
int sync_open(const SyncJob *job, const struct sockaddr_in *server, int *sock, char *msg, size_t msgsz);
int sync_send(const SyncJob *job, int sock, const void *data, size_t len, char *msg, size_t msgsz);
int sync_recv(const SyncJob *job, int sock, void *data, size_t len, char *msg, size_t msgsz);
void sync_close(int sock);

#endif // SYNC_H__
