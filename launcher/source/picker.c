// SPDX-License-Identifier: MIT
//
// The modern look's game picker (see picker.h). The bottom screen lists the
// games, six at a time, each with its banner icon (half size), its name and
// its achievements; the top screen has the picked one's details.
//
//   Up/Down: move   Left/Right: a page   A: start it   B or SELECT: back
//   X: its achievements   Y: a favorite (or not)   L/R: the order
//   START: the game last started   a tap: pick a game (a second one: start it)
//
// The achievement list (X) is the game's set on the SD card (sets/CODE.DRS,
// the list DSiRPC puts in it for nds-bootstrap's in-game menu), with the
// unlocks waiting in RPCUNLK.BIN marked: unlocked here, waiting for DSiRPC.
//
// games.idx, written whole when something in it changes:
//
//   DSiRPC games 1
//   <size> <mtime> <last started> <favorite> <code> <version> <path>\t<name>\t<publisher>

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <time.h>

#include <nds.h>

#include "picker.h"
#include "stats.h"
#include "sync.h"
#include "topscreen.h"

#define PATH_LEN        256
#define TITLE_LEN       64
#define PUBLISHER_LEN   32
#define MAX_GAMES       1024
#define MAX_DEPTH       4
#define ROWS            6
#define ROW_H           24
#define LIST_Y          (UI_BAR_H + 3)
#define INDEX_MAGIC     "DSiRPC games 1"
#define UNIX_TIME_2000  946684800
#define UNLOCK_SLOT     16
#define UNLOCK_SLOTS    256
#define SET_HEADER_SIZE 64
#define MAX_LIST        (256 * 1024)

typedef struct
{
    char path[PATH_LEN];
    char title[TITLE_LEN];
    char publisher[PUBLISHER_LEN];
    char code[5];
    uint8_t version;
    uint32_t size;
    int32_t mtime;
    uint32_t last;              // started from the launcher, seconds since 2000 (0: never)
    uint32_t played;            // last played as far as anyone knows (the PC's playtimes too)
    bool favorite;
    bool read;                  // its header and banner were read (or came from games.idx)
    UiBanner *icon;             // read when it's first shown
    bool icon_tried;
    int earned, total;          // achievements (total -1: not counted yet, 0: no set)
} Game;

static Game *games;
static int n_games, cap_games;
static int *order;              // games' indexes, in the order shown
static int sort_mode;
static StatsList stats;
static uint32_t *pending;       // achievement IDs waiting in RPCUNLK.BIN
static int n_pending;
static int bank;                // which half of the banner palette slots is shown

static const char *const SORT_NAMES[SORTS] = { "Recent", "A-Z", "Favorites" };
static const char *const STAR[7] = {
    "...1...", "...1...", "1111111", ".11111.", "..111..", ".11.11.", ".1...1.",
};

// ---------------------------------------------------------------------------
// Little helpers

static uint16_t get16(const uint8_t *p)
{
    return p[0] | (p[1] << 8);
}

