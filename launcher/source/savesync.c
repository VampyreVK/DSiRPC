// SPDX-License-Identifier: MIT
//
// The save sync's work (see savesync.h): finding the saves, the two-stage
// check against saves.idx, and the exchange with DSiRPC
// (core/save_session.py describes it). Downloads are written to a .tmp file,
// checked against their CRC, then swapped in (the old file kept as .bak
// until the new one is in place, and put back on the next scan if the
// console went off in between). A console's save always goes to the PC
// before anything replaces it.
//
// A save goes through memory both ways, with the SD card and the Wi-Fi never
// busy at once: one going out is read whole (twice, until both reads agree)
// before it's sent, one coming in is received whole, then written and read
// back. Reading the SD card while the Wi-Fi sent corrupted a few blocks in a
// hundred on a 3DS (big saves arrived damaged nearly every time). An
// exchange that fails on the way (the network, or DSiRPC finding the save
// damaged or unable to store it) is tried again, up to SYNC_TRIES times.

#include <dirent.h>
#include <errno.h>
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <time.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "savesync.h"

#define PROTO_VERSION    2
#define OP_PLAN          1
#define OP_PUT           2
#define OP_GET           3
#define OP_HIST          4
#define OP_DONE          5
#define PUT_SYNC         1
#define PUT_BACKUP       2
#define PUT_SAFETY       3
#define GET_MAKE_LATEST  1
#define STATE_PRESENT    1
#define STATE_EXCLUDED   2
#define STATUS_OFF       5
#define STATUS_RELEASE   6

#define HEADER_SIZE      16
#define PLAN_ENTRY_SIZE  21
#define PLAN_ITEM_SIZE   22
#define HIST_ITEM_SIZE   14
#define MAX_SAVE_SIZE    (16 * 1024 * 1024)
#define CHUNK            4096
#define MAX_DEPTH        3
#define DIR_CACHE_MAX    16
#define DIR_NAME_LEN     128     // longer file names are left out
#define INDEX_MAGIC      "DSiRPC saves 1"
#define TWLM_SAVES       "sd:/_nds/TWiLightMenu/saves"
#define UNIX_TIME_2000   946684800

#define READ_TRIES       4       // reads of a save until two agree
#define WRITE_TRIES      3       // writes of a download until one reads back right
#define SYNC_TRIES       3       // tries of an exchange that failed on the way
#ifndef SAVE_RETRY_FRAMES
#define SAVE_RETRY_FRAMES 60     // the wait before another try: 1 s, then 2 s
#endif

// Aligned for the SD card's DMA, like every buffer a save is read into
static uint8_t chunk[CHUNK] __attribute__((aligned(32)));

// Whether the last failure is worth another try: the network (no connection,
// a lost one, a stall), DSiRPC finding the save damaged or unable to store it,
// or the SD card not keeping a download
static bool transient;

static int net(int r)
{
    if (r < 0)
        transient = true;
    return r;
}

// Waits before another try (1 s, then 2 s...), saying so. false if B stops it.
static bool retry_wait(const SyncJob *job, int attempt, const char *name, SaveProgress progress)
{
    if (progress != NULL)
    {
        char what[96];
        snprintf(what, sizeof(what), "Trying again (%d of %d)\n%s", attempt + 1, SYNC_TRIES, name);
        progress(what, 0, 1);
    }
    for (int f = 0; f < SAVE_RETRY_FRAMES * attempt; f++)
    {
        sync_frame();
        if (job->cancelled != NULL && job->cancelled())
            return false;
    }
    return true;
}

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

static void put16(uint8_t *p, uint16_t v)
{
    p[0] = v;
    p[1] = v >> 8;
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = v;
    p[1] = v >> 8;
    p[2] = v >> 16;
    p[3] = v >> 24;
}

static bool valid_code(const uint8_t *c)
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

static bool ends_with(const char *s, const char *tail)
{
    size_t n = strlen(s), m = strlen(tail);
    return n >= m && strcasecmp(s + n - m, tail) == 0;
}

static const char *slot_ext(int slot)
{
    static const char *ext[SAVE_MAX_SLOT + 1] = {
        ".sav", ".sav1", ".sav2", ".sav3", ".sav4", ".sav5", ".sav6", ".sav7", ".sav8", ".sav9",
    };
    return ext[slot];
}

static bool is_dir(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISDIR(st.st_mode);
}

// mkdir -p, for a save's folder
static void make_dirs(const char *dir)
{
    char path[SAVE_PATH_LEN];
    snprintf(path, sizeof(path), "%s", dir);
    for (char *p = path + 1; *p != '\0'; p++)
    {
        if (*p == '/' && p[-1] != ':')
        {
            *p = '\0';
            mkdir(path, 0777);
            *p = '/';
        }
    }
    mkdir(path, 0777);
}

// The folder part of a path, in out
static void parent_dir(char *out, size_t outsz, const char *path)
{
    snprintf(out, outsz, "%s", path);
    char *slash = strrchr(out, '/');
    if (slash != NULL)
        *slash = '\0';
}

// ---------------------------------------------------------------------------
// CRC32 (zlib's)

static uint32_t crc_table[256];

