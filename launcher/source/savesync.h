// SPDX-License-Identifier: MIT
//
// The save sync: backing the games' saves up to DSiRPC on the PC, and taking
// newer ones from it (DSiRPC's core/saves.py and core/save_session.py are
// the other side and describe the exchange). This part has no screens
// (saveui.c has them), so it also builds on a PC, where the tests run it
// against DSiRPC.
//
// The saves are found through the games: every .nds in the games folder
// (subfolders too), its save next to it in a "saves" folder, in the games
// folder's "saves" folder, next to it, or in TWiLight Menu++'s saves folder,
// as .sav and .sav1 to .sav9 (TWiLight's save slots). A save no game is
// named after (a renamed backup, say) is left alone.
//
// saves.idx (in the launcher's folder) remembers each save as it was at its
// last sync: size, modified time and CRC32. A save whose size and time match
// hasn't changed (stage 1, no reading); only the others are read for their
// CRC (stage 2), which also catches the saves nds-bootstrap only touched (it
// updates a save's time whenever it starts the game).

#ifndef SAVESYNC_H__
#define SAVESYNC_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "sync.h"

#define SAVE_PATH_LEN    256
#define SAVE_NAME_LEN    48
#define SAVE_SOURCE_LEN  33
#define SAVE_MAX_ITEMS   1024
#define SAVE_MAX_SLOT    9
#define SAVE_MAX_VERSIONS 64
#define SAVES_INDEX      "saves.idx"

// What DSiRPC's plan says (core/saves.py's numbers)
typedef enum
{
    SA_IN_SYNC,
    SA_UPLOAD,          // changed here: back it up, and it's what the PC shares
    SA_DOWNLOAD,        // the PC's is newer
    SA_CONFLICT,        // changed on both sides since the last sync
    SA_BACKUP,          // back-up-only mode: changed here, back it up
    SA_EXCLUDED,
    SA_DOWNLOAD_NEW,    // the PC has a save for a game here that has none
    SA_UNKNOWN,         // not in the plan (no DSiRPC answer yet)
} SaveAction;

// How a conflict is settled
typedef enum
{
    SC_ASK,
    SC_KEEP_CONSOLE,
    SC_TAKE_PC,
    SC_SKIP,
} SaveChoice;

typedef struct
{
    char code[5];               // the game code
    uint16_t hcrc;              // the ROM header's CRC (with the code, the game's key)
    uint8_t slot;               // 0: .sav, 1-9: .sav1-.sav9
    char name[SAVE_NAME_LEN];   // the game's file name, without .nds
    char path[SAVE_PATH_LEN];   // the save (or where it would go)
    bool present;               // there's a save file
    bool excluded;              // left out of the sync (Y)
    uint32_t size, crc;         // now
    int32_t mtime;
    uint32_t base;              // CRC at its last sync, 0: never synced
    bool changed;               // crc != base

    // From DSiRPC's plan
    SaveAction action;
    uint32_t pc_size, pc_crc, pc_time;   // the PC's live save (pc_time: seconds since 2000)
    uint8_t versions;           // versions DSiRPC keeps (the live save and the backups)
    char pc_source[SAVE_SOURCE_LEN];     // the console the live save came from, or "External"
    SaveChoice choice;          // a conflict's answer
    bool done;                  // synced in this session
    bool failed;
} SaveItem;

typedef struct
{
    SaveItem *items;            // malloc'd, count of them
    int count;
    int roms;                   // games found
    char index_path[SAVE_PATH_LEN];
    char games_dir[SAVE_PATH_LEN];
} SaveList;

typedef struct
{
    uint8_t mac[6];
    int model;                  // TWiLight's CONSOLE_MODEL
    bool backup_only;
} SaveConsole;

typedef struct
{
    uint8_t version;            // 0: the live save, 1..: the backups, newest first
    uint32_t time, size, crc;
    char source[SAVE_SOURCE_LEN];   // the console it came from, or "External"
} SaveVersion;

typedef struct
{
    int uploaded, downloaded, backed_up, failed;
} SaveCounts;

// Progress for the screen: what (a short line), done of total (bytes, or
// files while scanning).
typedef void (*SaveProgress)(const char *what, uint32_t done, uint32_t total);

// The games and their saves, with stage 1 and 2 against saves.idx. Returns
// the number of saves found, or -1 if out of memory. index_dir: where
// saves.idx is (the launcher's folder).
int saves_scan(SaveList *list, const char *games_dir, const char *index_dir, SaveProgress progress);

void saves_free(SaveList *list);

// At startup: how many saves changed since the last sync (stage 1, and
// stage 2 for what that flags; new saves in the games folder's "saves"
// folder count too, if a game is named after them). -1 if there has never
// been a sync.
int saves_quick_check(const char *games_dir, const char *index_dir);

// Writes saves.idx: every save's state at its last sync, and the exclusions.
bool saves_write_index(const SaveList *list);

// Whether a planned item still has something to do (what the Saves screen
// and the main screen's count go by): a save to back up, a conflict, or a
// newer save on the PC unless backup_only.
bool saves_needs_sync(const SaveItem *item, bool backup_only);

// Sends the list to DSiRPC (found first; *server is filled in) and takes its
// plan: each item's action and the PC's side. Items for saves DSiRPC has but
// this console doesn't (for its games) are added, and the saves it says are
// in sync count as synced (write saves.idx after). 1: done, 0: cancelled,
// -1: failed (msg).
int saves_plan(const SyncJob *job, const SaveConsole *console, SaveList *list,
               struct sockaddr_in *server, char *msg, size_t msgsz);

// Carries out an item's action (a conflict as its choice says; the console's
// save always goes to the PC before it's replaced) and updates saves.idx.
// 1: done, 0: cancelled or nothing to do, -1: failed (msg).
int saves_sync_item(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                    SaveList *list, SaveItem *item, SaveCounts *counts, SaveProgress progress,
                    char *msg, size_t msgsz);

// The versions DSiRPC keeps of a save. Returns how many (up to max), or -1
// (msg).
int saves_versions(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                   const SaveItem *item, SaveVersion *out, int max, char *msg, size_t msgsz);

// Replaces the console's save with a version DSiRPC keeps (the console's
// goes to the PC first); from: the console that version came from, for the
// screen. In sync mode, that version becomes the PC's live save too.
// 1: done, -1: failed (msg).
int saves_restore(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                  SaveList *list, SaveItem *item, uint8_t version, const char *from, SaveCounts *counts,
                  SaveProgress progress, char *msg, size_t msgsz);

// Tells DSiRPC what the sync did (for its notification).
void saves_done(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                const SaveCounts *counts);

// CRC32 (zlib's) of a file. false if it can't be read.
bool saves_file_crc(const char *path, uint32_t *crc, uint32_t *size);

#endif // SAVESYNC_H__
