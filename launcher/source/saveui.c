// SPDX-License-Identifier: MIT
//
// The save sync's screens (see saveui.h). The console is 32x24 characters:
//
//   Saves (back up and sync)
//   -------------------------------
//   > Sync all (3 to do)
//     ^ Pokemon Black              green ^: back up (changed here)
//     v Pokemon White              cyan v: from the PC (newer there)
//     ! Pokemon Platinum           yellow !: changed on both: asked
//       Mario Kart DS              in sync
//     x Picross 3D                 grey: left out (Y)
//   -------------------------------
//   From 3DS 3F21, Oct 20 14:02    the selected save (whose the PC's is)
//   A:sync Y:leave out X:restore
//   START:sync all  B:back
//
//   Up/Down: move   L/R or Left/Right: a page   A: sync the one picked
//   (or all, on Sync all)   START: sync all   Y: leave out / include
//   X: the versions the PC keeps (restore one)   B: back to the launcher
//
// The modern look draws the same screens with ui.c: the list six saves at a
// time, each with a badge for what it does (UP, DN, !, OK), the picked one's
// details on the top screen (topscreen.c's top_save()), and cards for the
// progress, the questions and the messages. A tap picks a save (a second
// one syncs it).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include <nds.h>

#include "saveui.h"
#include "savesync.h"
#include "topscreen.h"
#include "ui.h"

#define LIST_ROWS        17
#define M_ROWS           6        // the modern look's
#define M_ROW_H          24
#define M_LIST_Y         (UI_BAR_H + 3)
#define NAME_COLS        27
#define UNIX_TIME_2000   946684800

#define WHITE   "\x1b[39;0m"
#define GREEN   "\x1b[32;1m"
#define CYAN    "\x1b[36;1m"
#define YELLOW  "\x1b[33;1m"
#define RED     "\x1b[31;1m"
#define GREY    "\x1b[30;1m"

static SaveList list;
static SaveConsole console;
static SyncJob job;
static struct sockaddr_in server;
static SaveCounts counts;
static int *shown;          // indexes into list.items of what the list shows
static int n_shown;
static int tapped = -1;     // the list row tapped (the modern look), or -1

// ---------------------------------------------------------------------------
// Little helpers

static void next_frame(void)
{
    sync_frame();
    scanKeys();
}

static bool b_pressed(void)
{
    scanKeys();
    return (keysDown() & KEY_B) != 0;
}

static void wait_release(void)
{
    do
        next_frame();
    while (keysHeld() & (KEY_A | KEY_B | KEY_X | KEY_Y | KEY_START | KEY_L | KEY_R));
}

static u32 wait_keys(u32 keys)
{
    while (1)
    {
        next_frame();
        u32 down = (keysDownRepeat() | ui_footer_key()) & keys;
        tapped = ui_tapped();
        if (down || tapped >= 0)
            return down;
    }
}

static int list_rows(void)
{
    return ui_on() ? M_ROWS : LIST_ROWS;
}

static void message_tone(const char *title, const char *text, uint8_t accent)
{
    if (ui_on())
    {
        static const UiKey keys[] = { { "A", "OK", KEY_A } };
        ui_sound(accent == UI_GREEN ? SND_DONE : SND_ERROR);
        ui_card(title, text, accent, keys, 1);
    }
    else
    {
        consoleClear();
        printf("%s\n-------------------------------\n%s\n\nPress A\n", title, text);
    }
    wait_release();
    wait_keys(KEY_A | KEY_B | KEY_START);
}

static void message(const char *title, const char *text)
{
    bool good = strcmp(title, "Synced") == 0 || strcmp(title, "Restored") == 0;
    message_tone(title, text, good ? UI_GREEN : strncmp(title, "Didn't", 6) == 0 ? UI_RED : UI_AMBER);
}

// "Oct 20 14:02" from seconds since 2000 (the console's local time, as is)
static void format_time(char *out, size_t outsz, uint32_t since_2000)
{
    if (since_2000 == 0)
    {
        snprintf(out, outsz, "?");
        return;
    }
    time_t t = (time_t)since_2000 + UNIX_TIME_2000;
    struct tm *tm = gmtime(&t);
    static const char *months[] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
    snprintf(out, outsz, "%s %d %02d:%02d", months[tm->tm_mon], tm->tm_mday, tm->tm_hour, tm->tm_min);
}

