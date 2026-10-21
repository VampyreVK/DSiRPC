// SPDX-License-Identifier: MIT
//
// The launcher's settings (see settings.h). The file is small and only ours,
// so it's written whole each time:
//
//   [LAUNCHER]
//   DSIRPC_IP = 192.168.1.20      (empty: look for DSiRPC with a broadcast)
//   SAVE_MODE = sync              (or backup: never take a save from the PC)
//   LAST_GAME = sd:/roms/nds/Pokemon Black.nds   (START in the game picker)

#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "bootstrap_ini.h"
#include "settings.h"

#define SECTION "LAUNCHER"

// "a.b.c.d", each 0-255 and nothing else. Returns the address in network
// order (a first in memory), or 0 if it isn't one (or is 0.0.0.0).
static uint32_t parse_ip(const char *text)
{
    uint32_t addr = 0;
    const char *p = text;
    for (int i = 0; i < 4; i++)
    {
        if (*p < '0' || *p > '9')
            return 0;
        int n = 0, digits = 0;
        while (*p >= '0' && *p <= '9' && digits < 4)
        {
            n = n * 10 + (*p++ - '0');
            digits++;
        }
        if (n > 255 || digits > 3 || (i < 3 && *p++ != '.'))
            return 0;
        addr |= (uint32_t)n << (8 * i);
    }
    return *p == '\0' ? addr : 0;
}

static bool valid_ip(const char *text)
{
    uint32_t a = parse_ip(text);
    return a != 0 && a != 0xFFFFFFFF;
}

void settings_load(const char *path, LauncherSettings *s)
{
    memset(s, 0, sizeof(*s));
    char value[16];
    if (ini_get(path, SECTION, "DSIRPC_IP", value, sizeof(value)) == 1 && valid_ip(value))
        snprintf(s->dsirpc_ip, sizeof(s->dsirpc_ip), "%s", value);
    if (ini_get(path, SECTION, "SAVE_MODE", value, sizeof(value)) == 1)
        s->backup_only = strcasecmp(value, "backup") == 0;
    ini_get(path, SECTION, "LAST_GAME", s->last_game, sizeof(s->last_game));
}

bool settings_save(const char *path, const LauncherSettings *s)
{
    FILE *f = fopen(path, "wb");
    if (f == NULL)
        return false;
    fprintf(f, "; The DSiRPC launcher's settings (L+R in the launcher changes them)\r\n"
               "[" SECTION "]\r\n"
               "; DSiRPC's IPv4 address, or empty to look for it on the network\r\n"
               "DSIRPC_IP = %s\r\n"
               "; The save sync: sync (back up and take newer saves from the PC)\r\n"
               "; or backup (only back up)\r\n"
               "SAVE_MODE = %s\r\n"
               "; The game last started from the launcher (START in the game picker)\r\n"
               "LAST_GAME = %s\r\n",
            s->dsirpc_ip, s->backup_only ? "backup" : "sync", s->last_game);
    return fclose(f) == 0;
}

uint32_t settings_server_addr(const LauncherSettings *s)
{
    return valid_ip(s->dsirpc_ip) ? parse_ip(s->dsirpc_ip) : 0;
}

// ---------------------------------------------------------------------------
// The screen

#ifdef __NDS__
#include <nds.h>

#include "sync.h"

enum { ROW_FIND, ROW_ADDRESS, ROW_SAVES, ROWS };

static void parse_octets(const char *ip, int octet[4])
{
    unsigned a = 0, b = 0, c = 0, d = 0;
    if (sscanf(ip, "%u.%u.%u.%u", &a, &b, &c, &d) != 4)
        a = 192, b = 168, c = 1, d = 2;
    octet[0] = a & 255;
    octet[1] = b & 255;
    octet[2] = c & 255;
    octet[3] = d & 255;
}

