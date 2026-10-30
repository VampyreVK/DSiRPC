// SPDX-License-Identifier: MIT
//
// The launcher's settings (see settings.h). The file is small and only ours,
// so it's written whole each time:
//
//   [LAUNCHER]
//   DSIRPC_IP = 192.168.1.20      (empty: look for DSiRPC with a broadcast)
//   SAVE_MODE = sync              (or backup: never take a save from the PC)
//   AUTO_UPDATE = on              (or off: never ask DSiRPC for updates)
//   LOOK = modern                 (or classic: the text screens)
//   SOUNDS = on                   (or off: the modern look's menu sounds)
//   MUSIC = bright                (or subtle, off: the modern look's menu music)
//   GAME_SORT = recent            (or name, favorites: the modern game picker)
//   LAST_GAME = sd:/roms/nds/Pokemon Black.nds   (START in the game picker)

#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "bootstrap_ini.h"
#include "music.h"
#include "settings.h"

#define SECTION "LAUNCHER"

// GAME_SORT's words, in picker.h's order
static const char *const SORTS[] = { "recent", "name", "favorites" };
#define N_SORTS (sizeof(SORTS) / sizeof(SORTS[0]))

// MUSIC's words, in music.h's order
static const char *const MUSICS[MUSIC_CHOICES] = { "off", "bright", "subtle" };

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

// On unless it says off (or no, or 0)
static bool switched_on(const char *path, const char *key)
{
    char value[16];
    return ini_get(path, SECTION, key, value, sizeof(value)) != 1 ||
           !(strcasecmp(value, "off") == 0 || strcasecmp(value, "no") == 0 || strcmp(value, "0") == 0);
}

void settings_load(const char *path, LauncherSettings *s)
{
    memset(s, 0, sizeof(*s));
    char value[16];
    if (ini_get(path, SECTION, "DSIRPC_IP", value, sizeof(value)) == 1 && valid_ip(value))
        snprintf(s->dsirpc_ip, sizeof(s->dsirpc_ip), "%s", value);
    if (ini_get(path, SECTION, "SAVE_MODE", value, sizeof(value)) == 1)
        s->backup_only = strcasecmp(value, "backup") == 0;
    s->auto_update = switched_on(path, "AUTO_UPDATE");
    if (ini_get(path, SECTION, "LOOK", value, sizeof(value)) == 1)
        s->classic_look = strcasecmp(value, "classic") == 0;
    s->sounds = switched_on(path, "SOUNDS");
    s->music = MUSIC_BRIGHT;
    if (ini_get(path, SECTION, "MUSIC", value, sizeof(value)) == 1)
    {
        for (int i = 0; i < MUSIC_CHOICES; i++)
        {
            if (strcasecmp(value, MUSICS[i]) == 0)
                s->music = (uint8_t)i;
        }
    }
    if (ini_get(path, SECTION, "GAME_SORT", value, sizeof(value)) == 1)
    {
        for (size_t i = 0; i < N_SORTS; i++)
        {
            if (strcasecmp(value, SORTS[i]) == 0)
                s->game_sort = (uint8_t)i;
        }
    }
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
               "; When DSiRPC on the PC has other versions of the launcher or\r\n"
               "; nds-bootstrap, offer them as the launcher starts: on or off\r\n"
               "AUTO_UPDATE = %s\r\n"
               "; How the launcher looks: modern, or classic (the text screens)\r\n"
               "LOOK = %s\r\n"
               "; The modern look's menu sounds: on or off\r\n"
               "SOUNDS = %s\r\n"
               "; The modern look's menu music: bright, subtle or off\r\n"
               "MUSIC = %s\r\n"
               "; The modern game picker's order: recent, name or favorites (first)\r\n"
               "GAME_SORT = %s\r\n"
               "; The game last started from the launcher (START in the game picker)\r\n"
               "LAST_GAME = %s\r\n",
            s->dsirpc_ip, s->backup_only ? "backup" : "sync", s->auto_update ? "on" : "off",
            s->classic_look ? "classic" : "modern", s->sounds ? "on" : "off",
            MUSICS[s->music < MUSIC_CHOICES ? s->music : MUSIC_BRIGHT],
            SORTS[s->game_sort < N_SORTS ? s->game_sort : 0], s->last_game);
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
#include "topscreen.h"
#include "ui.h"

enum { ROW_FIND, ROW_ADDRESS, ROW_SAVES, ROW_UPDATES, ROW_LOOK, ROW_SOUNDS, ROW_MUSIC, ROWS };