static void format_size(char *out, size_t outsz, uint32_t size)
{
    if (size >= 1024 * 1024)
        snprintf(out, outsz, "%u.%u MB", (unsigned)(size / (1024 * 1024)),
                 (unsigned)((size % (1024 * 1024)) * 10 / (1024 * 1024)));
    else
        snprintf(out, outsz, "%u KB", (unsigned)((size + 1023) / 1024));
}

// The game's name, with its save slot after it if it isn't the first
static void item_name(char *out, size_t outsz, const SaveItem *it, int cols)
{
    char name[SAVE_NAME_LEN + 8];
    if (it->slot > 0)
        snprintf(name, sizeof(name), "%s (%d)", it->name, it->slot);
    else
        snprintf(name, sizeof(name), "%s", it->name);
    if ((int)strlen(name) > cols)
    {
        name[cols - 1] = '~';
        name[cols] = '\0';
    }
    snprintf(out, outsz, "%s", name);
}

static bool to_do(const SaveItem *it)
{
    return saves_needs_sync(it, console.backup_only);
}

// ---------------------------------------------------------------------------
// Progress

static const char *progress_title = "";

// A screen with progress coming: the console cleared, or the modern look's
// header and B
static void begin(const char *title)
{
    progress_title = title;
    if (!ui_on())
    {
        consoleClear();
        return;
    }
    static const UiKey keys[] = { { "B", "Cancel", KEY_B } };
    ui_clear();
    ui_header("Saves");
    ui_footer(keys, 1);
    ui_present();
}

// The modern look's progress: a card with the title, what it's doing (up to
// two lines), and a bar (or how many were found)
static void progress_card(const char *what, uint32_t done, uint32_t total, int pct)
{
    Canvas *c = ui_screen();
    char first[64];
    const char *nl = strchr(what, '\n');
    snprintf(first, sizeof(first), "%.*s", nl != NULL ? (int)(nl - what) : (int)strlen(what), what);
    ui_panel(10, 52, UI_W - 20, 76, UI_CYAN);
    ui_text_fit(c, 20, 61, progress_title, UI_W - 40, UI_CYAN);
    ui_text_fit(c, 20, 76, first, UI_W - 40, UI_SOFT);
    if (nl != NULL)
        ui_text_fit(c, 20, 87, nl + 1, UI_W - 40, UI_DIM);
    char num[24];
    if (total)
    {
        snprintf(num, sizeof(num), "%d%%", pct);
        ui_bar(c, 20, 104, UI_W - 76, 10, pct, UI_CYAN);
        ui_text_right(c, UI_W - 20, 105, num, UI_TEXT);
    }
    else
    {
        snprintf(num, sizeof(num), "%u found", (unsigned)done);
        ui_text(c, 20, 105, num, UI_TEXT);
    }
    ui_present();
}

static void progress(const char *what, uint32_t done, uint32_t total)
{
    static int last_pct = -1;
    int pct = total ? (int)((uint64_t)done * 100 / total) : -1;
    if (total && pct == last_pct && done != 0)
        return;
    last_pct = pct;
    if (ui_on())
    {
        progress_card(what, done, total, pct);
        return;
    }
    printf("\x1b[0;0H%-31.31s\n-------------------------------\n", progress_title);
    // What it's doing, on up to two lines ("Taking Pokemon Black\nfrom: 3DS 3F21")
    const char *nl = strchr(what, '\n');
    int first = nl != NULL ? (int)(nl - what) : (int)strlen(what);
    printf("\x1b[3;0H%-31.*s\n", first > 31 ? 31 : first, what);
    printf("\x1b[4;0H%-31.31s\n", nl != NULL ? nl + 1 : "");
    if (total)
    {
        char bar[25];
        int fill = pct * 24 / 100;
        for (int i = 0; i < 24; i++)
            bar[i] = i < fill ? '#' : '-';
        bar[24] = '\0';
        printf("\x1b[5;0H[%s] %3d%%\n", bar, pct);
    }
    else
    {
        printf("\x1b[5;0H%u found%-20s\n", (unsigned)done, "");
    }
}

// ---------------------------------------------------------------------------
// The list

static void build_shown(void)
{
    free(shown);
    shown = malloc(sizeof(int) * (list.count ? list.count : 1));
    n_shown = 0;
    if (shown == NULL)
        return;
    for (int i = 0; i < list.count; i++)
    {
        if (list.items[i].action != SA_UNKNOWN)
            shown[n_shown++] = i;
    }
}

static int count_to_do(void)
{
    int n = 0;
    for (int i = 0; i < n_shown; i++)
        n += to_do(&list.items[shown[i]]);
    return n;
}

