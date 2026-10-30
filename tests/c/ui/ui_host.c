// The launcher's modern look on a PC, driven by tests/test_launcher_ui.py
// (and tools/render_launcher.py, for the README's pictures): its screens drawn
// by its own code (ui.c, topscreen.c, and main.c, picker.c, saveui.c,
// settings.c and update.c included whole by host_*.c) on the libnds stand-in
// in stub/, with the sanitizers on. One command per line on stdin, fields
// after the command separated by '|':
//
//   render out|sd|rom|key        draws every screen into out/NAME.ppm (the
//                                picker's games from the SD card at sd, the
//                                starting screen's game rom; key 1: the top
//                                screen's clear pixels magenta): render N,
//                                then pattern RRGGBB RRGGBB RRGGBB (the
//                                diamonds' backdrop, tile and dot)
//   games sd|sort                the game list (sort: 0 recent, 1 A-Z, 2
//                                favorites first): game lines
//                                code|name|publisher|version|favorite|last
//                                played|earned/total, then games N
//   favorite sd|path             Y on a game, then back out
//   started sd|path              the game being started (games.idx)
//   text a|b                     text a|b's widths|a's lines at 100 pixels
//   music classic|choice|stop    settings_apply() with that look and Music
//                                (0 off, 1 bright, 2 subtle), then
//                                music_stop() if stop is 1: music then the
//                                maxmod calls made, comma-separated
//
// The SD card is a folder on the PC with sd:'s layout (roms/nds, DSiRPC, the
// root's RPCUNLK.BIN).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <nds.h>

#include "music.h"
#include "settings.h"
#include "topscreen.h"
#include "ui.h"
#include "ui_host.h"

static int split(char *rest, char **field, int max)
{
    int n = 0;
    while (n < max)
    {
        field[n++] = rest;
        char *bar = strchr(rest, '|');
        if (bar == NULL)
            break;
        *bar = '\0';
        rest = bar + 1;
    }
    return n;
}

static unsigned rgb24(uint16_t c)
{
    return ((c & 31) << 19) | (((c >> 5) & 31) << 11) | (((c >> 10) & 31) << 3);
}

int main(void)
{
    consoleDemoInit();
    top_init();
    ui_init();
    LauncherSettings defaults;
    settings_load("/nonexistent/launcher.ini", &defaults);
    settings_apply(&defaults);      // the modern look

    char line[1024];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        line[strcspn(line, "\r\n")] = '\0';
        char *rest = strchr(line, ' ');
        if (rest != NULL)
            *rest++ = '\0';
        else
            rest = line + strlen(line);
        char *f[4] = { 0 };
        int nf = split(rest, f, 4);

        if (strcmp(line, "render") == 0 && nf == 4)
        {
            host_out = f[0];
            host_key = atoi(f[3]) != 0;
            host_shots = 0;
            host_main_screens(f[2]);
            host_update_screens();
            host_settings_screens();
            host_picker_screens(f[1]);
            host_save_screens();
            printf("render %d\n", host_shots);
            printf("pattern %06X %06X %06X\n", rgb24(BG_PALETTE[0]), rgb24(BG_PALETTE[1]), rgb24(BG_PALETTE[2]));
        }
        else if (strcmp(line, "games") == 0 && nf == 2)
        {
            host_games(f[0], atoi(f[1]));
        }
        else if (strcmp(line, "favorite") == 0 && nf == 2)
        {
            host_favorite(f[0], f[1]);
            printf("favorite\n");
        }
        else if (strcmp(line, "started") == 0 && nf == 2)
        {
            host_started(f[0], f[1]);
            printf("started\n");
        }
        else if (strcmp(line, "music") == 0 && nf == 3)
        {
            host_music_log[0] = '\0';
            LauncherSettings s = defaults;
            s.classic_look = atoi(f[0]) != 0;
            s.music = (uint8_t)atoi(f[1]);
            settings_apply(&s);
            if (atoi(f[2]) != 0)
                music_stop();
            printf("music %s\n", host_music_log);
        }
        else if (strcmp(line, "text") == 0 && nf == 2)
        {
            printf("text %d|%d|%d\n", ui_text_width(f[0]), ui_text_width(f[1]),
                   ui_text_wrap(NULL, 0, 0, f[0], 100, 20, 0));
        }
        else
        {
            printf("? %s\n", line);
        }
        fflush(stdout);
    }
    return 0;
}
