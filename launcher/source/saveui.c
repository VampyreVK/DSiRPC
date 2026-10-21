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
//   Newer on the PC (3DS 3F21)     the selected save
//   A:sync Y:leave out X:restore
//   START:sync all  B:back
//
//   Up/Down: move   L/R or Left/Right: a page   A: sync the one picked
//   (or all, on Sync all)   START: sync all   Y: leave out / include
//   X: the versions the PC keeps (restore one)   B: back to the launcher

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include <nds.h>

#include "saveui.h"
#include "savesync.h"

#define LIST_ROWS        17
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
        u32 down = keysDownRepeat() & keys;
        if (down)
            return down;
    }
}

static void message(const char *title, const char *text)
{
    consoleClear();
    printf("%s\n-------------------------------\n%s\n\nPress A\n", title, text);
    wait_release();
    wait_keys(KEY_A | KEY_B | KEY_START);
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
    if (it->excluded || it->done)
        return false;
    switch (it->action)
    {
    case SA_UPLOAD:
    case SA_BACKUP:
    case SA_CONFLICT:
        return true;
    case SA_DOWNLOAD:
    case SA_DOWNLOAD_NEW:
        return !console.backup_only;
    default:
        return false;
    }
}

// ---------------------------------------------------------------------------
// Progress

static const char *progress_title = "";

static void progress(const char *what, uint32_t done, uint32_t total)
{
    static int last_pct = -1;
    int pct = total ? (int)((uint64_t)done * 100 / total) : -1;
    if (total && pct == last_pct && done != 0)
        return;
    last_pct = pct;
    printf("\x1b[0;0H%-31.31s\n-------------------------------\n", progress_title);
    printf("\x1b[3;0H%-31.31s\n", what);
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
            snprintf(out, outsz, "Newer on the PC: %s", when);
            break;
        case SA_DOWNLOAD_NEW:
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

static void draw_list(int sel, int top)
{
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
        char text[64];
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

    consoleClear();
    printf(YELLOW "Both saves changed" WHITE "\n");
    printf("-------------------------------\n");
    printf("%s\n\n", name);
    printf("This %s: %s\n", self, here);
    printf("          %s\n", size_here);
    printf("The PC:   %s\n", there);
    printf("          %s\n", size_there);
    if (it->pc_source[0] != '\0')
        printf("  (from the %.18s)\n", it->pc_source);
    printf("\nThe one you don't pick stays\nin the PC's backup history.\n");
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
    consoleClear();
    progress_title = "Syncing saves";
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

static void versions_screen(SaveItem *it)
{
    static SaveVersion v[SAVE_MAX_VERSIONS];
    char msg[160];
    consoleClear();
    printf("Asking DSiRPC for the\nversions it keeps...\n");
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
        if (sel >= top + LIST_ROWS)
            top = sel - LIST_ROWS + 1;
        char name[33];
        item_name(name, sizeof(name), it, 32);
        consoleClear();
        printf("%s\n-------------------------------\n", name);
        for (int i = top; i < n && i < top + LIST_ROWS; i++)
        {
            char when[24], size[16];
            format_time(when, sizeof(when), v[i].time);
            format_size(size, sizeof(size), v[i].size);
            printf("%c %-12s %-7s %s\n", i == sel ? '>' : ' ', when, size, v[i].version == 0 ? "latest" : "");
        }
        printf("\x1b[20;0H-------------------------------");
        printf("\x1b[21;0HFrom the %-23.23s", v[sel].source);
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
            printf("%s, from the %.18s\n\n", when, v[sel].source);
            if (it->present)
                printf("The console's save now goes\nto the PC first, so it can be\nput back too.\n");
            if (!console.backup_only)
                printf("\nYour other consoles get it at\ntheir next sync.\n");
            printf("\x1b[22;0HA: yes, put it on\x1b[23;0HB: no");
            wait_release();
            if (wait_keys(KEY_A | KEY_B) & KEY_B)
                continue;
            consoleClear();
            progress_title = "Restoring a save";
            int r = saves_restore(&job, &console, &server, &list, it, v[sel].version, &counts, progress, msg,
                                  sizeof(msg));
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
    consoleClear();
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
    message("Saves synced", text);
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

    consoleClear();
    progress_title = "Looking for your saves";
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

    consoleClear();
    printf("Save sync\n-------------------------------\n");
    printf("%d game(s), %d save(s)\n\nAsking DSiRPC (B: cancel)...\n", list.roms, found);
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
        if (sel >= top + LIST_ROWS)
            top = sel - LIST_ROWS + 1;
        draw_list(sel, top);
        u32 k = wait_keys(KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R | KEY_A | KEY_B | KEY_X | KEY_Y |
                          KEY_START);
        SaveItem *it = sel > 0 ? &list.items[shown[sel - 1]] : NULL;
        if (k & KEY_UP)
            sel = (sel + rows - 1) % rows;
        else if (k & KEY_DOWN)
            sel = (sel + 1) % rows;
        else if (k & (KEY_LEFT | KEY_L))
            sel = sel > LIST_ROWS ? sel - LIST_ROWS : 0;
        else if (k & (KEY_RIGHT | KEY_R))
            sel = sel + LIST_ROWS < rows ? sel + LIST_ROWS : rows - 1;
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
                consoleClear();
                printf("Asking DSiRPC...\n");
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
}