static void icon(const SaveItem *it, const char **color, char *c)
{
    *color = WHITE;
    *c = ' ';
    if (it->failed)
    {
        *color = RED;
        *c = 'X';
        return;
    }
    if (it->excluded)
    {
        *color = GREY;
        *c = 'x';
        return;
    }
    switch (it->action)
    {
    case SA_UPLOAD:
    case SA_BACKUP:
        *color = GREEN;
        *c = '^';
        break;
    case SA_DOWNLOAD:
    case SA_DOWNLOAD_NEW:
        if (!console.backup_only)
        {
            *color = CYAN;
            *c = 'v';
        }
        break;
    case SA_CONFLICT:
        *color = YELLOW;
        *c = '!';
        break;
    default:
        break;
    }
}

static void detail(const SaveItem *it, char *out, size_t outsz)
{
    char when[24];
    format_time(when, sizeof(when), it->pc_time);
    if (it->failed)
        snprintf(out, outsz, "Didn't sync; try again (A)");
    else if (it->excluded)
        snprintf(out, outsz, "Left out (Y to include it)");
    else if (it->done)
        snprintf(out, outsz, "Synced");
    else
    {
        switch (it->action)
        {
        case SA_UPLOAD:
        case SA_BACKUP:
            snprintf(out, outsz, it->base ? "Changed here: back it up" : "New here: back it up");
            break;
        case SA_DOWNLOAD:
            if (it->pc_source[0] != '\0')
                snprintf(out, outsz, "From %s, %s", it->pc_source, when);
            else
                snprintf(out, outsz, "Newer on the PC: %s", when);
            break;
        case SA_DOWNLOAD_NEW:
            if (it->pc_source[0] != '\0')
                snprintf(out, outsz, "New from %s, %s", it->pc_source, when);
            else
                snprintf(out, outsz, "Only on the PC: %s", when);
            break;
        case SA_CONFLICT:
            snprintf(out, outsz, "Changed here and on the PC");
            break;
        case SA_EXCLUDED:
            snprintf(out, outsz, "Left out (Y to include it)");
            break;
        default:
            snprintf(out, outsz, "In sync");
            break;
        }
    }
}

// The modern look's list: a badge for what each save does, a short word on
// the right, and the picked one's details on the top screen

static void badge(const SaveItem *it, const char **text, uint8_t *fill, uint8_t *ink)
{
    *text = "OK";
    *fill = UI_CHIP;
    *ink = UI_DIM;
    if (it->failed)
    {
        *text = "X";
        *fill = UI_RED;
        *ink = UI_RED_DARK;
        return;
    }
    if (it->excluded)
    {
        *text = "--";
        return;
    }
    if (it->done)
    {
        *fill = UI_GREEN;
        *ink = UI_GREEN_DARK;
        return;
    }
    switch (it->action)
    {
    case SA_UPLOAD:
    case SA_BACKUP:
        *text = "UP";
        *fill = UI_GREEN;
        *ink = UI_GREEN_DARK;
        break;
    case SA_DOWNLOAD:
    case SA_DOWNLOAD_NEW:
        if (!console.backup_only)
        {
            *text = "DN";
            *fill = UI_CYAN;
            *ink = UI_CYAN_DARK;
        }
        break;
    case SA_CONFLICT:
        *text = "!";
        *fill = UI_AMBER;
        *ink = UI_AMBER_DARK;
        break;
    default:
        break;
    }
}

static void short_word(const SaveItem *it, char *out, size_t outsz)
{
    if (it->failed)
        snprintf(out, outsz, "didn't sync");
    else if (it->excluded)
        snprintf(out, outsz, "left out");
    else if (it->done)
        snprintf(out, outsz, "synced");
    else if (it->action == SA_UPLOAD || it->action == SA_BACKUP)
        format_size(out, outsz, it->size);
    else if ((it->action == SA_DOWNLOAD || it->action == SA_DOWNLOAD_NEW) && !console.backup_only)
        snprintf(out, outsz, "%.20s", it->pc_source[0] ? it->pc_source : "from the PC");
    else if (it->action == SA_CONFLICT)
        snprintf(out, outsz, "conflict");
    else
        snprintf(out, outsz, "in sync");
}

