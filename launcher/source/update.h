// SPDX-License-Identifier: MIT
//
// Updating the launcher and our nds-bootstrap build from DSiRPC on the PC, so
// a new build doesn't need the SD card taken out. DSiRPC offers the files
// that came with it (core/console_update.py, which describes the exchange);
// as the launcher starts, it asks, and when a file on the SD card differs it
// offers the update: A downloads each file next to the old one, checks it,
// turns the Wi-Fi off and swaps the files in, then the launcher exits to be
// started again. Auto-updates in the launcher's settings (L+R) turns the
// asking off, "Console updates" in DSiRPC's tray menu the offering.
//
// The part without screens also builds on a PC, where the tests run it
// against DSiRPC.

#ifndef UPDATE_H__
#define UPDATE_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "sync.h"

#define UPDATE_INDEX      "update.idx"   // in the launcher's folder: the files' CRCs
#define UPDATE_MAX_FILES  4
#define UPDATE_PATH_LEN   512
#define UPDATE_LABEL_LEN  33

// DSiRPC's numbers for the files
enum
{
    UPDATE_LAUNCHER = 1,
    UPDATE_BOOTSTRAP = 2,
};

typedef struct
{
    uint8_t id;                     // UPDATE_LAUNCHER or UPDATE_BOOTSTRAP
    char path[UPDATE_PATH_LEN];     // the file on the SD card, or where it goes
    uint32_t size, crc;             // DSiRPC's
    bool needed;                    // the SD card's differs, or there isn't one
    bool downloaded;                // path + ".tmp" holds DSiRPC's, checked
} UpdateFile;

typedef struct
{
    UpdateFile files[UPDATE_MAX_FILES];   // what DSiRPC has
    int count;
    int needed;                     // how many of them to update
    uint32_t total;                 // their bytes
    char label[UPDATE_LABEL_LEN];   // DSiRPC's version ("v0.9.0", "dev-abc1234")
    char index_path[UPDATE_PATH_LEN];
} UpdatePlan;

// Progress for the screen: what ("the launcher"), done of total bytes.
typedef void (*UpdateProgress)(const char *what, uint32_t done, uint32_t total);

// "the launcher" or "nds-bootstrap"
const char *update_file_name(uint8_t id);

// Asks DSiRPC (at server) which console files it has and compares them with
// the SD card's: the launcher at launcher_path ("" if it can't be found:
// left alone), nds-bootstrap at bootstrap_path (where it is, or where it
// goes). index_dir: the launcher's folder (update.idx). 1: something to
// update (plan says what), 0: nothing (or console updates are off in
// DSiRPC, or it's from before them, or B), -1: failed (msg).
int update_check(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                 const char *launcher_path, const char *bootstrap_path, const char *index_dir,
                 UpdatePlan *plan, char *msg, size_t msgsz);

// Downloads each file the plan needs to its path + ".tmp": its size, CRC32
// and .nds header are checked, then its CRC32 again as read back from the SD
// card. 1: all there, 0: cancelled (B), -1: failed (msg). Unless 1, no
// .tmp file is left and nothing else changed.
int update_download(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                    UpdatePlan *plan, UpdateProgress progress, char *msg, size_t msgsz);

// Swaps the downloaded files in: each old file becomes its name + ".bak" and
// the .tmp takes its name; if any of it fails, every file goes back as it
// was. Then the .bak files go and update.idx is written. true if done (msg
// says what went wrong if not).
bool update_install(UpdatePlan *plan, char *msg, size_t msgsz);

// Removes the plan's .tmp files.
void update_discard(UpdatePlan *plan);

#ifdef __NDS__
typedef enum
{
    UPDATE_NONE,        // nothing to update: nothing was shown
    UPDATE_SHOWN,       // not now (B), or the download didn't work: redraw
    UPDATE_EXIT,        // the Wi-Fi is off (updated, or the swap failed): exit
} UpdateOutcome;

typedef struct
{
    const char *launcher_path;      // this launcher's file, or ""
    const char *bootstrap_path;     // nds-bootstrap's, or where it would go
    const char *index_dir;          // the launcher's folder
    const uint8_t *mac;
    int console_model;
    uint32_t server_addr;           // DSiRPC, as the sync found it (network order)
    uint16_t server_port;           // its TCP port
} UpdateUi;

// After the launcher's first sync: asks DSiRPC and, if a file differs, offers
// the update (A: update, B: not now), downloads, swaps and says how it went.
UpdateOutcome update_offer(const UpdateUi *ui);
#endif

#endif // UPDATE_H__
