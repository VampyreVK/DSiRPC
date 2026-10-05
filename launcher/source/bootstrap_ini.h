// SPDX-License-Identifier: MIT
//
// Pointing nds-bootstrap at the game picked in the launcher, through the
// ini TWiLight Menu++ writes for it (sd:/_nds/nds-bootstrap.ini).

#ifndef BOOTSTRAP_INI_H__
#define BOOTSTRAP_INI_H__

#include <stdbool.h>
#include <stddef.h>

#define BOOTSTRAP_INI_PATH   "sd:/_nds/nds-bootstrap.ini"
#define BOOTSTRAP_SECTION    "NDS-BOOTSTRAP"

// Reads `key` from `section` of an ini file. Returns 1 if found (value in
// out), 0 if not, -1 if the file can't be read.
int ini_get(const char *path, const char *section, const char *key, char *out, size_t outsz);

// Sets keys in `section` of an ini file, keeping everything else (order,
// comments, line endings). Keys that aren't there yet are added at the end
// of the section. Returns 0 on success, -1 on failure.
int ini_set(const char *path, const char *section, const char *const *keys,
            const char *const *values, int count);

// Where the game's save file is, the way TWiLight Menu++ names it: next to
// it, in a "saves" folder next to it, or in TWiLight's own saves folder, as
// .sav or (per-game save slot) .sav1 to .sav9. prev_nds and prev_sav are the
// last game's paths from the ini, which show which of those places TWiLight
// is set to use. Returns true with the path of an existing save in out.
bool find_save(const char *game, const char *prev_nds, const char *prev_sav,
               char *out, size_t outsz);

// Makes nds-bootstrap boot `game`: if the ini already names it, nothing
// changes. Otherwise NDS_PATH and SAV_PATH are set, the last game's
// per-game values (manual, donor SDK, MPU patch) are reset, and its cheat
// files are removed (TWiLight writes new ones for each game it launches).
// Returns 0 on success, or -1 with a message for the screen in msg.
int bootstrap_ini_prepare(const char *game, char *msg, size_t msgsz);

#endif // BOOTSTRAP_INI_H__