static void show_save(const SaveItem *it)
{
    char name[48], size[16], status[96], here[24], there[24];
    item_name(name, sizeof(name), it, 40);
    format_size(size, sizeof(size), it->present ? it->size : it->pc_size);
    detail(it, status, sizeof(status));
    if (it->present)
        format_time(here, sizeof(here), (uint32_t)(it->mtime - UNIX_TIME_2000));
    if (it->pc_time)
        format_time(there, sizeof(there), it->pc_time);
    const char *text;
    uint8_t fill, ink;
    badge(it, &text, &fill, &ink);
    TopSave t = {
        .name = name,
        .size = size,
        .status = status,
        .tone = fill == UI_GREEN ? TONE_GREEN : fill == UI_CYAN ? TONE_CYAN : fill == UI_AMBER ? TONE_AMBER
                : fill == UI_RED ? TONE_RED : TONE_GREY,
        .console = console.model >= 2 ? "3DS" : "DSi",
        .here = it->present ? here : NULL,
        .there = it->pc_time ? there : NULL,
        .from = it->pc_source,
        .versions = it->versions,
    };
    top_save(&t);
}

static void draw_list_modern(int sel, int top)
{
    Canvas *c = ui_screen();
    ui_clear();
    ui_header(NULL);
    int x = ui_text(c, 8, 5, "Saves", UI_SOFT);
    ui_text(c, x + 6, 5, console.backup_only ? "back up only" : "back up and sync", UI_DIM);
    int rows = n_shown + 1;
    for (int row = top; row < rows && row < top + M_ROWS; row++)
    {
        int y = M_LIST_Y + (row - top) * M_ROW_H;
        if (row == sel)
        {
            ui_fill(c, 4, y, UI_W - 16, M_ROW_H - 2, UI_GREEN);
            ui_fill(c, 6, y + 2, UI_W - 20, M_ROW_H - 6, UI_PANEL);
        }
        ui_touch_add(4, y, UI_W - 16, M_ROW_H - 2, row);
        if (row == 0)
        {
            int n = count_to_do();
            char text[32];
            if (n)
            {
                snprintf(text, sizeof(text), "Sync all (%d)", n);
                ui_chip(c, 10, y + 5, text, UI_GREEN, UI_GREEN_DARK);
                ui_text_right(c, UI_W - 16, y + 7, "START", UI_DIM);
            }
            else
            {
                ui_chip(c, 10, y + 5, n_shown ? "All in sync" : "No saves to sync", UI_CHIP, UI_DIM);
            }
            continue;
        }
        const SaveItem *it = &list.items[shown[row - 1]];
        const char *text;
        uint8_t fill, ink;
        badge(it, &text, &fill, &ink);
        ui_fill(c, 10, y + 5, 20, 12, fill);
        ui_text_center(c, 20, y + 7, text, ink);
        char word[32], name[48];
        short_word(it, word, sizeof(word));
        item_name(name, sizeof(name), it, 40);
        int ww = ui_text_width(word);
        ui_text(c, UI_W - 16 - ww, y + 7, word, UI_DIM);
        ui_text_fit(c, 36, y + 7, name, UI_W - 16 - ww - 42, it->excluded ? UI_DIM : UI_TEXT);
    }
    ui_scrollbar(UI_W - 8, M_LIST_Y, M_ROWS * M_ROW_H - 2, top, M_ROWS, rows);
    static const UiKey keys[] = { { "A", "Sync", KEY_A }, { "X", "Restore", KEY_X }, { "Y", "Leave out", KEY_Y } };
    ui_footer(keys, 3);
    ui_present();
    if (sel > 0)
        show_save(&list.items[shown[sel - 1]]);
    else
        top_dsi();
}

static void draw_list(int sel, int top)
{
    if (ui_on())
    {
        draw_list_modern(sel, top);
        return;
    }
    consoleClear();
    printf("Saves (%s)\n", console.backup_only ? "back up only" : "back up and sync");
    printf("-------------------------------\n");
    int rows = n_shown + 1;
    for (int row = top; row < rows && row < top + LIST_ROWS; row++)
    {
        char mark = row == sel ? '>' : ' ';
        if (row == 0)
        {
            int n = count_to_do();
            if (n)
                printf("%c Sync all (%d to do)\n", mark, n);
            else
                printf("%c Sync all " GREY "(all in sync)" WHITE "\n", mark);
            continue;
        }
        const SaveItem *it = &list.items[shown[row - 1]];
        const char *color;
        char c;
        icon(it, &color, &c);
        char name[NAME_COLS + 1];
        item_name(name, sizeof(name), it, NAME_COLS);
        printf("%c %s%c %s%s" WHITE "\n", mark, color, c, it->excluded ? GREY : "", name);
    }
    printf("\x1b[20;0H-------------------------------");
    if (sel > 0)
    {
        char text[96];
        detail(&list.items[shown[sel - 1]], text, sizeof(text));
        printf("\x1b[21;0H%-31.31s", text);
    }
    else
    {
        printf("\x1b[21;0H%-31.31s", n_shown ? "Sync everything that changed" : "No saves to sync");
    }
    printf("\x1b[22;0HA:sync Y:leave out X:restore");
    printf("\x1b[23;0HSTART:sync all  B:back");
}