static void draw(const LauncherSettings *s, int row, bool manual, const int octet[4], int editing)
{
    consoleClear();
    printf("Settings\n");
    printf("-------------------------------\n");
    printf("%c Find DSiRPC: %s\n", row == ROW_FIND ? '>' : ' ', manual ? "at this address" : "automatically");
    if (manual)
    {
        printf("%c Address:     ", row == ROW_ADDRESS ? '>' : ' ');
        for (int i = 0; i < 4; i++)
        {
            if (editing == i)
                printf("\x1b[33;1m%d\x1b[39;0m", octet[i]);
            else
                printf("%d", octet[i]);
            if (i < 3)
                printf(".");
        }
        printf("\n");
    }
    else
    {
        printf("\x1b[30;1m%c Address:     (looked for)\x1b[39;0m\n", row == ROW_ADDRESS ? '>' : ' ');
    }
    printf("%c Saves:       %s\n", row == ROW_SAVES ? '>' : ' ', s->backup_only ? "back up only" : "back up and sync");
    printf("-------------------------------\n");
    if (row == ROW_FIND)
        printf("How the launcher finds DSiRPC.\nAutomatically works on most\nnetworks; use an address if it\nisn't found.\n");
    else if (row == ROW_ADDRESS)
        printf("The PC's IP address. The\nlauncher shows it when it\nfinds DSiRPC (DSiRPC: ...).\n");
    else
        printf("Back up and sync: newer saves\nfrom the PC come here too.\nBack up only: saves only go to\nthe PC, so each console can\nkeep its own.\n");
    printf("\x1b[21;0H-------------------------------\n");
    // (no newline after the last row: it would scroll the screen)
    if (editing >= 0)
        printf("Left/Right: move  Up/Down: +/-\nA or B: done");
    else
        printf("Up/Down: choose  A: change\nB: save and go back");
}

void settings_screen(const char *path, LauncherSettings *s, const char *current_ip)
{
    LauncherSettings before = *s;
    int octet[4];
    bool manual = s->dsirpc_ip[0] != '\0';
    parse_octets(manual ? s->dsirpc_ip : current_ip, octet);
    if (!manual)
        octet[3] = 2;   // a guess on the console's own network
    int row = ROW_FIND, editing = -1;
    keysSetRepeat(15, 4);

    while (1)
    {
        draw(s, row, manual, octet, editing);
        u32 down;
        do
        {
            sync_frame();
            scanKeys();
            down = keysDownRepeat();
        } while (down == 0);

        if (editing >= 0)
        {
            if (down & KEY_LEFT)
                editing = (editing + 3) % 4;
            if (down & KEY_RIGHT)
                editing = (editing + 1) % 4;
            if (down & KEY_UP)
                octet[editing] = (octet[editing] + 1) & 255;
            if (down & KEY_DOWN)
                octet[editing] = (octet[editing] + 255) & 255;
            if (down & (KEY_A | KEY_B))
                editing = -1;
            continue;
        }
        if (down & KEY_UP)
            row = (row + ROWS - 1) % ROWS;
        if (down & KEY_DOWN)
            row = (row + 1) % ROWS;
        if (down & (KEY_A | KEY_LEFT | KEY_RIGHT))
        {
            if (row == ROW_FIND)
                manual = !manual;
            else if (row == ROW_ADDRESS && manual)
                editing = 3;
            else if (row == ROW_SAVES)
                s->backup_only = !s->backup_only;
        }
        if (down & KEY_B)
            break;
    }

    if (manual)
        snprintf(s->dsirpc_ip, sizeof(s->dsirpc_ip), "%d.%d.%d.%d", octet[0], octet[1], octet[2], octet[3]);
    else
        s->dsirpc_ip[0] = '\0';
    if (memcmp(&before, s, sizeof(before)) != 0 && !settings_save(path, s))
    {
        consoleClear();
        printf("Can't save the settings\n(is the SD card locked?)\n\nPress A\n");
        do
        {
            cothread_yield_irq(IRQ_VBLANK);
            scanKeys();
        } while (!(keysDown() & (KEY_A | KEY_B)));
    }
}
#endif