static uint32_t get32(const uint8_t *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool valid_code(const char *c)
{
    for (int i = 0; i < 4; i++)
    {
        if (!((c[i] >= 'A' && c[i] <= 'Z') || (c[i] >= '0' && c[i] <= '9')))
            return false;
    }
    return true;
}

static void join_path(char *out, size_t outsz, const char *dir, const char *name)
{
    size_t n = strlen(dir);
    snprintf(out, outsz, (n > 0 && dir[n - 1] == '/') ? "%s%s" : "%s/%s", dir, name);
}

static bool is_dir(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISDIR(st.st_mode);
}

static bool is_nds(const char *name)
{
    size_t n = strlen(name);
    return n > 4 && strcasecmp(name + n - 4, ".nds") == 0;
}

static uint32_t now_2000(void)
{
    time_t t = time(NULL);
    return t > UNIX_TIME_2000 ? (uint32_t)(t - UNIX_TIME_2000) : 0;
}

// The file's name without its folder or ".nds"
static void file_title(char *out, size_t outsz, const char *path)
{
    const char *name = strrchr(path, '/');
    snprintf(out, outsz, "%.*s", (int)outsz - 1, name != NULL ? name + 1 : path);
    size_t n = strlen(out);
    if (is_nds(out))
        out[n - 4] = '\0';
}

// ---------------------------------------------------------------------------
// A game's header and banner

// Its code and version (the header), and its banner's icon and English name
// (its lines but the last, joined) and publisher (the last line)
static bool read_rom(const char *path, char code[5], uint8_t *version, UiBanner *icon, char *title, size_t tsz,
                     char *publisher, size_t psz)
{
    static uint8_t b[0x440];
    uint8_t hdr[0x70];
    if (icon != NULL)
        icon->ok = false;
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return false;
    bool ok = fread(hdr, 1, sizeof(hdr), f) == sizeof(hdr);
    uint32_t at = ok ? get32(hdr + 0x68) : 0;
    bool banner = ok && at != 0 && fseek(f, (long)at, SEEK_SET) == 0 && fread(b, 1, sizeof(b), f) == sizeof(b);
    fclose(f);
    if (!ok)
        return false;
    if (code != NULL)
    {
        code[0] = '\0';
        if (valid_code((const char *)hdr + 0x0C))
        {
            memcpy(code, hdr + 0x0C, 4);
            code[4] = '\0';
        }
    }
    if (version != NULL)
        *version = hdr[0x1E];
    if (!banner)
        return false;

    if (icon != NULL)
    {
        // 4x4 tiles of 8x8, 4 bits a pixel (the low nibble on the left)
        for (int t = 0; t < 16; t++)
        {
            for (int row = 0; row < 8; row++)
            {
                for (int col = 0; col < 4; col++)
                {
                    uint8_t v = b[0x20 + t * 32 + row * 4 + col];
                    int x = (t % 4) * 8 + col * 2, y = (t / 4) * 8 + row;
                    icon->px[y * 32 + x] = v & 15;
                    icon->px[y * 32 + x + 1] = v >> 4;
                }
            }
        }
        for (int i = 0; i < 16; i++)
            icon->pal[i] = get16(b + 0x220 + i * 2);
        icon->ok = true;
    }

    // The English name, UTF-16, its lines split at '\n'
    char lines[3][TITLE_LEN];
    int n_lines = 0, len = 0;
    memset(lines, 0, sizeof(lines));
    for (int i = 0; i < 128; i++)
    {
        uint16_t ch = get16(b + 0x340 + i * 2);
        if (ch == 0)
            break;
        if (ch == '\n')
        {
            if (n_lines < 2)
            {
                n_lines++;
                len = 0;
            }
            continue;
        }
        if (len < TITLE_LEN - 1)
            lines[n_lines][len++] = ui_ascii(ch);
    }
    n_lines++;
    while (n_lines > 1 && lines[n_lines - 1][0] == '\0')
        n_lines--;
    if (title != NULL)
    {
        title[0] = '\0';
        int names = n_lines > 1 ? n_lines - 1 : 1;
        for (int i = 0; i < names; i++)
        {
            size_t at_t = strlen(title);
            snprintf(title + at_t, tsz - at_t, "%s%s", i ? " " : "", lines[i]);
        }
    }
    if (publisher != NULL)
        snprintf(publisher, psz, "%s", n_lines > 1 ? lines[n_lines - 1] : "");
    return true;
}

bool picker_banner(const char *path, UiBanner *icon, char *title, size_t tsz, char *publisher, size_t psz)
{
    return read_rom(path, NULL, NULL, icon, title, tsz, publisher, psz);
}

// ---------------------------------------------------------------------------
// games.idx

static int cmp_path(const void *a, const void *b)
{
    return strcasecmp(((const Game *)a)->path, ((const Game *)b)->path);
}

// Its entries, sorted by path (malloc'd), or NULL
static Game *load_index(const char *index_dir, int *count)
{
    *count = 0;
    char path[PATH_LEN + 16], line[PATH_LEN + TITLE_LEN + PUBLISHER_LEN + 64];
    join_path(path, sizeof(path), index_dir, PICKER_INDEX);
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return NULL;
    if (fgets(line, sizeof(line), f) == NULL || strncmp(line, INDEX_MAGIC, strlen(INDEX_MAGIC)) != 0)
    {
        fclose(f);
        return NULL;
    }
    Game *index = NULL;
    int cap = 0;
    while (fgets(line, sizeof(line), f) != NULL && *count < MAX_GAMES)
    {
        line[strcspn(line, "\r\n")] = '\0';
        unsigned size, last;
        int mtime, fav, ver, at = 0;
        char code[8];
        if (sscanf(line, "%u %d %u %d %7s %d %n", &size, &mtime, &last, &fav, code, &ver, &at) != 6 || at == 0)
            continue;
        if (*count == cap)
        {
            int ncap = cap ? cap * 2 : 64;
            Game *more = realloc(index, (size_t)ncap * sizeof(Game));
            if (more == NULL)
                break;
            index = more;
            cap = ncap;
        }
        Game *g = &index[*count];
        memset(g, 0, sizeof(*g));
        char *p = line + at, *tab = strchr(p, '\t');
        if (tab != NULL)
            *tab = '\0';
        snprintf(g->path, sizeof(g->path), "%s", p);
        if (tab != NULL)
        {
            p = tab + 1;
            tab = strchr(p, '\t');
            if (tab != NULL)
                *tab = '\0';
            snprintf(g->title, sizeof(g->title), "%s", p);
            if (tab != NULL)
                snprintf(g->publisher, sizeof(g->publisher), "%s", tab + 1);
        }
        g->size = size;
        g->mtime = mtime;
        g->last = last;
        g->favorite = fav != 0;
        g->version = (uint8_t)ver;
        if (strlen(code) == 4 && valid_code(code))
            memcpy(g->code, code, 5);
        (*count)++;
    }
    fclose(f);
    if (*count > 1)
        qsort(index, *count, sizeof(Game), cmp_path);
    return index;
}

static Game *find_entry(Game *index, int count, const char *path)
{
    if (index == NULL)
        return NULL;
    Game key;
    snprintf(key.path, sizeof(key.path), "%s", path);
    return bsearch(&key, index, count, sizeof(Game), cmp_path);
}

static bool write_index(const char *index_dir, const Game *list, int count)
{
    char path[PATH_LEN + 16], tmp[PATH_LEN + 24];
    join_path(path, sizeof(path), index_dir, PICKER_INDEX);
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *f = fopen(tmp, "wb");
    if (f == NULL)
        return false;
    fprintf(f, "%s\n", INDEX_MAGIC);
    for (int i = 0; i < count; i++)
    {
        const Game *g = &list[i];
        fprintf(f, "%u %d %u %d %s %d %s\t%s\t%s\n", (unsigned)g->size, (int)g->mtime, (unsigned)g->last,
                g->favorite ? 1 : 0, g->code[0] ? g->code : "-", g->version, g->path, g->title, g->publisher);
    }
    if (fclose(f) != 0)
    {
        remove(tmp);
        return false;
    }
    remove(path);
    return rename(tmp, path) == 0;
}

void picker_started(const char *index_dir, const char *path)
{
    int count;
    Game *index = load_index(index_dir, &count);
    Game *e = find_entry(index, count, path);
    if (e == NULL)
    {
        // Not listed yet (START before the picker was ever opened): a bare
        // entry, its name read the next time the picker opens
        Game *more = realloc(index, (size_t)(count + 1) * sizeof(Game));
        struct stat st;
        if (more == NULL || stat(path, &st) != 0)
        {
            free(more != NULL ? more : index);
            return;
        }
        index = more;
        e = &index[count++];
        memset(e, 0, sizeof(*e));
        snprintf(e->path, sizeof(e->path), "%s", path);
        e->size = (uint32_t)st.st_size;
        e->mtime = (int32_t)st.st_mtime;
    }
    e->last = now_2000();
    write_index(index_dir, index, count);
    free(index);
}

// ---------------------------------------------------------------------------
// Finding the games

static Game *add_game(void)
{
    if (n_games == cap_games)
    {
        int ncap = cap_games ? cap_games * 2 : 64;
        Game *more = realloc(games, (size_t)ncap * sizeof(Game));
        if (more == NULL)
            return NULL;
        games = more;
        cap_games = ncap;
    }
    Game *g = &games[n_games++];
    memset(g, 0, sizeof(*g));
    g->total = -1;
    return g;
}

static void scan_dir(const char *dir, int depth, const char *launcher_dir)
{
    DIR *d = opendir(dir);
    if (d == NULL)
        return;
    struct dirent *e;
    while ((e = readdir(d)) != NULL && n_games < MAX_GAMES)
    {
        // Like the save sync: not hidden files, "_nds" and the like, or
        // saves; nor the launcher's own folder (sd:/roms/nds/DSiRPC, with
        // the games): the launcher and our nds-bootstrap aren't games
        if (e->d_name[0] == '.')
            continue;
        char path[PATH_LEN];
        join_path(path, sizeof(path), dir, e->d_name);
        bool sub = e->d_type == DT_DIR || (e->d_type == DT_UNKNOWN && is_dir(path));
        if (sub)
        {
            if (depth < MAX_DEPTH && e->d_name[0] != '_' && strcasecmp(e->d_name, "saves") != 0 &&
                strcasecmp(path, launcher_dir) != 0)
                scan_dir(path, depth + 1, launcher_dir);
            continue;
        }
        struct stat st;
        if (!is_nds(e->d_name) || stat(path, &st) != 0)
            continue;
        Game *g = add_game();
        if (g == NULL)
            break;
        snprintf(g->path, sizeof(g->path), "%s", path);
        g->size = (uint32_t)st.st_size;
        g->mtime = (int32_t)st.st_mtime;
    }
    closedir(d);
}

// The first time (and for new games): a card with how far it got
static void reading(int done, int total)
{
    Canvas *c = ui_screen();
    char text[48];
    snprintf(text, sizeof(text), "%d of %d", done, total);
    ui_clear();
    ui_header("Games");
    ui_panel(10, 66, UI_W - 20, 56, UI_CYAN);
    ui_text(c, 20, 75, "Reading your games", UI_CYAN);
    ui_text(c, 20, 89, text, UI_SOFT);
    ui_bar(c, 20, 104, UI_W - 40, 8, total ? done * 100 / total : 0, UI_CYAN);
    ui_present();
}

// The unlocks waiting in RPCUNLK.BIN (only their IDs: those are unique)
static void load_pending(const char *path)
{
    static uint8_t buf[UNLOCK_SLOT * UNLOCK_SLOTS];
    free(pending);
    pending = NULL;
    n_pending = 0;
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return;
    size_t n = fread(buf, 1, sizeof(buf), f);
    fclose(f);
    if (n < UNLOCK_SLOT || memcmp(buf, "DRUL", 4) != 0)
        return;
    pending = malloc(UNLOCK_SLOTS * sizeof(uint32_t));
    if (pending == NULL)
        return;
    for (size_t i = 1; i < n / UNLOCK_SLOT; i++)
    {
        // sync.c's count_unlocks() test: an ID, a code and the check
        const uint8_t *s = buf + i * UNLOCK_SLOT;
        uint32_t sum = 0x5AA5;
        for (int w = 0; w < 7; w++)
            sum += get16(s + w * 2);
        if (get32(s) != 0 && valid_code((const char *)s + 4) && (sum & 0xFFFF) == get16(s + 14))
            pending[n_pending++] = get32(s);
    }
}

static bool is_pending(uint32_t id)
{
    for (int i = 0; i < n_pending; i++)
    {
        if (pending[i] == id)
            return true;
    }
    return false;
}

// Loads the games: the folder, then games.idx for what's known, the banners
// of the rest, and the PC's playtimes
static bool load_games(const PickerUi *ui)
{
    n_games = 0;
    scan_dir(ui->games_dir, 0, ui->index_dir);
    int count;
    Game *index = load_index(ui->index_dir, &count);
    int to_read = 0;
    for (int i = 0; i < n_games; i++)
    {
        Game *g = &games[i];
        Game *e = find_entry(index, count, g->path);
        if (e == NULL)
        {
            to_read++;
            continue;
        }
        g->last = e->last;
        g->favorite = e->favorite;
        if (e->size == g->size && e->mtime == g->mtime && e->title[0] != '\0')
        {
            memcpy(g->title, e->title, sizeof(g->title));
            memcpy(g->publisher, e->publisher, sizeof(g->publisher));
            memcpy(g->code, e->code, sizeof(g->code));
            g->version = e->version;
            g->read = true;
        }
        else
        {
            to_read++;
        }
    }
    free(index);

    bool changed = to_read > 0 || count != n_games;
    int done = 0;
    for (int i = 0; i < n_games; i++)
    {
        Game *g = &games[i];
        if (g->read)
            continue;
        if (done % 4 == 0)
            reading(done, to_read);
        if (!read_rom(g->path, g->code, &g->version, NULL, g->title, sizeof(g->title), g->publisher,
                      sizeof(g->publisher)) ||
            g->title[0] == '\0')
            file_title(g->title, sizeof(g->title), g->path);
        g->read = true;
        done++;
    }
    if (changed)
        write_index(ui->index_dir, games, n_games);

    stats_free(&stats);
    stats_load(ui->index_dir, &stats);
    for (int i = 0; i < n_games; i++)
    {
        Game *g = &games[i];
        const GameStats *st = g->code[0] ? stats_find(&stats, g->code) : NULL;
        g->played = st != NULL && st->last > g->last ? st->last : g->last;
    }
    load_pending(ui->unlocks_path);
    return true;
}

static void free_games(void)
{
    for (int i = 0; i < n_games; i++)
        free(games[i].icon);
    free(games);
    games = NULL;
    n_games = cap_games = 0;
    free(order);
    order = NULL;
    stats_free(&stats);
    free(pending);
    pending = NULL;
    n_pending = 0;
}

static int cmp_order(const void *a, const void *b)
{
    const Game *x = &games[*(const int *)a], *y = &games[*(const int *)b];
    if (sort_mode == SORT_FAVORITES && x->favorite != y->favorite)
        return x->favorite ? -1 : 1;
    if (sort_mode == SORT_RECENT && x->played != y->played)
        return x->played > y->played ? -1 : 1;
    int c = strcasecmp(x->title, y->title);
    return c != 0 ? c : strcasecmp(x->path, y->path);
}

static void sort_games(void)
{
    for (int i = 0; i < n_games; i++)
        order[i] = i;
    if (n_games > 1)
        qsort(order, n_games, sizeof(int), cmp_order);
}

// ---------------------------------------------------------------------------
// A game's achievements

typedef struct
{
    uint8_t *data;              // the list section, malloc'd
    int count;
    const uint8_t *entries;     // count x 16 bytes
    const char *text;
    uint32_t text_size;
} CheevoList;

static bool load_list(const char *sets_dir, const char *code, CheevoList *out)
{
    memset(out, 0, sizeof(*out));
    if (!valid_code(code))
        return false;
    char path[PATH_LEN], name[16];
    snprintf(name, sizeof(name), "%.4s.DRS", code);
    join_path(path, sizeof(path), sets_dir, name);
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return false;
    uint8_t h[SET_HEADER_SIZE];
    bool ok = fread(h, 1, sizeof(h), f) == sizeof(h) && memcmp(h, "DRSE", 4) == 0 && get16(h + 4) >= 3 &&
              memcmp(h + 8, code, 4) == 0;
    // (the list came in version 3, after the header and the programs)
    uint32_t list_at = ok ? get16(h + 6) + get32(h + 24) + get32(h + 36) : 0;
    uint32_t list_size = ok ? get32(h + 32) : 0;
    if (ok && (list_size < 16 || list_size > MAX_LIST || fseek(f, (long)list_at, SEEK_SET) != 0))
        ok = false;
    if (ok && (out->data = malloc(list_size)) != NULL && fread(out->data, 1, list_size, f) == list_size &&
        memcmp(out->data, "DRMN", 4) == 0)
    {
        out->count = get16(out->data + 6);
        out->text_size = get32(out->data + 8);
        if (16 + (uint32_t)out->count * 16 + out->text_size <= list_size)
        {
            out->entries = out->data + 16;
            out->text = (const char *)out->entries + out->count * 16;
        }
    }
    fclose(f);
    if (out->entries == NULL)
    {
        free(out->data);
        memset(out, 0, sizeof(*out));
        return false;
    }
    return true;
}

static const char *list_text(const CheevoList *l, uint16_t at)
{
    if (at >= l->text_size)
        return "";
    // (NUL-terminated by DSiRPC; the last one is checked)
    return memchr(l->text + at, '\0', l->text_size - at) != NULL ? l->text + at : "";
}

// 1 earned (as DSiRPC knew at the last sync), 2 unlocked here and waiting
// for DSiRPC, 0 not yet
static int cheevo_state(const uint8_t *e)
{
    if (e[13] & 1)
        return 1;
    return is_pending(get32(e)) ? 2 : 0;
}

static void count_achievements(Game *g, const char *sets_dir)
{
    CheevoList l;
    g->total = 0;
    g->earned = 0;
    if (!load_list(sets_dir, g->code, &l))
        return;
    g->total = l.count;
    for (int i = 0; i < l.count; i++)
        g->earned += cheevo_state(l.entries + i * 16) != 0;
    free(l.data);
}

// "41h 12m", "12m", or "" for nothing
static void format_playtime(char *out, size_t outsz, uint32_t secs)
{
    if (secs < 60)
        snprintf(out, outsz, "%s", secs ? "under a minute" : "");
    else if (secs < 3600)
        snprintf(out, outsz, "%um", (unsigned)(secs / 60));
    else
        snprintf(out, outsz, "%uh %02um", (unsigned)(secs / 3600), (unsigned)(secs / 60 % 60));
}

static void show_cheevo(const Game *g, const CheevoList *l, int i)
{
    const uint8_t *e = l->entries + i * 16;
    TopCheevo t = {
        .game = g->title,
        .title = list_text(l, get16(e + 8)),
        .description = list_text(l, get16(e + 10)),
        .points = e[12],
        .state = cheevo_state(e),
        .when = get32(e + 4),
    };
    top_cheevo(&t);
}

enum { SHOW_ALL, SHOW_LEFT, SHOW_EARNED, SHOWS };

static void achievements_screen(Game *g, const char *sets_dir)
{
    static const char *const SHOW_NAMES[SHOWS] = { "All", "To earn", "Earned" };
    CheevoList l;
    if (!load_list(sets_dir, g->code, &l))
    {
        static const UiKey keys[] = { { "A", "Back", KEY_A } };
        ui_sound(SND_ERROR);
        ui_card("No achievements here yet",
                "DSiRPC puts a game's set on the SD card when the game is started while it's around.", UI_AMBER,
                keys, 1);
        ui_release();
        ui_wait(KEY_A | KEY_B);
        ui_sound(SND_BACK);
        return;
    }
    int *shown = malloc(sizeof(int) * (l.count ? l.count : 1));
    if (shown == NULL)
    {
        free(l.data);
        return;
    }
    const GameStats *st = stats_find(&stats, g->code);
    int show = SHOW_ALL, sel = 0, top = 0, n = 0, earned = 0;
    for (int i = 0; i < l.count; i++)
        earned += cheevo_state(l.entries + i * 16) != 0;
    const int rows = 5, row_h = 26, y0 = UI_BAR_H + 14;
    bool rebuild = true;
    ui_release();
    while (1)
    {
        if (rebuild)
        {
            n = 0;
            for (int i = 0; i < l.count; i++)
            {
                int s = cheevo_state(l.entries + i * 16);
                if (show == SHOW_ALL || (show == SHOW_LEFT && s == 0) || (show == SHOW_EARNED && s != 0))
                    shown[n++] = i;
            }
            sel = top = 0;
            rebuild = false;
        }
        if (sel < top)
            top = sel;
        if (sel >= top + rows)
            top = sel - rows + 1;

        Canvas *c = ui_screen();
        char line[64], when[32];
        ui_clear();
        ui_header(NULL);
        snprintf(line, sizeof(line), "%d/%d", earned, l.count);
        int rx = ui_header_right(line, earned == l.count ? UI_GREEN : UI_DIM);
        ui_text_fit(c, 8, 5, g->title, rx - 16, UI_SOFT);
        // The playtime, under the header
        format_playtime(when, sizeof(when), st != NULL ? st->seconds : 0);
        if (when[0] != '\0')
            snprintf(line, sizeof(line), "Played for %s", when);
        else
            snprintf(line, sizeof(line), "No playtime from DSiRPC yet");
        ui_text_fit(c, 8, UI_BAR_H + 2, line, UI_W - 16, UI_DIM);
        for (int row = 0; row < rows && top + row < n; row++)
        {
            int i = shown[top + row], y = y0 + row * row_h;
            const uint8_t *e = l.entries + i * 16;
            int s = cheevo_state(e);
            if (top + row == sel)
            {
                ui_fill(c, 4, y, UI_W - 16, row_h - 2, UI_GREEN);
                ui_fill(c, 6, y + 2, UI_W - 20, row_h - 6, UI_PANEL);
            }
            if (s == 1)
                ui_icon(c, 10, y + 6, STEP_DONE, UI_GREEN, UI_GREEN_DARK);
            else if (s == 2)
                ui_icon(c, 10, y + 6, STEP_DONE, UI_AMBER, UI_AMBER_DARK);
            else
                ui_icon(c, 10, y + 6, STEP_WAITING, UI_SCROLL, 0);
            char pts[8];
            snprintf(pts, sizeof(pts), "%d", e[12]);
            int pw = ui_chip_width(pts);
            ui_chip(c, UI_W - 16 - pw, y + 5, pts, UI_CHIP, UI_SOFT);
            ui_text_fit(c, 28, y + 3, list_text(&l, get16(e + 8)), UI_W - 16 - pw - 34, s ? UI_TEXT : UI_SOFT);
            ui_text_fit(c, 28, y + 13, list_text(&l, get16(e + 10)), UI_W - 16 - pw - 34, UI_DIM);
            ui_touch_add(4, y, UI_W - 16, row_h - 2, top + row);
        }
        if (n == 0)
            ui_text_center(c, UI_W / 2, 90, show == SHOW_LEFT ? "All earned!" : "None yet", UI_DIM);
        ui_scrollbar(UI_W - 8, y0, rows * row_h - 2, top, rows, n);
        snprintf(line, sizeof(line), "Show: %s", SHOW_NAMES[show]);
        UiKey keys[] = { { "B", "Back", KEY_B }, { "L/R", line, KEY_R } };
        ui_footer(keys, 2);
        ui_present();
        if (n > 0)
            show_cheevo(g, &l, shown[sel]);

        uint32_t k;
        int tap;
        do
        {
            sync_frame();
            scanKeys();
            k = (keysDownRepeat() & (KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R | KEY_B | KEY_A)) |
                ui_footer_key();
            tap = ui_tapped();
        } while (k == 0 && tap < 0);
        int old = sel;
        if (tap >= 0)
            sel = tap;
        if (k & KEY_UP)
            sel = sel > 0 ? sel - 1 : (n > 0 ? n - 1 : 0);
        if (k & KEY_DOWN)
            sel = sel + 1 < n ? sel + 1 : 0;
        if (k & KEY_LEFT)
            sel = sel > rows ? sel - rows : 0;
        if (k & KEY_RIGHT)
            sel = sel + rows < n ? sel + rows : (n > 0 ? n - 1 : 0);
        if (sel != old)
            ui_sound(SND_MOVE);
        if (k & (KEY_L | KEY_R))
        {
            show = (show + ((k & KEY_R) ? 1 : SHOWS - 1)) % SHOWS;
            rebuild = true;
            ui_sound(SND_TOGGLE);
        }
        if (k & KEY_B)
        {
            ui_sound(SND_BACK);
            break;
        }
    }
    free(shown);
    free(l.data);
}

// ---------------------------------------------------------------------------
// The list

static void show_game(const Game *g)
{
    const GameStats *st = g->code[0] ? stats_find(&stats, g->code) : NULL;
    TopGame t = {
        .icon = g->icon,
        .title = g->title,
        .publisher = g->publisher,
        .code = g->code,
        .version = g->version,
        .earned = g->earned,
        .total = g->total > 0 ? g->total : 0,
        .playtime = st != NULL ? st->seconds : 0,
        .last_played = g->played,
        .now = now_2000(),
        .favorite = g->favorite,
    };
    top_game(&t);
}

static void draw_row(int row, int index, bool sel, const PickerUi *ui)
{
    Canvas *c = ui_screen();
    int y = LIST_Y + row * ROW_H;
    if (index >= n_games)
        return;
    Game *g = &games[order[index]];
    if (sel)
    {
        ui_fill(c, 4, y, UI_W - 16, ROW_H - 2, UI_GREEN);
        ui_fill(c, 6, y + 2, UI_W - 20, ROW_H - 6, UI_PANEL);
    }
    if (!g->icon_tried)
    {
        g->icon_tried = true;
        g->icon = malloc(sizeof(UiBanner));
        if (g->icon != NULL && !read_rom(g->path, NULL, NULL, g->icon, NULL, 0, NULL, 0))
        {
            free(g->icon);
            g->icon = NULL;
        }
    }
    if (g->icon != NULL)
        ui_banner_half(c, 10, y + 3, g->icon, ui_banner_slot(bank * ROWS + row, g->icon));
    else
        ui_round(c, 10, y + 3, 16, 16, 2, UI_CHIP);

    // Its achievements on the right (counted when first shown), its name
    // in what's left
    if (g->total < 0)
        count_achievements(g, ui->sets_dir);
    char badge[16];
    int right = UI_W - 16, bw;
    if (g->total > 0)
    {
        bool all = g->earned == g->total;
        snprintf(badge, sizeof(badge), "%d/%d", g->earned, g->total);
        bw = ui_chip_width(badge);
        ui_chip(c, right - bw, y + 5, badge, all ? UI_GREEN : UI_CHIP, all ? UI_GREEN_DARK : UI_SOFT);
    }
    else
    {
        bw = ui_text_width("no set");
        ui_text(c, right - bw, y + 7, "no set", UI_DIM);
    }
    int nx = 32;
    if (g->favorite)
    {
        const uint8_t star[4] = { UI_AMBER, 0, 0, 0 };
        ui_art(c, nx, y + 7, STAR, 7, star);
        nx += 10;
    }
    ui_text_fit(c, nx, y + 7, g->title, right - bw - 6 - nx, UI_TEXT);
    ui_touch_add(4, y, UI_W - 16, ROW_H - 2, index);
}

static void draw_list(int sel, int top, const PickerUi *ui)
{
    Canvas *c = ui_screen();
    ui_clear();
    ui_header(NULL);
    char pos[24];
    snprintf(pos, sizeof(pos), "%d/%d", n_games ? sel + 1 : 0, n_games);
    int x = ui_text(c, 8, 5, "Games", UI_SOFT);
    ui_text(c, x + 6, 5, pos, UI_DIM);
    // The order between L and R's caps (a tap on it: the next one)
    int cw = ui_chip_width(SORT_NAMES[sort_mode]), lw = ui_text_width("L") + 6, rw = ui_text_width("R") + 6;
    int sx = UI_W - 6 - rw - 3 - cw - 3 - lw;
    ui_key_cap(c, sx, 3, "L");
    ui_chip(c, sx + lw + 3, 3, SORT_NAMES[sort_mode], UI_CHIP, UI_TEXT);
    ui_key_cap(c, sx + lw + 3 + cw + 3, 3, "R");
    ui_touch_add(sx, 0, UI_W - sx, UI_BAR_H, -2);

    bank ^= 1;      // the new icons' colors in the slots not on the screen
    for (int row = 0; row < ROWS; row++)
        draw_row(row, top + row, top + row == sel, ui);
    ui_scrollbar(UI_W - 8, LIST_Y, ROWS * ROW_H - 2, top, ROWS, n_games);
    static const UiKey keys[] = { { "A", "Play", KEY_A }, { "X", "Achievements", KEY_X }, { "Y", "Favorite", KEY_Y } };
    ui_footer(keys, 3);
    ui_present();
}

bool pick_game(const PickerUi *ui, char *out, size_t outsz)
{
    sort_mode = ui->settings->game_sort < SORTS ? ui->settings->game_sort : SORT_RECENT;
    if (!load_games(ui) || (order = malloc(sizeof(int) * (n_games ? n_games : 1))) == NULL)
    {
        free_games();
        return false;
    }
    if (n_games == 0)
    {
        static const UiKey keys[] = { { "A", "Back", KEY_A } };
        char text[PATH_LEN + 32];
        snprintf(text, sizeof(text), "No games (.nds) in %s", ui->games_dir);
        ui_sound(SND_ERROR);
        ui_clear();
        ui_header("Games");
        ui_card("No games here", text, UI_AMBER, keys, 1);
        ui_release();
        ui_wait(KEY_A | KEY_B);
        free_games();
        return false;
    }
    sort_games();

    int sel = 0, top = 0;
    bool picked = false, favorites_changed = false, redraw = true;
    keysSetRepeat(15, 4);
    ui_release();
    while (1)
    {
        if (sel < top)
            top = sel;
        if (sel >= top + ROWS)
            top = sel - ROWS + 1;
        if (redraw)
        {
            draw_list(sel, top, ui);
            show_game(&games[order[sel]]);
            redraw = false;
        }

        uint32_t k;
        int tap;
        do
        {
            sync_frame();
            scanKeys();
            k = (keysDownRepeat() & (KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT)) |
                (keysDown() & (KEY_A | KEY_B | KEY_X | KEY_Y | KEY_L | KEY_R | KEY_START | KEY_SELECT)) |
                ui_footer_key();
            tap = ui_tapped();
        } while (k == 0 && tap == -1);

        int old = sel;
        if (tap == -2)
            k |= KEY_R;
        else if (tap >= 0 && tap == sel)
            k |= KEY_A;
        else if (tap >= 0)
            sel = tap;
        if (k & KEY_UP)
            sel = sel > 0 ? sel - 1 : n_games - 1;
        if (k & KEY_DOWN)
            sel = sel + 1 < n_games ? sel + 1 : 0;
        if (k & KEY_LEFT)
            sel = sel > ROWS ? sel - ROWS : 0;
        if (k & KEY_RIGHT)
            sel = sel + ROWS < n_games ? sel + ROWS : n_games - 1;
        if (sel != old)
        {
            ui_sound(SND_MOVE);
            redraw = true;
        }

        Game *g = &games[order[sel]];
        if (k & KEY_A)
        {
            ui_sound(SND_SELECT);
            snprintf(out, outsz, "%s", g->path);
            picked = true;
            break;
        }
        if ((k & KEY_START) && ui->last != NULL)
        {
            ui_sound(SND_SELECT);
            snprintf(out, outsz, "%s", ui->last);
            picked = true;
            break;
        }
        if (k & (KEY_B | KEY_SELECT))
        {
            ui_sound(SND_BACK);
            break;
        }
        if (k & KEY_Y)
        {
            g->favorite = !g->favorite;
            favorites_changed = true;
            ui_sound(SND_TOGGLE);
            redraw = true;
        }
        if (k & (KEY_L | KEY_R))
        {
            // The new order, keeping the same game picked
            int keep = order[sel];
            sort_mode = (sort_mode + ((k & KEY_R) ? 1 : SORTS - 1)) % SORTS;
            sort_games();
            for (int i = 0; i < n_games; i++)
            {
                if (order[i] == keep)
                    sel = i;
            }
            ui_sound(SND_TOGGLE);
            redraw = true;
        }
        if (k & KEY_X)
        {
            ui_sound(SND_SELECT);
            achievements_screen(g, ui->sets_dir);
            ui_release();
            redraw = true;
        }
    }

    if (favorites_changed)
        write_index(ui->index_dir, games, n_games);
    if (ui->settings->game_sort != sort_mode)
    {
        ui->settings->game_sort = (uint8_t)sort_mode;
        settings_save(ui->settings_path, ui->settings);
    }
    free_games();
    top_dsi();
    return picked;
}