// ---------------------------------------------------------------------------
// Conflicts, versions

// Asks which save to keep. Returns the choice (SC_SKIP for B).
static SaveChoice ask_conflict(const SaveItem *it)
{
    char name[33], here[24], there[24], size_here[16], size_there[16];
    item_name(name, sizeof(name), it, 32);
    format_time(here, sizeof(here), (uint32_t)(it->mtime - UNIX_TIME_2000));
    format_time(there, sizeof(there), it->pc_time);
    format_size(size_here, sizeof(size_here), it->size);
    format_size(size_there, sizeof(size_there), it->pc_size);
    const char *self = console.model >= 2 ? "3DS" : "DSi";

    if (ui_on())
    {
        // Both dates are on the top screen (the save's details)
        char keep[24], text[160];
        snprintf(keep, sizeof(keep), "Keep %s's", self);
        UiKey keys[] = { { "L", keep, KEY_L }, { "R", "Take PC's", KEY_R }, { "B", "Later", KEY_B } };
        snprintf(text, sizeof(text), "%s changed here and on the PC since the last sync.\n\n"
                 "The one you don't pick stays in the PC's backups.", name);
        show_save(it);
        ui_sound(SND_TOGGLE);
        ui_card("Both saves changed", text, UI_AMBER, keys, 3);
        wait_release();
        u32 k;
        while ((k = wait_keys(KEY_L | KEY_R | KEY_B)) == 0)
            ;
        ui_sound(k & KEY_B ? SND_BACK : SND_SELECT);
        if (k & KEY_L)
            return SC_KEEP_CONSOLE;
        if (k & KEY_R)
            return SC_TAKE_PC;
        return SC_SKIP;
    }

    consoleClear();
    printf(YELLOW "Both saves changed" WHITE "\n");
    printf("-------------------------------\n");
    printf("%s\n\n", name);
    printf("This %s: %s\n", self, here);
    printf("          %s\n", size_here);
    printf("The PC:   %s\n", there);
    printf("          %s\n", size_there);
    if (it->pc_source[0] != '\0')
        printf("          from: %.15s\n", it->pc_source);
    printf("\nThe one you don't pick is kept\nin the PC's backups.\n");
    printf("\x1b[20;0H-------------------------------");
    printf("\x1b[21;0HL: keep this %s's", self);
    printf("\x1b[22;0HR: take the PC's");
    printf("\x1b[23;0HB: decide later");
    wait_release();
    u32 k = wait_keys(KEY_L | KEY_R | KEY_B);
    if (k & KEY_L)
        return SC_KEEP_CONSOLE;
    if (k & KEY_R)
        return SC_TAKE_PC;
    return SC_SKIP;
}

static void sync_one(SaveItem *it)
{
    char msg[160];
    begin("Syncing saves");
    int r = saves_sync_item(&job, &console, &server, &list, it, &counts, progress, msg, sizeof(msg));
    if (r < 0 || msg[0] != '\0')
    {
        char name[33];
        item_name(name, sizeof(name), it, 32);
        char text[200];
        snprintf(text, sizeof(text), "%s:\n%s", name, msg[0] ? msg : "it didn't sync");
        message(r < 0 ? "Didn't sync" : "Synced", text);
    }
}

