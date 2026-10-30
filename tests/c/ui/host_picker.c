// picker.c: its screens, and what it finds on an SD card, printed

#include <stdlib.h>

#include "picker.c"

#include "ui_host.h"

static char games_dir[600], index_dir[600], sets_dir[600], unlocks[600], ini[600];
static LauncherSettings picker_settings;

static PickerUi sd_card(const char *sd)
{
    snprintf(games_dir, sizeof(games_dir), "%s/roms/nds", sd);
    snprintf(index_dir, sizeof(index_dir), "%s/DSiRPC", sd);
    snprintf(sets_dir, sizeof(sets_dir), "%s/DSiRPC/sets", sd);
    snprintf(unlocks, sizeof(unlocks), "%s/RPCUNLK.BIN", sd);
    snprintf(ini, sizeof(ini), "%s/DSiRPC/launcher.ini", sd);
    PickerUi ui = { games_dir, index_dir, sets_dir, unlocks, NULL, &picker_settings, ini };
    return ui;
}

static bool load(const PickerUi *ui, int sort)
{
    if (!load_games(ui) || (order = malloc(sizeof(int) * (n_games ? n_games : 1))) == NULL)
        return false;
    sort_mode = sort;
    sort_games();
    return true;
}

static int find_code(const char *code)
{
    for (int i = 0; i < n_games; i++)
    {
        if (strcmp(games[order[i]].code, code) == 0)
            return i;
    }
    return 0;
}

void host_picker_screens(const char *sd)
{
    PickerUi ui = sd_card(sd);
    if (!load(&ui, SORT_NAME))
        return;
    games[order[find_code("AMCE")]].favorite = true;
    int sel = find_code("CPUE");
    draw_list(sel, sel >= ROWS ? sel - ROWS + 1 : 0, &ui);
    show_game(&games[order[sel]]);
    host_shot("games");
    achievements_screen(&games[order[sel]], ui.sets_dir);    // (B: back)
    host_shot("achievements");
    free_games();
    top_dsi();
}

void host_games(const char *sd, int sort)
{
    PickerUi ui = sd_card(sd);
    if (!load(&ui, sort))
    {
        printf("games -1\n");
        return;
    }
    for (int i = 0; i < n_games; i++)
    {
        Game *g = &games[order[i]];
        count_achievements(g, ui.sets_dir);
        printf("game %s|%s|%s|%d|%d|%u|%d/%d\n", g->code[0] ? g->code : "-", g->title, g->publisher, g->version,
               g->favorite, (unsigned)g->played, g->earned, g->total);
    }
    printf("games %d\n", n_games);
    free_games();
}

void host_favorite(const char *sd, const char *path)
{
    PickerUi ui = sd_card(sd);
    if (load(&ui, SORT_NAME))
    {
        // Y on it, then back out: games.idx written
        for (int i = 0; i < n_games; i++)
        {
            if (strcmp(games[i].path, path) == 0)
                games[i].favorite = !games[i].favorite;
        }
        write_index(ui.index_dir, games, n_games);
    }
    free_games();
}

void host_started(const char *sd, const char *path)
{
    PickerUi ui = sd_card(sd);
    picker_started(ui.index_dir, path);
}