// The classic look has no sounds or music, so no rows for them
static int rows(void)
{
    return ui_on() ? ROWS : ROW_SOUNDS;
}

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
    printf("%c Auto-update: %s\n", row == ROW_UPDATES ? '>' : ' ', s->auto_update ? "on" : "off");
    printf("%c Look:        classic\n", row == ROW_LOOK ? '>' : ' ');
    printf("-------------------------------\n");
    if (row == ROW_FIND)
        printf("How the launcher finds DSiRPC.\nAutomatically works on most\nnetworks; use an address if it\nisn't found.\n");
    else if (row == ROW_ADDRESS)
        printf("The PC's IP address. The\nlauncher shows it when it\nfinds DSiRPC (DSiRPC: ...).\n");
    else if (row == ROW_SAVES)
        printf("Back up and sync: newer saves\nfrom the PC come here too.\nBack up only: saves only go to\nthe PC, so each console can\nkeep its own.\n");
    else if (row == ROW_UPDATES)
        printf("On: when DSiRPC on the PC has\nother versions of the launcher\nor nds-bootstrap, the launcher\noffers them as it starts\n(A: update, B: not now).\n");
    else
        printf("Classic: these text screens.\nModern: the new screens, with\nthe games' icons, sounds, music\nand the battery.\n");
    printf("\x1b[21;0H-------------------------------\n");
    // (no newline after the last row: it would scroll the screen)
    if (editing >= 0)
        printf("Left/Right: move  Up/Down: +/-\nA or B: done");
    else
        printf("Up/Down: choose  A: change\nB: save and go back");
}

// The modern look's settings screen

static const char *const LABELS[ROWS] = { "Find DSiRPC", "Address", "Saves", "Auto-update", "Look", "Sounds",
                                          "Music" };
static const char *const HELP[ROWS] = {
    "How the launcher finds DSiRPC. Automatically works on most networks; use an address if it isn't found.",
    "The PC's IP address. The launcher shows it once it finds DSiRPC.",
    "Back up and sync: newer saves from the PC come here too. Back up only: saves only go to the PC, so each "
    "console can keep its own.",
    "On: when DSiRPC on the PC has other versions of the launcher or nds-bootstrap, the launcher offers them as "
    "it starts.",
    "Modern: these screens, with the games' icons, sounds, music and the battery. Classic: the text screens.",
    "Soft sounds as you move around and pick things.",
    "Bright: an airy loop (the default). Subtle: a quiet lounge one. Off: no music.",
};
static const char *const MUSIC_NAMES[MUSIC_CHOICES] = { "Off", "Bright", "Subtle" };

#define ROW_H   15
#define TEXT_Y  3       // a row's text, from its top

static void draw_switch(Canvas *c, int x, int y, bool yes)
{
    ui_round(c, x, y, 20, 10, 3, yes ? UI_GREEN : UI_SCROLL);
    ui_round(c, yes ? x + 12 : x + 2, y + 2, 6, 6, 2, UI_TEXT);
}

static void draw_modern(const LauncherSettings *s, int row, bool manual, const int octet[4], int editing)
{
    Canvas *c = ui_screen();
    ui_clear();
    ui_header("Settings");
    for (int i = 0; i < ROWS; i++)
    {
        int y = UI_TOP + i * ROW_H;
        bool sel = i == row;
        if (sel)
        {
            ui_fill(c, 8, y, UI_W - 16, ROW_H - 1, UI_GREEN);
            ui_fill(c, 10, y + 2, UI_W - 20, ROW_H - 5, UI_PANEL);
        }
        bool dim = i == ROW_ADDRESS && !manual;
        ui_text(c, 16, y + TEXT_Y, LABELS[i], dim ? UI_DIM : UI_TEXT);
        int right = UI_W - 16;
        uint8_t ink = sel ? UI_TEXT : UI_DIM;
        switch (i)
        {
        case ROW_FIND:
            ui_text_right(c, right, y + TEXT_Y, manual ? "At this address" : "Automatically", ink);
            break;
        case ROW_ADDRESS:
            if (!manual)
            {
                ui_text_right(c, right, y + TEXT_Y, "Looked for", UI_DIM);
                break;
            }
            {
                char part[8];
                int w = 0;
                for (int o = 0; o < 4; o++)
                {
                    snprintf(part, sizeof(part), o < 3 ? "%d." : "%d", octet[o]);
                    w += ui_text_width(part) + 1;
                }
                int x = right - w + 1;
                for (int o = 0; o < 4; o++)
                {
                    snprintf(part, sizeof(part), "%d", octet[o]);
                    x = ui_text(c, x, y + TEXT_Y, part, editing == o ? UI_AMBER : ink) + 1;
                    if (o < 3)
                        x = ui_text(c, x, y + TEXT_Y, ".", ink) + 1;
                }
            }
            break;
        case ROW_SAVES:
            ui_text_right(c, right, y + TEXT_Y, s->backup_only ? "Back up only" : "Back up and sync", ink);
            break;
        case ROW_UPDATES:
            draw_switch(c, right - 20, y + 2, s->auto_update);
            break;
        case ROW_LOOK:
            ui_text_right(c, right, y + TEXT_Y, s->classic_look ? "Classic" : "Modern", ink);
            break;
        case ROW_SOUNDS:
            draw_switch(c, right - 20, y + 2, s->sounds);
            break;
        case ROW_MUSIC:
            ui_text_right(c, right, y + TEXT_Y, MUSIC_NAMES[s->music < MUSIC_CHOICES ? s->music : MUSIC_BRIGHT], ink);
            break;
        }
        ui_touch_add(8, y, UI_W - 16, ROW_H - 1, i);
    }
    ui_text_wrap(c, 12, UI_TOP + ROWS * ROW_H + 3, HELP[row], UI_W - 24, 4, UI_DIM);
    if (editing >= 0)
    {
        static const UiKey keys[] = { { "<>", "Digit", 0 }, { "^v", "+/-", 0 }, { "A", "Done", KEY_A } };
        ui_footer(keys, 3);
    }
    else
    {
        static const UiKey keys[] = { { "A", "Change", KEY_A }, { "B", "Back", KEY_B } };
        ui_footer(keys, 2);
    }
    ui_present();
}