// The modern look's versions: when each was saved, its size and whose it
// is, the live save first
static void draw_versions_modern(const SaveItem *it, const SaveVersion *v, int n, int sel, int top)
{
    Canvas *c = ui_screen();
    char name[48], line[48];
    item_name(name, sizeof(name), it, 40);
    ui_clear();
    ui_header(NULL);
    snprintf(line, sizeof(line), "%d version%s", n, n == 1 ? "" : "s");
    int rx = ui_header_right(line, UI_DIM);
    ui_text_fit(c, 8, 5, name, rx - 16, UI_SOFT);
    for (int i = top; i < n && i < top + M_ROWS; i++)
    {
        int y = M_LIST_Y + (i - top) * M_ROW_H;
        if (i == sel)
        {
            ui_fill(c, 4, y, UI_W - 16, M_ROW_H - 2, UI_GREEN);
            ui_fill(c, 6, y + 2, UI_W - 20, M_ROW_H - 6, UI_PANEL);
        }
        char when[24], size[16];
        format_time(when, sizeof(when), v[i].time);
        format_size(size, sizeof(size), v[i].size);
        if (v[i].version == 0)
            ui_chip(c, 10, y + 5, "live", UI_CYAN, UI_CYAN_DARK);
        ui_text(c, 46, y + 7, when, UI_TEXT);
        ui_text(c, 136, y + 7, size, UI_DIM);
        ui_text_fit(c, 182, y + 7, v[i].source, UI_W - 16 - 182, UI_DIM);
        ui_touch_add(4, y, UI_W - 16, M_ROW_H - 2, i);
    }
    ui_scrollbar(UI_W - 8, M_LIST_Y, M_ROWS * M_ROW_H - 2, top, M_ROWS, n);
    static const UiKey keys[] = { { "A", "Put it back", KEY_A }, { "B", "Back", KEY_B } };
    ui_footer(keys, 2);
    ui_present();
}

static void versions_screen(SaveItem *it)
{
    static SaveVersion v[SAVE_MAX_VERSIONS];
    char msg[160];
    if (ui_on())
    {
        begin("Asking DSiRPC");
        progress_card("for the versions it keeps", 0, 1, 0);
    }
    else
    {
        consoleClear();
        printf("Asking DSiRPC for the\nversions it keeps...\n");
    }
    int n = saves_versions(&job, &console, &server, it, v, SAVE_MAX_VERSIONS, msg, sizeof(msg));
    if (n < 0)
    {
        message("Older versions", msg);
        return;
    }
    if (n == 0)
    {
        message("Older versions", "DSiRPC doesn't keep any\nversions of this save yet.");
        return;
    }
    int sel = 0, top = 0;
    keysSetRepeat(15, 4);
    wait_release();
    while (1)
    {
        if (sel < top)
            top = sel;
        if (sel >= top + list_rows())
            top = sel - list_rows() + 1;
        char name[33];
        item_name(name, sizeof(name), it, 32);
        if (ui_on())
        {
            draw_versions_modern(it, v, n, sel, top);
            u32 k = wait_keys(KEY_UP | KEY_DOWN | KEY_A | KEY_B);
            if (tapped >= 0 && tapped != sel)
            {
                sel = tapped;
                ui_sound(SND_MOVE);
                continue;
            }
            if (tapped >= 0)
                k |= KEY_A;
            if (k & (KEY_UP | KEY_DOWN))
                ui_sound(SND_MOVE);
            if (k & KEY_UP)
                sel = (sel + n - 1) % n;
            if (k & KEY_DOWN)
                sel = (sel + 1) % n;
            if (k & KEY_B)
            {
                ui_sound(SND_BACK);
                return;
            }
            if (!(k & KEY_A))
                continue;
            static const UiKey keys[] = { { "A", "Yes, put it back", KEY_A }, { "B", "No", KEY_B } };
            char when[24], text[200];
            format_time(when, sizeof(when), v[sel].time);
            snprintf(text, sizeof(text), "%s, from %.18s.%s%s", when, v[sel].source,
                     it->present ? "\nThe console's save goes to the PC first, so it can come back too." : "",
                     console.backup_only ? "" : "\nYour other consoles are offered it at their next sync.");
            ui_sound(SND_SELECT);
            ui_card("Put this version back?", text, UI_CYAN, keys, 2);
            wait_release();
            u32 yes;
            while ((yes = wait_keys(KEY_A | KEY_B)) == 0)
                ;
            if (yes & KEY_B)
            {
                ui_sound(SND_BACK);
                continue;
            }
            begin("Restoring a save");
            int r = saves_restore(&job, &console, &server, &list, it, v[sel].version, v[sel].source, &counts,
                                  progress, msg, sizeof(msg));
            message(r > 0 ? "Restored" : "Didn't restore", r > 0 ? (msg[0] ? msg : "The save is on the console.")
                                                                 : msg);
            return;
        }
        consoleClear();
        printf("%s\n-------------------------------\n", name);
        for (int i = top; i < n && i < top + list_rows(); i++)
        {
            // When it was saved, its size, and whose it is (the live save: "live")
            char when[24], size[16];
            format_time(when, sizeof(when), v[i].time);
            format_size(size, sizeof(size), v[i].size);
            printf("%c %-12s %-7s %-8.8s\n", i == sel ? '>' : ' ', when, size,
                   v[i].version == 0 ? "live" : v[i].source);
        }
        printf("\x1b[20;0H-------------------------------");
        char from[48];
        snprintf(from, sizeof(from), "%sfrom: %s", v[sel].version == 0 ? "Live, " : "", v[sel].source);
        printf("\x1b[21;0H%-31.31s", from);
        printf("\x1b[22;0HA: put this one on the console");
        printf("\x1b[23;0HB: back");
        u32 k = wait_keys(KEY_UP | KEY_DOWN | KEY_A | KEY_B);
        if (k & KEY_UP)
            sel = (sel + n - 1) % n;
        if (k & KEY_DOWN)
            sel = (sel + 1) % n;
        if (k & KEY_B)
            return;
        if (k & KEY_A)
        {
            consoleClear();
            printf("Put this version on the\nconsole?\n\n%s\n", name);
            char when[24];
            format_time(when, sizeof(when), v[sel].time);
            printf("%s, from: %.18s\n\n", when, v[sel].source);
            if (it->present)
                printf("The console's save now goes\nto the PC first, so it can be\nput back too.\n");
            if (!console.backup_only)
                printf("\nYour other consoles are offered\nit at their next sync.\n");
            printf("\x1b[22;0HA: yes, put it on\x1b[23;0HB: no");
            wait_release();
            if (wait_keys(KEY_A | KEY_B) & KEY_B)
                continue;
            begin("Restoring a save");
            int r = saves_restore(&job, &console, &server, &list, it, v[sel].version, v[sel].source, &counts,
                                  progress, msg, sizeof(msg));
            message(r > 0 ? "Restored" : "Didn't restore", r > 0 ? (msg[0] ? msg : "The save is on the console.")
                                                                 : msg);
            return;
        }
    }
}

