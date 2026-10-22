// SPDX-License-Identifier: MIT
//
// The save sync's screens (X in the launcher; savesync.c does the work).

#ifndef SAVEUI_H__
#define SAVEUI_H__

#include <stdbool.h>
#include <stdint.h>

#include "settings.h"

typedef struct
{
    const char *games_dir;          // where the games are ("sd:/roms/nds")
    const char *index_dir;          // the launcher's folder (saves.idx)
    const LauncherSettings *settings;
    const uint8_t *mac;             // the console's MAC address (6 bytes)
    int console_model;              // TWiLight's CONSOLE_MODEL
} SaveUi;

// Finds the saves, asks DSiRPC for its plan and shows the list: Sync all on
// top, then each save. Returns when it's left with B, or after Sync all's
// summary (back to the launcher's main screen either way).
void save_sync_screen(const SaveUi *ui);

#endif // SAVEUI_H__