void settings_apply(const LauncherSettings *s)
{
    if (s->classic_look && ui_on())
        ui_leave();
    else if (!s->classic_look && !ui_on())
        ui_enter();
    top_modern(!s->classic_look);
    ui_sounds(s->sounds);
    music_play(s->classic_look ? MUSIC_OFF : (MusicChoice)s->music);
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
        if (ui_on())
            draw_modern(s, row, manual, octet, editing);
        else
            draw(s, row, manual, octet, editing);
        u32 down;
        int tap;
        do
        {
            sync_frame();
            scanKeys();
            down = (keysDownRepeat() & ~KEY_TOUCH) | ui_footer_key();
            tap = editing < 0 ? ui_tapped() : -1;
        } while (down == 0 && tap < 0);

        if (tap >= 0)
        {
            // A tap picks a row, and changes the one already picked
            if (tap != row)
            {
                row = tap;
                ui_sound(SND_MOVE);
                continue;
            }
            down |= KEY_A;
        }
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
            ui_sound(down & (KEY_A | KEY_B) ? SND_SELECT : SND_MOVE);
            continue;
        }
        if (down & KEY_UP)
        {
            row = (row + rows() - 1) % rows();
            ui_sound(SND_MOVE);
        }
        if (down & KEY_DOWN)
        {
            row = (row + 1) % rows();
            ui_sound(SND_MOVE);
        }
        if (down & (KEY_A | KEY_LEFT | KEY_RIGHT))
        {
            if (row == ROW_FIND)
                manual = !manual;
            else if (row == ROW_ADDRESS && manual)
                editing = 3;
            else if (row == ROW_SAVES)
                s->backup_only = !s->backup_only;
            else if (row == ROW_UPDATES)
                s->auto_update = !s->auto_update;
            else if (row == ROW_LOOK)
            {
                s->classic_look = !s->classic_look;
                settings_apply(s);
            }
            else if (row == ROW_SOUNDS)
            {
                s->sounds = !s->sounds;
                settings_apply(s);
            }
            else if (row == ROW_MUSIC)
            {
                // Off, Bright, Subtle: A and right go along, left back
                s->music = (uint8_t)((s->music + (down & KEY_LEFT ? MUSIC_CHOICES - 1 : 1)) % MUSIC_CHOICES);
                settings_apply(s);
            }
            if (row != ROW_ADDRESS || manual)
                ui_sound(SND_TOGGLE);
            else
                ui_sound(SND_ERROR);
        }
        if (down & KEY_B)
        {
            ui_sound(SND_BACK);
            break;
        }
    }

    if (manual)
        snprintf(s->dsirpc_ip, sizeof(s->dsirpc_ip), "%d.%d.%d.%d", octet[0], octet[1], octet[2], octet[3]);
    else
        s->dsirpc_ip[0] = '\0';
    if (memcmp(&before, s, sizeof(before)) != 0 && !settings_save(path, s))
    {
        if (ui_on())
        {
            static const UiKey keys[] = { { "A", "OK", KEY_A } };
            ui_sound(SND_ERROR);
            ui_card("Can't save the settings", "Is the SD card locked?", UI_RED, keys, 1);
        }
        else
        {
            consoleClear();
            printf("Can't save the settings\n(is the SD card locked?)\n\nPress A\n");
        }
        do
        {
            cothread_yield_irq(IRQ_VBLANK);
            scanKeys();
        } while (!(keysDown() & (KEY_A | KEY_B)) && !ui_footer_key());
    }
}
#endif