// Sync all: the conflicts asked first, then everything to do, then the
// summary.
static void sync_all(void)
{
    for (int i = 0; i < n_shown; i++)
    {
        SaveItem *it = &list.items[shown[i]];
        if (it->action == SA_CONFLICT && !it->excluded && !it->done && it->choice == SC_ASK)
            it->choice = ask_conflict(it);
    }
    int total = 0, at = 0;
    for (int i = 0; i < n_shown; i++)
        total += to_do(&list.items[shown[i]]);
    SaveCounts before = counts;
    int skipped = 0;
    begin("Syncing saves");
    for (int i = 0; i < n_shown; i++)
    {
        SaveItem *it = &list.items[shown[i]];
        if (!to_do(it))
            continue;
        if (it->action == SA_CONFLICT && it->choice != SC_KEEP_CONSOLE && it->choice != SC_TAKE_PC)
        {
            skipped++;
            continue;
        }
        static char title[40];
        snprintf(title, sizeof(title), "Syncing saves (%d of %d)", ++at, total);
        progress_title = title;
        char msg[160];
        saves_sync_item(&job, &console, &server, &list, it, &counts, progress, msg, sizeof(msg));
    }

    char text[200];
    int up = counts.uploaded - before.uploaded, down = counts.downloaded - before.downloaded;
    int backed = counts.backed_up - before.backed_up, failed = counts.failed - before.failed;
    snprintf(text, sizeof(text), "%d backed up%s\n%d taken from the PC\n%d left to decide%s",
             up + backed, backed && !up ? " (back up only)" : "", down, skipped,
             failed ? "" : "\n\nEverything else is in sync.");
    if (failed)
    {
        size_t n = strlen(text);
        snprintf(text + n, sizeof(text) - n, "\n" RED "%d didn't sync" WHITE " (see the list)", failed);
    }
    message_tone("Saves synced", text, failed ? UI_RED : UI_GREEN);
}

// ---------------------------------------------------------------------------

