// picker.c: its screens, and what it finds on an SD card, printed

#include <stdlib.h>

#include "picker.c"

#include "ui_host.h"

static char games_dir[600], index_dir[600], sets_dir[600], unlocks[600], ini[600];
static LauncherSettings picker_settings;

// The SD card at sd, the launcher in its folder there (sd's "DSiRPC", or
// another: "roms/nds/DSiRPC", with the games)
static PickerUi sd_card_with(const char *sd, const char *folder)
{
    snprintf(games_dir, sizeof(games_dir), "%s/roms/nds", sd);
    snprintf(index_dir, sizeof(index_dir), "%s/%s", sd, folder);
    snprintf(sets_dir, sizeof(sets_dir), "%s/%s/sets", sd, folder);
    snprintf(unlocks, sizeof(unlocks), "%s/RPCUNLK.BIN", sd);
    snprintf(ini, sizeof(ini), "%s/%s/launcher.ini", sd, folder);
    PickerUi ui = { games_dir, index_dir, sets_dir, unlocks, NULL, &picker_settings, ini };
    return ui;
}

static PickerUi sd_card(const char *sd)
{
    return sd_card_with(sd, "DSiRPC");
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
    Game *adme = &games[order[find_code("ADME")]];    // (its USA file: RetroAchievements has no set for it)
    adme->hashed = HASH_OK;
    adme->ra = PICKER_RA_NOT_THIS_ROM;
    int sel = find_code("CPUE");
    draw_list(sel, sel >= ROWS ? sel - ROWS + 1 : 0, &ui);
    show_game(&games[order[sel]]);
    host_shot("games");
    achievements_screen(&games[order[sel]], ui.sets_dir);    // (B: back)
    host_shot("achievements");
    // A file RetroAchievements has the game of, but no set for (another
    // version, or a hack), one whose game it doesn't have, and one DSiRPC
    // hasn't checked yet
    Game *g = &games[order[sel]];
    g->hashed = HASH_OK;
    g->ra = PICKER_RA_NOT_THIS_ROM;
    g->earned = g->total = 0;               // (as count_achievements() leaves a game with no set)
    draw_list(sel, sel >= ROWS ? sel - ROWS + 1 : 0, &ui);
    show_game(g);
    achievements_screen(g, ui.sets_dir);    // (A: back)
    host_shot("achievements_unsupported");
    g->ra = PICKER_RA_NO_GAME;
    draw_list(sel, sel >= ROWS ? sel - ROWS + 1 : 0, &ui);
    show_game(g);
    achievements_screen(g, ui.sets_dir);
    host_shot("achievements_no_game");
    int other = find_code("ATRE");          // (no set on the card)
    games[order[other]].hashed = HASH_NONE;
    draw_list(other, other >= ROWS ? other - ROWS + 1 : 0, &ui);
    show_game(&games[order[other]]);
    achievements_screen(&games[order[other]], ui.sets_dir);
    host_shot("achievements_new");
    // Then RetroAchievements has a set for it, not on the card yet; and the
    // same for a file without a game code (homebrew: it can't be given it)
    Game *o = &games[order[other]];
    o->hashed = HASH_OK;
    o->ra = PICKER_RA_SET;
    draw_list(other, other >= ROWS ? other - ROWS + 1 : 0, &ui);
    show_game(o);
    achievements_screen(o, ui.sets_dir);
    host_shot("achievements_coming");
    o->code[0] = '\0';
    draw_list(other, other >= ROWS ? other - ROWS + 1 : 0, &ui);
    show_game(o);
    achievements_screen(o, ui.sets_dir);
    host_shot("achievements_no_code");
    free_games();
    top_dsi();
}

// The demo's (ui_host.c): the game list (A-Z) with the game with that code
// picked, or its achievements
void host_demo_games(const char *sd, const char *code, bool achievements)
{
    PickerUi ui = sd_card(sd);
    if (!load(&ui, SORT_NAME))
        return;
    games[order[find_code("AMCE")]].favorite = true;
    int sel = find_code(code);
    draw_list(sel, sel >= ROWS ? sel - ROWS + 1 : 0, &ui);
    show_game(&games[order[sel]]);
    if (achievements)
        achievements_screen(&games[order[sel]], ui.sets_dir);    // (B: back)
    free_games();
}

void host_games(const char *sd, int sort, const char *folder)
{
    PickerUi ui = sd_card_with(sd, folder);
    if (!load(&ui, sort))
    {
        printf("games -1\n");
        return;
    }
    for (int i = 0; i < n_games; i++)
    {
        Game *g = &games[order[i]];
        count_achievements(g, ui.sets_dir);
        // (then the badge, the top screen's line without a count, and X's card: one state)
        RaState s = ra_state(g);
        const char *what, *card = ra_card(s, &what);
        printf("game %s|%s|%s|%d|%d|%u|%d/%d|%s|%s|%s\n", g->code[0] ? g->code : "-", shown_title(g), g->publisher,
               g->version, g->favorite, (unsigned)g->played, g->earned, g->total,
               s == RA_LISTED ? "count" : ra_badge(s), ra_top(s), card != NULL ? card : "list");
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

void host_hash(const char *path)
{
    uint8_t md5[16];
    char hex[33] = "-";
    int r = rom_hash(path, md5, NULL, NULL);
    if (r == ROMHASH_OK)
        md5_to_hex(md5, hex);
    printf("hash %d %s\n", r, hex);
}

static int setup_calls;
static void count_progress(int game, int games, const char *title, uint32_t done, uint32_t total, void *ctx)
{
    (void)game; (void)games; (void)title; (void)done; (void)total; (void)ctx;
    setup_calls++;
}

void host_setup(const char *sd)
{
    PickerUi ui = sd_card(sd);
    PickerSetup setup = { .games_dir = ui.games_dir, .index_dir = ui.index_dir, .progress = count_progress };
    setup_calls = 0;
    int hashed;
    int done = picker_setup(&setup, &hashed);
    printf("setup %d %d %d\n", done, hashed, setup_calls > 0);
}

void host_roms(const char *sd, const char *started)
{
    PickerUi ui = sd_card(sd);
    uint8_t *roms;
    size_t size;
    int n = picker_rom_hashes(ui.index_dir, started, &roms, &size);
    const uint8_t *r = roms;
    for (int i = 0; i < n; i++)
    {
        char hex[33];
        md5_to_hex(r + 4, hex);
        printf("rom %.4s %s %d %.*s\n", (const char *)r, hex, r[20], r[21], (const char *)r + PICKER_ROM_RECORD);
        r += PICKER_ROM_RECORD + r[21];
    }
    printf("roms %d %d\n", n, (size_t)(r - roms) == size);
    free(roms);
}

void host_status(const char *sd, const char *list)
{
    PickerUi ui = sd_card(sd);
    uint8_t status[64 * PICKER_STATUS_RECORD];
    int n = 0;
    for (const char *p = list; *p != '\0' && n < 64;)
    {
        uint8_t *s = status + n * PICKER_STATUS_RECORD;
        memset(s, 0, PICKER_STATUS_RECORD);
        if (strlen(p) < 34 || !md5_from_hex(p, s))
            break;
        s[16] = (uint8_t)atoi(p + 33);
        n++;
        p = strchr(p, ',');
        if (p == NULL)
            break;
        p++;
    }
    printf("status %d\n", picker_store_status(ui.index_dir, ui.sets_dir, status, n));
}