static uint32_t crc_update(uint32_t crc, const uint8_t *p, size_t n)
{
    if (crc_table[1] == 0)
    {
        for (uint32_t i = 0; i < 256; i++)
        {
            uint32_t c = i;
            for (int k = 0; k < 8; k++)
                c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            crc_table[i] = c;
        }
    }
    crc = ~crc;
    while (n--)
        crc = crc_table[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

bool saves_file_crc(const char *path, uint32_t *crc, uint32_t *size)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return false;
    uint32_t c = 0, total = 0;
    size_t n;
    while ((n = fread(chunk, 1, sizeof(chunk), f)) > 0)
    {
        c = crc_update(c, chunk, n);
        total += n;
    }
    bool ok = !ferror(f);
    fclose(f);
    *crc = c;
    *size = total;
    return ok;
}

// ---------------------------------------------------------------------------
// The save folders, each listed once

typedef struct
{
    char dir[SAVE_PATH_LEN];
    char (*names)[DIR_NAME_LEN];   // the files with ".sav" in their name, sorted
    int count;
    bool exists;
} DirCache;

static DirCache dirs[DIR_CACHE_MAX];
static int n_dirs;

// ".sav" anywhere in a file name (any case): saves, slots, .bak and .tmp
static bool has_sav(const char *name)
{
    for (const char *p = name; p[0] != '\0'; p++)
    {
        if (p[0] == '.' && strncasecmp(p + 1, "sav", 3) == 0)
            return true;
    }
    return false;
}

static int cmp_name(const void *a, const void *b)
{
    return strcasecmp((const char *)a, (const char *)b);
}

static DirCache *dir_list(const char *dir)
{
    for (int i = 0; i < n_dirs; i++)
    {
        if (strcasecmp(dirs[i].dir, dir) == 0)
            return &dirs[i];
    }
    if (n_dirs == DIR_CACHE_MAX)
        return NULL;
    DirCache *d = &dirs[n_dirs++];
    memset(d, 0, sizeof(*d));
    snprintf(d->dir, sizeof(d->dir), "%s", dir);
    DIR *h = opendir(dir);
    if (h == NULL)
        return d;
    d->exists = true;
    int cap = 0;
    struct dirent *e;
    while ((e = readdir(h)) != NULL)
    {
        if (strlen(e->d_name) >= DIR_NAME_LEN || !has_sav(e->d_name))
            continue;
        if (d->count == cap)
        {
            int ncap = cap ? cap * 2 : 64;
            char (*more)[DIR_NAME_LEN] = realloc(d->names, (size_t)ncap * DIR_NAME_LEN);
            if (more == NULL)
                break;
            d->names = more;
            cap = ncap;
        }
        snprintf(d->names[d->count++], DIR_NAME_LEN, "%s", e->d_name);
    }
    closedir(h);
    if (d->count > 1)
        qsort(d->names, d->count, DIR_NAME_LEN, cmp_name);
    return d;
}

static bool dir_has(const DirCache *d, const char *name)
{
    return d != NULL && d->count > 0 && strlen(name) < DIR_NAME_LEN &&
           bsearch(name, d->names, d->count, DIR_NAME_LEN, cmp_name) != NULL;
}

static void dir_cache_free(void)
{
    for (int i = 0; i < n_dirs; i++)
        free(dirs[i].names);
    n_dirs = 0;
}

// ---------------------------------------------------------------------------
// saves.idx: one line per save, "code hcrc slot size mtime crc base flags
// path" (tab-separated): the file as last seen (size, time and CRC, for
// stage 1) and its CRC at the last sync (base).

typedef struct
{
    char code[5];
    uint16_t hcrc;
    uint8_t slot, flags;
    uint32_t size, crc, base;
    int32_t mtime;
    char path[SAVE_PATH_LEN];
} IndexEntry;

static IndexEntry *load_index(const char *path, int *count, bool *exists)
{
    *count = 0;
    *exists = false;
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return NULL;
    *exists = true;
    char line[SAVE_PATH_LEN + 128];
    if (fgets(line, sizeof(line), f) == NULL || strncmp(line, INDEX_MAGIC, strlen(INDEX_MAGIC)) != 0)
    {
        fclose(f);
        return NULL;
    }
    int cap = 0;
    IndexEntry *out = NULL;
    while (fgets(line, sizeof(line), f) != NULL)
    {
        IndexEntry e;
        memset(&e, 0, sizeof(e));
        unsigned hcrc, slot, flags;
        unsigned long size, crc, base;
        long mtime;
        int used = 0;
        if (sscanf(line, "%4s\t%x\t%u\t%lu\t%ld\t%lx\t%lx\t%u\t%n", e.code, &hcrc, &slot, &size, &mtime, &crc,
                   &base, &flags, &used) != 8 || used == 0 || slot > SAVE_MAX_SLOT)
            continue;
        char *p = line + used;
        p[strcspn(p, "\r\n")] = '\0';
        if (*p == '\0')
            continue;
        snprintf(e.path, sizeof(e.path), "%s", p);
        e.hcrc = hcrc;
        e.slot = slot;
        e.flags = flags;
        e.size = size;
        e.mtime = (int32_t)mtime;
        e.crc = crc;
        e.base = base;
        if (*count == cap)
        {
            int ncap = cap ? cap * 2 : 64;
            IndexEntry *more = realloc(out, (size_t)ncap * sizeof(IndexEntry));
            if (more == NULL)
                break;
            out = more;
            cap = ncap;
        }
        out[(*count)++] = e;
    }
    fclose(f);
    return out;
}

static IndexEntry *find_entry(IndexEntry *index, int count, const char *path)
{
    for (int i = 0; i < count; i++)
    {
        if (strcasecmp(index[i].path, path) == 0)
            return &index[i];
    }
    return NULL;
}

static bool write_entries(const char *path, const IndexEntry *entries, int count)
{
    char tmp[SAVE_PATH_LEN + 8];
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *f = fopen(tmp, "wb");
    if (f == NULL)
        return false;
    fprintf(f, INDEX_MAGIC "\n");
    for (int i = 0; i < count; i++)
    {
        const IndexEntry *e = &entries[i];
        fprintf(f, "%s\t%04X\t%u\t%lu\t%ld\t%08lX\t%08lX\t%u\t%s\n", e->code, e->hcrc, e->slot,
                (unsigned long)e->size, (long)e->mtime, (unsigned long)e->crc, (unsigned long)e->base, e->flags,
                e->path);
    }
    if (fclose(f) != 0)
    {
        remove(tmp);
        return false;
    }
    remove(path);
    return rename(tmp, path) == 0;
}

bool saves_write_index(const SaveList *list)
{
    IndexEntry *entries = malloc(sizeof(IndexEntry) * (list->count ? list->count : 1));
    if (entries == NULL)
        return false;
    int n = 0;
    for (int i = 0; i < list->count; i++)
    {
        const SaveItem *it = &list->items[i];
        if (!it->present && !it->excluded && it->base == 0)
            continue;
        IndexEntry *e = &entries[n++];
        memset(e, 0, sizeof(*e));
        memcpy(e->code, it->code, 5);
        e->hcrc = it->hcrc;
        e->slot = it->slot;
        e->flags = it->excluded ? 1 : 0;
        e->size = it->present ? it->size : 0;
        e->mtime = it->present ? it->mtime : 0;
        e->crc = it->present ? it->crc : 0;
        e->base = it->base;
        snprintf(e->path, sizeof(e->path), "%s", it->path);
    }
    bool ok = write_entries(list->index_path, entries, n);
    free(entries);
    return ok;
}

// ---------------------------------------------------------------------------
// Finding the saves

static SaveItem *new_item(SaveList *list, int *cap)
{
    if (list->count == SAVE_MAX_ITEMS)
        return NULL;
    if (list->count == *cap)
    {
        int ncap = *cap ? *cap * 2 : 64;
        SaveItem *more = realloc(list->items, (size_t)ncap * sizeof(SaveItem));
        if (more == NULL)
            return NULL;
        list->items = more;
        *cap = ncap;
    }
    SaveItem *it = &list->items[list->count++];
    memset(it, 0, sizeof(*it));
    it->action = SA_UNKNOWN;
    return it;
}

static int items_cap;

static bool already_listed(const SaveList *list, const char code[4], uint16_t hcrc)
{
    for (int i = 0; i < list->count; i++)
    {
        if (memcmp(list->items[i].code, code, 4) == 0 && list->items[i].hcrc == hcrc)
            return true;
    }
    return false;
}

// A save left as .bak by a swap that didn't finish: put it back.
static void recover(DirCache *d, const char *name)
{
    if (strlen(name) + 4 >= DIR_NAME_LEN)
        return;     // too long to be listed with ".bak" on it
    char bak[DIR_NAME_LEN], path[SAVE_PATH_LEN], bak_path[SAVE_PATH_LEN];
    snprintf(bak, sizeof(bak), "%.*s.bak", DIR_NAME_LEN - 5, name);
    if (dir_has(d, name) || !dir_has(d, bak))
        return;
    join_path(path, sizeof(path), d->dir, name);
    join_path(bak_path, sizeof(bak_path), d->dir, bak);
    if (rename(bak_path, path) == 0)
    {
        // Listed now under its real name
        for (int i = 0; i < d->count; i++)
        {
            if (strcasecmp(d->names[i], bak) == 0)
            {
                snprintf(d->names[i], DIR_NAME_LEN, "%.*s", DIR_NAME_LEN - 1, name);
                break;
            }
        }
        qsort(d->names, d->count, DIR_NAME_LEN, cmp_name);
    }
}

static void add_rom(SaveList *list, const char *dir, const char *file)
{
    char rom[SAVE_PATH_LEN];
    join_path(rom, sizeof(rom), dir, file);
    uint8_t hdr[0x160];
    FILE *f = fopen(rom, "rb");
    if (f == NULL)
        return;
    size_t got = fread(hdr, 1, sizeof(hdr), f);
    fclose(f);
    if (got != sizeof(hdr) || !valid_code(hdr + 0x0C))
        return;
    uint16_t hcrc = get16(hdr + 0x15E);
    if (already_listed(list, (const char *)hdr + 0x0C, hcrc))
        return;     // a second copy of the same game: its saves are the first's
    list->roms++;

    char base[SAVE_PATH_LEN];
    snprintf(base, sizeof(base), "%s", file);
    base[strlen(base) - 4] = '\0';   // without ".nds"

    // Where TWiLight Menu++ may keep its saves, in the order it looks
    char cands[4][SAVE_PATH_LEN];
    int nc = 0;
    join_path(cands[nc++], sizeof(cands[0]), dir, "saves");
    join_path(cands[nc], sizeof(cands[0]), list->games_dir, "saves");
    if (strcasecmp(cands[nc], cands[0]) != 0)
        nc++;
    snprintf(cands[nc++], sizeof(cands[0]), "%s", dir);
    snprintf(cands[nc++], sizeof(cands[0]), "%s", TWLM_SAVES);

    bool found = false;
    for (int c = 0; c < nc && !found; c++)
    {
        DirCache *d = dir_list(cands[c]);
        if (d == NULL || d->count == 0)
            continue;
        for (int slot = 0; slot <= SAVE_MAX_SLOT; slot++)
        {
            char name[SAVE_PATH_LEN];
            snprintf(name, sizeof(name), "%s%s", base, slot_ext(slot));
            recover(d, name);
            if (!dir_has(d, name))
                continue;
            SaveItem *it = new_item(list, &items_cap);
            if (it == NULL)
                return;
            memcpy(it->code, hdr + 0x0C, 4);
            it->hcrc = hcrc;
            it->slot = slot;
            snprintf(it->name, sizeof(it->name), "%s", base);
            join_path(it->path, sizeof(it->path), cands[c], name);
            it->present = true;
            found = true;

            char tmp[SAVE_PATH_LEN + 8];
            snprintf(tmp, sizeof(tmp), "%s.tmp", it->path);
            remove(tmp);   // a download that didn't finish
        }
    }
    if (found)
        return;

    // No save yet: where one from the PC would go (the game's "saves"
    // folder, or the games folder's if only that one is there)
    SaveItem *it = new_item(list, &items_cap);
    if (it == NULL)
        return;
    memcpy(it->code, hdr + 0x0C, 4);
    it->hcrc = hcrc;
    snprintf(it->name, sizeof(it->name), "%s", base);
    const char *target = cands[0];
    if (!dir_list(cands[0])->exists && nc > 1 && strcasecmp(cands[1], dir) != 0 && dir_list(cands[1])->exists)
        target = cands[1];
    char name[SAVE_PATH_LEN];
    snprintf(name, sizeof(name), "%s.sav", base);
    join_path(it->path, sizeof(it->path), target, name);
}

static void scan_dir(SaveList *list, const char *dir, int depth, SaveProgress progress)
{
    DIR *d = opendir(dir);
    if (d == NULL)
        return;
    struct dirent *e;
    while ((e = readdir(d)) != NULL)
    {
        if (e->d_name[0] == '.')
            continue;
        char path[SAVE_PATH_LEN];
        join_path(path, sizeof(path), dir, e->d_name);
        bool sub = e->d_type == DT_DIR || (e->d_type == DT_UNKNOWN && is_dir(path));
        if (sub)
        {
            if (depth < MAX_DEPTH && e->d_name[0] != '_' && strcasecmp(e->d_name, "saves") != 0)
                scan_dir(list, path, depth + 1, progress);
            continue;
        }
        if (ends_with(e->d_name, ".nds"))
        {
            add_rom(list, dir, e->d_name);
            if (progress != NULL && list->roms % 8 == 0)
                progress("Looking for your games", list->roms, 0);
        }
    }
    closedir(d);
}

static int cmp_item(const void *a, const void *b)
{
    const SaveItem *x = a, *y = b;
    int c = strcasecmp(x->name, y->name);
    return c != 0 ? c : (int)x->slot - (int)y->slot;
}

int saves_scan(SaveList *list, const char *games_dir, const char *index_dir, SaveProgress progress)
{
    memset(list, 0, sizeof(*list));
    items_cap = 0;
    snprintf(list->games_dir, sizeof(list->games_dir), "%s", games_dir);
    join_path(list->index_path, sizeof(list->index_path), index_dir, SAVES_INDEX);

    scan_dir(list, games_dir, 0, progress);
    dir_cache_free();
    if (list->count > 1)
        qsort(list->items, list->count, sizeof(SaveItem), cmp_item);

    // Stage 1 against saves.idx, stage 2 (the CRC) for what it can't vouch for
    int n_index;
    bool exists;
    IndexEntry *index = load_index(list->index_path, &n_index, &exists);
    int checked = 0, to_check = 0;
    for (int i = 0; i < list->count; i++)
        to_check += list->items[i].present;
    for (int i = 0; i < list->count; i++)
    {
        SaveItem *it = &list->items[i];
        IndexEntry *e = find_entry(index, n_index, it->path);
        if (e != NULL)
        {
            it->base = e->base;
            it->excluded = e->flags & 1;
        }
        if (!it->present)
            continue;
        struct stat st;
        if (stat(it->path, &st) != 0)
        {
            it->present = false;
            continue;
        }
        it->size = (uint32_t)st.st_size;
        it->mtime = (int32_t)st.st_mtime;
        if (e != NULL && e->size == it->size && e->mtime == it->mtime && e->crc != 0)
        {
            it->crc = e->crc;
        }
        else
        {
            if (progress != NULL)
                progress(it->name, checked, to_check);
            uint32_t size;
            if (!saves_file_crc(it->path, &it->crc, &size))
                it->present = false;
        }
        it->changed = it->present && it->crc != it->base;
        checked++;
    }
    free(index);
    return list->count;
}

void saves_free(SaveList *list)
{
    free(list->items);
    list->items = NULL;
    list->count = 0;
}

// The games' file names without ".nds", for the startup check: found the
// way scan_dir() finds the games, without reading them
typedef struct
{
    char (*names)[DIR_NAME_LEN];
    int count, cap;
} GameNames;

static void collect_games(GameNames *g, const char *dir, int depth)
{
    DIR *d = opendir(dir);
    if (d == NULL)
        return;
    struct dirent *e;
    while ((e = readdir(d)) != NULL)
    {
        if (e->d_name[0] == '.')
            continue;
        char path[SAVE_PATH_LEN];
        join_path(path, sizeof(path), dir, e->d_name);
        bool sub = e->d_type == DT_DIR || (e->d_type == DT_UNKNOWN && is_dir(path));
        if (sub)
        {
            if (depth < MAX_DEPTH && e->d_name[0] != '_' && strcasecmp(e->d_name, "saves") != 0)
                collect_games(g, path, depth + 1);
            continue;
        }
        size_t n = strlen(e->d_name);
        if (!ends_with(e->d_name, ".nds") || n - 4 >= DIR_NAME_LEN)
            continue;
        if (g->count == g->cap)
        {
            int ncap = g->cap ? g->cap * 2 : 64;
            char (*more)[DIR_NAME_LEN] = realloc(g->names, (size_t)ncap * DIR_NAME_LEN);
            if (more == NULL)
                break;
            g->names = more;
            g->cap = ncap;
        }
        snprintf(g->names[g->count++], DIR_NAME_LEN, "%.*s", (int)(n - 4), e->d_name);
    }
    closedir(d);
}

int saves_quick_check(const char *games_dir, const char *index_dir)
{
    char index_path[SAVE_PATH_LEN];
    join_path(index_path, sizeof(index_path), index_dir, SAVES_INDEX);
    int n;
    bool exists;
    IndexEntry *index = load_index(index_path, &n, &exists);
    if (!exists)
        return -1;

    int changed = 0;
    bool dirty = false;
    for (int i = 0; i < n; i++)
    {
        IndexEntry *e = &index[i];
        struct stat st;
        if (e->size == 0 || stat(e->path, &st) != 0)
            continue;
        if ((uint32_t)st.st_size != e->size || (int32_t)st.st_mtime != e->mtime)
        {
            uint32_t crc, size;
            if (!saves_file_crc(e->path, &crc, &size))
                continue;
            // Seen as it is now, so the next start doesn't read it again
            e->size = size;
            e->mtime = (int32_t)st.st_mtime;
            e->crc = crc;
            dirty = true;
        }
        if (e->crc != e->base && !(e->flags & 1))
            changed++;
    }

    // New saves in the games folder's "saves" folder, the ones named after
    // a game (the scan leaves out the rest, like a renamed backup)
    char saves_dir[SAVE_PATH_LEN];
    join_path(saves_dir, sizeof(saves_dir), games_dir, "saves");
    if (is_dir(saves_dir))
    {
        GameNames games = { 0 };
        collect_games(&games, games_dir, 0);
        if (games.count > 1)
            qsort(games.names, games.count, DIR_NAME_LEN, cmp_name);
        DIR *d = games.count > 0 ? opendir(saves_dir) : NULL;
        struct dirent *ent;
        while (d != NULL && (ent = readdir(d)) != NULL)
        {
            const char *dot = strrchr(ent->d_name, '.');
            if (dot == NULL || strncasecmp(dot, ".sav", 4) != 0 || (dot[4] != '\0' && (dot[4] < '1' || dot[4] > '9' || dot[5] != '\0')))
                continue;
            char base[DIR_NAME_LEN];
            size_t len = (size_t)(dot - ent->d_name);
            if (len >= sizeof(base))
                continue;
            memcpy(base, ent->d_name, len);
            base[len] = '\0';
            if (bsearch(base, games.names, games.count, DIR_NAME_LEN, cmp_name) == NULL)
                continue;
            char path[SAVE_PATH_LEN];
            join_path(path, sizeof(path), saves_dir, ent->d_name);
            if (find_entry(index, n, path) == NULL)
                changed++;
        }
        if (d != NULL)
            closedir(d);
        free(games.names);
    }
    if (dirty)
        write_entries(index_path, index, n);
    free(index);
    return changed;
}

bool saves_needs_sync(const SaveItem *item, bool backup_only)
{
    if (item->excluded || item->done)
        return false;
    switch (item->action)
    {
    case SA_UPLOAD:
    case SA_BACKUP:
    case SA_CONFLICT:
        return true;
    case SA_DOWNLOAD:
    case SA_DOWNLOAD_NEW:
        return !backup_only;
    default:
        return false;
    }
}

// ---------------------------------------------------------------------------
// Talking to DSiRPC

static size_t request_header(uint8_t *p, const SaveConsole *c, uint8_t op)
{
    memcpy(p, "DRSV", 4);
    put16(p + 4, PROTO_VERSION);
    put16(p + 6, c->backup_only ? 1 : 0);
    memcpy(p + 8, c->mac, 6);
    p[14] = (uint8_t)c->model;
    p[15] = op;
    return HEADER_SIZE;
}

static void status_msg(char *msg, size_t msgsz, int status)
{
    if (status == 2 || status == 3)
        transient = true;
    if (status == STATUS_OFF)
        snprintf(msg, msgsz, "Save backups are off in DSiRPC");
    else if (status == STATUS_RELEASE)
        snprintf(msg, msgsz, "DSiRPC and this launcher\nare from different releases");
    else if (status == 1)
        snprintf(msg, msgsz, "DSiRPC doesn't have that save");
    else if (status == 2)
        snprintf(msg, msgsz, "The save arrived damaged;\nnothing was changed");
    else if (status == 3)
        snprintf(msg, msgsz, "DSiRPC can't store the save\n(is the PC's disk full?)");
    else
        snprintf(msg, msgsz, "DSiRPC couldn't read the\nrequest (%d)", status);
}

static SaveItem *find_item(SaveList *list, const uint8_t code[4], uint16_t hcrc, int slot)
{
    for (int i = 0; i < list->count; i++)
    {
        SaveItem *it = &list->items[i];
        if (memcmp(it->code, code, 4) == 0 && it->hcrc == hcrc && it->slot == slot)
            return it;
    }
    return NULL;
}

// A save DSiRPC has for one of the console's games, in a slot the console
// has no save in: listed, to go next to the game's other saves.
static SaveItem *add_pc_slot(SaveList *list, const uint8_t code[4], uint16_t hcrc, int slot)
{
    SaveItem *sibling = NULL;
    for (int i = 0; i < list->count && sibling == NULL; i++)
    {
        if (memcmp(list->items[i].code, code, 4) == 0 && list->items[i].hcrc == hcrc)
            sibling = &list->items[i];
    }
    if (sibling == NULL)
        return NULL;
    SaveItem copy = *sibling;
    SaveItem *it = new_item(list, &items_cap);
    if (it == NULL)
        return NULL;
    sibling = NULL;     // the array may have moved
    memcpy(it->code, copy.code, 5);
    it->hcrc = hcrc;
    it->slot = slot;
    snprintf(it->name, sizeof(it->name), "%s", copy.name);
    // The sibling's path with this slot's extension
    char path[SAVE_PATH_LEN];
    snprintf(path, sizeof(path), "%s", copy.path);
    char *dot = strrchr(path, '.');
    if (dot != NULL)
        *dot = '\0';
    snprintf(it->path, sizeof(it->path), "%s%s", path, slot_ext(slot));
    return it;
}

// The plan's request and its answer (one try).
static int plan_exchange(const SyncJob *job, SaveList *list, const struct sockaddr_in *server, const uint8_t *req,
                         size_t n, char *msg, size_t msgsz)
{
    int sock;
    int r = net(sync_open(job, server, &sock, msg, msgsz));
    if (r > 0)
        r = net(sync_send(job, sock, req, n, msg, msgsz));
    if (r <= 0)
    {
        sync_close(sock);
        return r;
    }

    uint8_t head[8];
    if ((r = net(sync_recv(job, sock, head, sizeof(head), msg, msgsz))) <= 0)
        goto done;
    if (memcmp(head, "DRSP", 4) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC's answer is garbled\n(an older DSiRPC?)");
        r = -1;
        goto done;
    }
    if (get16(head + 4) != 0)
    {
        status_msg(msg, msgsz, get16(head + 4));
        r = -1;
        goto done;
    }
    int items = get16(head + 6);
    for (int i = 0; i < items; i++)
    {
        uint8_t p[PLAN_ITEM_SIZE];
        char source[256];
        if ((r = net(sync_recv(job, sock, p, sizeof(p), msg, msgsz))) <= 0 ||
            (r = net(sync_recv(job, sock, source, p[21], msg, msgsz))) <= 0)
            goto done;
        source[p[21]] = '\0';
        if (!valid_code(p) || p[6] > SAVE_MAX_SLOT || p[7] > SA_DOWNLOAD_NEW)
        {
            snprintf(msg, msgsz, "DSiRPC's answer is garbled");
            r = -1;
            goto done;
        }
        SaveItem *it = find_item(list, p, get16(p + 4), p[6]);
        if (it == NULL)
            it = add_pc_slot(list, p, get16(p + 4), p[6]);
        if (it == NULL)
            continue;
        it->action = p[7];
        if (it->action == SA_IN_SYNC && it->present)
        {
            // The PC has this very save: synced now, as far as saves.idx
            // goes (or the startup check would go on counting it)
            it->base = it->crc;
            it->changed = false;
        }
        it->pc_size = get32(p + 8);
        it->pc_crc = get32(p + 12);
        it->pc_time = get32(p + 16);
        // Never a download over a save written after the PC's (as the
        // consoles' clocks have it: the PC dates a save by when its console
        // wrote it): that's a conflict, for the player to settle, whatever
        // DSiRPC planned
        if (it->action == SA_DOWNLOAD && it->present && it->pc_time != 0 && it->mtime > UNIX_TIME_2000 &&
            (uint32_t)(it->mtime - UNIX_TIME_2000) > it->pc_time)
            it->action = SA_CONFLICT;
        it->versions = p[20];
        snprintf(it->pc_source, sizeof(it->pc_source), "%.32s", source);
        it->choice = SC_ASK;
        it->done = it->failed = false;
    }
    r = 1;

done:
    sync_close(sock);
    return r;
}

int saves_plan(const SyncJob *job, const SaveConsole *console, SaveList *list,
               struct sockaddr_in *server, char *msg, size_t msgsz)
{
    msg[0] = '\0';
    int r = sync_find(job, server, msg, msgsz);
    if (r <= 0)
        return r;

    size_t cap = HEADER_SIZE + 2 + (size_t)list->count * (PLAN_ENTRY_SIZE + SAVE_NAME_LEN);
    uint8_t *req = malloc(cap);
    if (req == NULL)
    {
        snprintf(msg, msgsz, "Out of memory");
        return -1;
    }
    size_t n = request_header(req, console, OP_PLAN);
    put16(req + n, list->count);
    n += 2;
    for (int i = 0; i < list->count; i++)
    {
        SaveItem *it = &list->items[i];
        it->action = SA_UNKNOWN;
        uint8_t *p = req + n;
        memcpy(p, it->code, 4);
        put16(p + 4, it->hcrc);
        p[6] = it->slot;
        p[7] = (it->present ? STATE_PRESENT : 0) | (it->excluded ? STATE_EXCLUDED : 0);
        put32(p + 8, it->size);
        put32(p + 12, it->crc);
        put32(p + 16, it->base);
        size_t len = strlen(it->name);
        p[20] = (uint8_t)len;
        memcpy(p + PLAN_ENTRY_SIZE, it->name, len);
        n += PLAN_ENTRY_SIZE + len;
    }

    for (int attempt = 1; ; attempt++)
    {
        transient = false;
        msg[0] = '\0';
        r = plan_exchange(job, list, server, req, n, msg, msgsz);
        if (r >= 0 || !transient || attempt >= SYNC_TRIES || !retry_wait(job, attempt, "", NULL))
            break;
    }
    free(req);
    return r;
}

// The whole save in memory, read again to check it: two reads that disagree
// are read again (READ_TRIES in all). NULL if it can't be (msg).
static uint8_t *load_save(const char *path, uint32_t *size, uint32_t *crc, char *msg, size_t msgsz)
{
    struct stat st;
    if (stat(path, &st) != 0 || st.st_size > MAX_SAVE_SIZE)
    {
        snprintf(msg, msgsz, "Can't read the save");
        return NULL;
    }
    uint32_t n = (uint32_t)st.st_size;
    uint8_t *data = memalign(32, n ? n : 1);
    if (data == NULL)
    {
        snprintf(msg, msgsz, "Not enough memory for\nthis save");
        return NULL;
    }
    bool differed = false;
    for (int i = 0; i < READ_TRIES; i++)
    {
        FILE *f = fopen(path, "rb");
        bool read = f != NULL && fread(data, 1, n, f) == n;
        if (f != NULL)
            fclose(f);
        if (!read)
            break;
        uint32_t again, again_size;
        if (saves_file_crc(path, &again, &again_size) && again_size == n && again == crc_update(0, data, n))
        {
            *size = n;
            *crc = again;
            return data;
        }
        differed = true;
    }
    free(data);
    transient = differed;
    snprintf(msg, msgsz, differed ? "The SD card read this save\ndifferently each time" : "Can't read the save");
    return NULL;
}

// Sends the console's save. 1: DSiRPC has it, 0: cancelled, -1: failed.
static int upload(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                  SaveItem *it, int kind, const char *what, SaveProgress progress,
                  char *msg, size_t msgsz)
{
    // Read whole before anything's sent, so the SD card is idle while the
    // Wi-Fi sends; its CRC is the one sent, whatever saves.idx remembered,
    // and the item takes what's there, so saves.idx has it from then on
    uint32_t crc, size;
    uint8_t *data = load_save(it->path, &size, &crc, msg, msgsz);
    if (data == NULL)
        return -1;
    struct stat st;
    if (stat(it->path, &st) == 0)
        it->mtime = (int32_t)st.st_mtime;
    it->size = size;
    it->crc = crc;
    it->changed = it->crc != it->base;

    uint8_t req[HEADER_SIZE + 21 + SAVE_NAME_LEN];
    size_t n = request_header(req, console, OP_PUT);
    memcpy(req + n, it->code, 4);
    put16(req + n + 4, it->hcrc);
    req[n + 6] = it->slot;
    req[n + 7] = (uint8_t)kind;
    put32(req + n + 8, it->size);
    put32(req + n + 12, it->crc);
    // When the save was last written, by the console's clock (seconds since
    // 2000, its local time): the date DSiRPC gives its copy
    put32(req + n + 16, it->mtime > UNIX_TIME_2000 ? (uint32_t)(it->mtime - UNIX_TIME_2000) : 0);
    size_t len = strlen(it->name);
    req[n + 20] = (uint8_t)len;
    memcpy(req + n + 21, it->name, len);
    n += 21 + len;

    int sock;
    int r = net(sync_open(job, server, &sock, msg, msgsz));
    if (r > 0)
        r = net(sync_send(job, sock, req, n, msg, msgsz));
    uint32_t sent = 0;
    while (r > 0 && sent < size)
    {
        size_t want = size - sent < CHUNK ? size - sent : CHUNK;
        r = net(sync_send(job, sock, data + sent, want, msg, msgsz));
        sent += want;
        if (progress != NULL)
            progress(what, sent, size);
    }
    uint8_t answer[6];
    if (r > 0)
        r = net(sync_recv(job, sock, answer, sizeof(answer), msg, msgsz));
    sync_close(sock);
    free(data);
    if (r <= 0)
        return r;
    if (memcmp(answer, "DRSK", 4) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC's answer is garbled");
        return -1;
    }
    if (get16(answer + 4) != 0)
    {
        status_msg(msg, msgsz, get16(answer + 4));
        return -1;
    }
    return 1;
}

// Swaps a checked download in, keeping the old file as .bak until it's done.
static bool replace_file(const char *tmp, const char *path)
{
    char bak[SAVE_PATH_LEN + 8];
    snprintf(bak, sizeof(bak), "%s.bak", path);
    struct stat st;
    bool had = stat(path, &st) == 0;
    remove(bak);
    if (had && rename(path, bak) != 0)
        return false;
    if (rename(tmp, path) != 0)
    {
        if (had)
            rename(bak, path);
        return false;
    }
    if (had)
        remove(bak);
    return true;
}

// Takes a version DSiRPC keeps into the item's file. 1: done, 0: cancelled,
// -1: failed (the old save untouched).
static int download(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                    SaveItem *it, uint8_t version, uint8_t flags, const char *what, SaveProgress progress,
                    char *msg, size_t msgsz)
{
    uint8_t req[HEADER_SIZE + 9];
    size_t n = request_header(req, console, OP_GET);
    memcpy(req + n, it->code, 4);
    put16(req + n + 4, it->hcrc);
    req[n + 6] = it->slot;
    req[n + 7] = version;
    req[n + 8] = flags;
    n += 9;

    int sock;
    int r = net(sync_open(job, server, &sock, msg, msgsz));
    uint8_t head[14];
    if (r > 0)
        r = net(sync_send(job, sock, req, n, msg, msgsz));
    if (r > 0)
        r = net(sync_recv(job, sock, head, sizeof(head), msg, msgsz));
    if (r <= 0)
    {
        sync_close(sock);
        return r;
    }
    if (memcmp(head, "DRSD", 4) != 0 || get16(head + 4) != 0)
    {
        if (memcmp(head, "DRSD", 4) != 0)
            snprintf(msg, msgsz, "DSiRPC's answer is garbled");
        else
            status_msg(msg, msgsz, get16(head + 4));
        sync_close(sock);
        return -1;
    }
    uint32_t size = get32(head + 6), want_crc = get32(head + 10);
    uint8_t *data = size <= MAX_SAVE_SIZE ? memalign(32, size ? size : 1) : NULL;
    if (data == NULL)
    {
        snprintf(msg, msgsz, size <= MAX_SAVE_SIZE ? "Not enough memory for\nthis save" : "DSiRPC's answer is garbled");
        sync_close(sock);
        return -1;
    }

    // Received whole, with the SD card idle...
    uint32_t got = 0;
    while (got < size)
    {
        size_t want = size - got < CHUNK ? size - got : CHUNK;
        r = net(sync_recv(job, sock, data + got, want, msg, msgsz));
        if (r <= 0)
            break;
        got += want;
        if (progress != NULL)
            progress(what, got, size);
    }
    sync_close(sock);
    uint32_t crc = r > 0 ? crc_update(0, data, size) : 0;
    if (r <= 0 || crc != want_crc)
    {
        free(data);
        if (r > 0)
        {
            transient = true;
            snprintf(msg, msgsz, "The save arrived damaged;\nthe old one is kept");
        }
        return r <= 0 ? r : -1;
    }

    // ...then written with the Wi-Fi idle, and read back
    char dir[SAVE_PATH_LEN], tmp[SAVE_PATH_LEN + 8];
    parent_dir(dir, sizeof(dir), it->path);
    make_dirs(dir);
    snprintf(tmp, sizeof(tmp), "%s.tmp", it->path);
    bool written = false, kept = false;
    for (int i = 0; i < WRITE_TRIES && !kept; i++)
    {
        FILE *f = fopen(tmp, "wb");
        written = f != NULL && fwrite(data, 1, size, f) == size;
        if (f != NULL && fclose(f) != 0)
            written = false;
        uint32_t back, back_size;
        kept = written && saves_file_crc(tmp, &back, &back_size) && back == crc && back_size == size;
        if (!written)
            break;
    }
    free(data);
    if (!kept)
    {
        remove(tmp);
        transient = written;   // written but not kept: another try may do
        snprintf(msg, msgsz, written ? "The SD card didn't keep the\nsave; the old one is kept"
                                     : "Can't write the save\n(is the SD card full?)");
        return -1;
    }
    if (!replace_file(tmp, it->path))
    {
        remove(tmp);
        snprintf(msg, msgsz, "Can't replace the save\n(the old one is kept)");
        return -1;
    }
    struct stat st;
    it->present = true;
    it->size = size;
    it->crc = it->base = crc;
    it->mtime = stat(it->path, &st) == 0 ? (int32_t)st.st_mtime : 0;
    it->changed = false;
    return 1;
}

// The PC's save (version, from: the console it came from) replaces the
// console's, which is backed up on the PC first: downloading, or restoring
// an older version.
static int take_from_pc(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                        SaveItem *it, uint8_t version, const char *from, uint8_t flags, const uint32_t *listed,
                        SaveProgress progress, char *msg, size_t msgsz)
{
    char what[96];
    if (it->present)
    {
        snprintf(what, sizeof(what), "Backing up %s first", it->name);
        int r = upload(job, console, server, it, PUT_SAFETY, what, progress, msg, msgsz);
        if (r <= 0)
            return r;
        // The list said the console's save hadn't changed (so the PC's
        // newer one comes here; listed: its CRC then): if it has, that's
        // for you to decide
        if (listed != NULL && it->crc != *listed)
        {
            snprintf(msg, msgsz, "This save changed since the\nlist was made. It's backed up\non the PC; open the list again.");
            return -1;
        }
    }
    if (from != NULL && from[0] != '\0')
        snprintf(what, sizeof(what), "%s %s\nfrom: %s", version ? "Restoring" : "Downloading", it->name, from);
    else
        snprintf(what, sizeof(what), version ? "Restoring %s" : "Downloading %s from the PC", it->name);
    return download(job, console, server, it, version, flags, what, progress, msg, msgsz);
}

int saves_sync_item(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                    SaveList *list, SaveItem *it, SaveCounts *counts, SaveProgress progress,
                    char *msg, size_t msgsz)
{
    msg[0] = '\0';
    if (it->excluded || it->done)
        return 0;
    char what[80];
    int r = 0;
    int *count = NULL;
    SaveAction action = it->action;
    bool chosen = action == SA_CONFLICT;   // you settled it: no second-guessing
    uint32_t listed = it->crc;             // the console's save, as the list had it
    if (action == SA_CONFLICT)
    {
        if (it->choice == SC_KEEP_CONSOLE)
            action = SA_UPLOAD;
        else if (it->choice == SC_TAKE_PC)
            action = SA_DOWNLOAD;
        else
            return 0;
    }
    if ((action == SA_DOWNLOAD || action == SA_DOWNLOAD_NEW) && console->backup_only)
        return 0;
    for (int attempt = 1; ; attempt++)
    {
        transient = false;
        msg[0] = '\0';
        switch (action)
        {
        case SA_UPLOAD:
        case SA_BACKUP:
            // Uploading: it becomes the save the other consoles get;
            // backing up (back up only): a copy the PC keeps
            snprintf(what, sizeof(what), action == SA_UPLOAD ? "Uploading %s" : "Backing up %s", it->name);
            r = upload(job, console, server, it, action == SA_UPLOAD ? PUT_SYNC : PUT_BACKUP, what, progress, msg,
                       msgsz);
            if (r > 0)
                it->base = it->crc;
            count = action == SA_UPLOAD ? &counts->uploaded : &counts->backed_up;
            break;
        case SA_DOWNLOAD:
        case SA_DOWNLOAD_NEW:
            r = take_from_pc(job, console, server, it, 0, it->pc_source, 0, chosen ? NULL : &listed, progress, msg,
                             msgsz);
            count = &counts->downloaded;
            break;
        default:
            return 0;
        }
        if (r >= 0 || !transient || attempt >= SYNC_TRIES || !retry_wait(job, attempt, it->name, progress))
            break;
    }
    if (r > 0)
    {
        (*count)++;
        it->done = true;
        it->changed = false;
        it->action = SA_IN_SYNC;
        it->pc_crc = it->crc;
        it->pc_size = it->size;
        if (!saves_write_index(list))
            snprintf(msg, msgsz, "Synced, but can't write\nsaves.idx (SD card full?)");
    }
    else if (r < 0)
    {
        it->failed = true;
        counts->failed++;
        saves_write_index(list);   // what it found (a save changed since the list) for next time
    }
    return r;
}

static int versions_exchange(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                             const SaveItem *it, SaveVersion *out, int max, char *msg, size_t msgsz)
{
    uint8_t req[HEADER_SIZE + 7];
    size_t n = request_header(req, console, OP_HIST);
    memcpy(req + n, it->code, 4);
    put16(req + n + 4, it->hcrc);
    req[n + 6] = it->slot;
    n += 7;

    int sock;
    int r = net(sync_open(job, server, &sock, msg, msgsz));
    uint8_t head[8];
    if (r > 0)
        r = net(sync_send(job, sock, req, n, msg, msgsz));
    if (r > 0)
        r = net(sync_recv(job, sock, head, sizeof(head), msg, msgsz));
    if (r <= 0)
    {
        sync_close(sock);
        return -1;
    }
    if (memcmp(head, "DRSL", 4) != 0 || get16(head + 4) != 0)
    {
        if (memcmp(head, "DRSL", 4) != 0)
            snprintf(msg, msgsz, "DSiRPC's answer is garbled");
        else
            status_msg(msg, msgsz, get16(head + 4));
        sync_close(sock);
        return -1;
    }
    int total = get16(head + 6), kept = 0;
    for (int i = 0; i < total; i++)
    {
        uint8_t p[HIST_ITEM_SIZE];
        char source[256];
        if (net(sync_recv(job, sock, p, sizeof(p), msg, msgsz)) <= 0 ||
            net(sync_recv(job, sock, source, p[13], msg, msgsz)) <= 0)
        {
            sync_close(sock);
            return -1;
        }
        source[p[13]] = '\0';
        if (kept < max)
        {
            SaveVersion *v = &out[kept++];
            v->version = p[0];
            v->time = get32(p + 1);
            v->size = get32(p + 5);
            v->crc = get32(p + 9);
            snprintf(v->source, sizeof(v->source), "%.32s", source);
        }
    }
    sync_close(sock);
    return kept;
}

int saves_versions(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                   const SaveItem *it, SaveVersion *out, int max, char *msg, size_t msgsz)
{
    int r;
    for (int attempt = 1; ; attempt++)
    {
        transient = false;
        msg[0] = '\0';
        r = versions_exchange(job, console, server, it, out, max, msg, msgsz);
        if (r >= 0 || !transient || attempt >= SYNC_TRIES || !retry_wait(job, attempt, "", NULL))
            break;
    }
    return r;
}

int saves_restore(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                  SaveList *list, SaveItem *it, uint8_t version, const char *from, SaveCounts *counts,
                  SaveProgress progress, char *msg, size_t msgsz)
{
    int r;
    for (int attempt = 1; ; attempt++)
    {
        transient = false;
        msg[0] = '\0';
        r = take_from_pc(job, console, server, it, version, from, console->backup_only ? 0 : GET_MAKE_LATEST, NULL,
                         progress, msg, msgsz);
        if (r >= 0 || !transient || attempt >= SYNC_TRIES || !retry_wait(job, attempt, it->name, progress))
            break;
    }
    if (r > 0)
    {
        counts->downloaded++;
        it->done = true;
        it->action = SA_IN_SYNC;
        it->pc_crc = it->crc;
        it->pc_size = it->size;
        if (!saves_write_index(list))
            snprintf(msg, msgsz, "Restored, but can't write\nsaves.idx (SD card full?)");
    }
    else
    {
        counts->failed++;
        saves_write_index(list);
    }
    return r > 0 ? 1 : -1;
}

void saves_done(const SyncJob *job, const SaveConsole *console, const struct sockaddr_in *server,
                const SaveCounts *counts)
{
    uint8_t req[HEADER_SIZE + 8];
    size_t n = request_header(req, console, OP_DONE);
    put16(req + n, counts->uploaded);
    put16(req + n + 2, counts->downloaded);
    put16(req + n + 4, counts->backed_up);
    put16(req + n + 6, counts->failed);
    n += 8;
    char msg[64];
    for (int attempt = 1; attempt <= SYNC_TRIES; attempt++)
    {
        int sock;
        uint8_t answer[6];
        int r = sync_open(job, server, &sock, msg, sizeof(msg));
        if (r > 0)
            r = sync_send(job, sock, req, n, msg, sizeof(msg));
        if (r > 0)
            r = sync_recv(job, sock, answer, sizeof(answer), msg, sizeof(msg));
        sync_close(sock);
        if (r >= 0 || attempt >= SYNC_TRIES || !retry_wait(job, attempt, "", NULL))
            break;
    }
}