void save_sync_screen(const SaveUi *ui)
{
    memset(&counts, 0, sizeof(counts));
    memcpy(console.mac, ui->mac, 6);
    console.model = ui->console_model;
    console.backup_only = ui->settings->backup_only;
    memset(&job, 0, sizeof(job));
    job.server_addr = settings_server_addr(ui->settings);
    job.console_model = ui->console_model;
    job.cancelled = b_pressed;

    begin("Looking for your saves");
    int found = saves_scan(&list, ui->games_dir, ui->index_dir, progress);
    if (found < 0)
    {
        message("Save sync", "Out of memory.");
        saves_free(&list);
        return;
    }
    if (list.roms == 0)
    {
        char text[160];
        snprintf(text, sizeof(text), "No games in\n%s", ui->games_dir);
        message("Save sync", text);
        saves_free(&list);
        return;
    }

    if (ui_on())
    {
        char text[48];
        snprintf(text, sizeof(text), "%d game%s, %d save%s", list.roms, list.roms == 1 ? "" : "s", found,
                 found == 1 ? "" : "s");
        begin("Asking DSiRPC");
        progress_card(text, 0, 1, 0);
    }
    else
    {
        consoleClear();
        printf("Save sync\n-------------------------------\n");
        printf("%d game(s), %d save(s)\n\nAsking DSiRPC (B: cancel)...\n", list.roms, found);
    }
    char msg[160];
    int r = saves_plan(&job, &console, &list, &server, msg, sizeof(msg));
    if (r <= 0)
    {
        if (r < 0 || msg[0] != '\0')
            message("Save sync", msg[0] ? msg : "DSiRPC wasn't found");
        saves_free(&list);
        return;
    }
    saves_write_index(&list);   // what stage 2 found, so it isn't read again, and what's in sync
    build_shown();

    int sel = 0, top = 0;
    bool synced_all = false;
    keysSetRepeat(15, 4);
    wait_release();
    while (!synced_all)
    {
        int rows = n_shown + 1;
        if (sel < top)
            top = sel;
        if (sel >= top + list_rows())
            top = sel - list_rows() + 1;
        draw_list(sel, top);
        u32 k = wait_keys(KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R | KEY_A | KEY_B | KEY_X | KEY_Y |
                          KEY_START);
        if (tapped >= 0)
        {
            // A tap picks a save, and syncs the one already picked
            if (tapped != sel)
            {
                sel = tapped;
                ui_sound(SND_MOVE);
                continue;
            }
            k |= KEY_A;
        }
        SaveItem *it = sel > 0 ? &list.items[shown[sel - 1]] : NULL;
        if (k & (KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R))
            ui_sound(SND_MOVE);
        else if (k & (KEY_A | KEY_X | KEY_START))
            ui_sound(SND_SELECT);
        else if (k & KEY_Y)
            ui_sound(SND_TOGGLE);
        else if (k & KEY_B)
            ui_sound(SND_BACK);
        if (k & KEY_UP)
            sel = (sel + rows - 1) % rows;
        else if (k & KEY_DOWN)
            sel = (sel + 1) % rows;
        else if (k & (KEY_LEFT | KEY_L))
            sel = sel > list_rows() ? sel - list_rows() : 0;
        else if (k & (KEY_RIGHT | KEY_R))
            sel = sel + list_rows() < rows ? sel + list_rows() : rows - 1;
        else if (k & KEY_START || ((k & KEY_A) && it == NULL))
        {
            sync_all();
            synced_all = true;
        }
        else if ((k & KEY_A) && it != NULL)
        {
            if (it->action == SA_CONFLICT && !it->excluded && !it->done)
                it->choice = ask_conflict(it);
            if (to_do(it) || it->failed)
            {
                it->failed = false;
                sync_one(it);
            }
            wait_release();
        }
        else if ((k & KEY_Y) && it != NULL)
        {
            it->excluded = !it->excluded;
            it->choice = SC_ASK;
            saves_write_index(&list);
            if (it->excluded)
            {
                it->action = SA_EXCLUDED;
            }
            else
            {
                // Back in: what to do with it is DSiRPC's call again
                if (ui_on())
                {
                    begin("Asking DSiRPC");
                    progress_card("what to do with it", 0, 1, 0);
                }
                else
                {
                    consoleClear();
                    printf("Asking DSiRPC...\n");
                }
                if (saves_plan(&job, &console, &list, &server, msg, sizeof(msg)) > 0)
                {
                    saves_write_index(&list);
                    build_shown();
                }
                else
                    message("Save sync", msg[0] ? msg : "DSiRPC wasn't found");
                if (sel > n_shown)
                    sel = n_shown;
            }
        }
        else if ((k & KEY_X) && it != NULL)
        {
            versions_screen(it);
            wait_release();
        }
        else if (k & KEY_B)
        {
            break;
        }
    }

    if (counts.uploaded || counts.downloaded || counts.backed_up || counts.failed)
        saves_done(&job, &console, &server, &counts);
    free(shown);
    shown = NULL;
    saves_free(&list);
    top_dsi();
}
