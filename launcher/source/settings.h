// SPDX-License-Identifier: MIT
//
// The launcher's own settings (L+R in the launcher), in launcher.ini next to
// it: where to find DSiRPC, and what the save sync does. It also remembers
// the game last started from the launcher (START in the game picker).

#ifndef SETTINGS_H__
#define SETTINGS_H__

#include <stdbool.h>
#include <stdint.h>

#define SETTINGS_FILE "launcher.ini"
#define SETTINGS_PATH_LEN 512

typedef struct
{
    char dsirpc_ip[16];     // DSiRPC's IPv4 address, or "" to look for it
    bool backup_only;       // the save sync only backs saves up, never takes any
    char last_game[SETTINGS_PATH_LEN];  // the game last started from here, or ""
} LauncherSettings;

// Reads the settings (the defaults for anything missing: look for DSiRPC,
// back up and sync, no last game).
void settings_load(const char *path, LauncherSettings *s);

// Writes them all. Returns false if the file can't be written.
bool settings_save(const char *path, const LauncherSettings *s);

// The address to ask for DSiRPC at (network order), or 0 to broadcast.
uint32_t settings_server_addr(const LauncherSettings *s);

#ifdef __NDS__
// The settings screen. Returns when B is pressed, with the settings saved if
// they changed. current_ip: the console's address, to start a new DSiRPC
// address from.
void settings_screen(const char *path, LauncherSettings *s, const char *current_ip);
#endif

#endif // SETTINGS_H__
