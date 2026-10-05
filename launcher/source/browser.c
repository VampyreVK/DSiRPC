// SPDX-License-Identifier: MIT
//
// A file picker on the bottom screen (see browser.h). The console is 32x24
// characters: a title, the folder, then a page of entries and the controls.
//
//   Up/Down: move   Left/Right: a page at a time
//   A: open the folder / pick the file
//   B: up a folder (at the SD root: back out)   START: back out

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

#include <nds.h>

#include "browser.h"

#define PATH_LEN     512
#define MAX_ENTRIES  1024
#define PAGE_ROWS    18
#define NAME_COLS    29

typedef struct
{
    char *name;
    bool dir;
} Entry;

static Entry *entries;
static int entry_count;

static void free_entries(void)
{
    for (int i = 0; i < entry_count; i++)
        free(entries[i].name);
    free(entries);
    entries = NULL;
    entry_count = 0;
}

static int compare_entries(const void *a, const void *b)
{
    const Entry *x = a, *y = b;
    if (x->dir != y->dir)
        return x->dir ? -1 : 1;
    return strcasecmp(x->name, y->name);
}

static bool has_extension(const char *name, const char *ext)
{
    size_t a = strlen(name), b = strlen(ext);
    return a > b && strcasecmp(name + a - b, ext) == 0;
}

static bool is_root(const char *dir)
{
    const char *colon = strchr(dir, ':');
    return colon != NULL && strcmp(colon, ":/") == 0;
}

static void join(char *out, const char *dir, const char *name)
{
    size_t n = strlen(dir);
    snprintf(out, PATH_LEN, (n > 0 && dir[n - 1] == '/') ? "%s%s" : "%s/%s", dir, name);
}

// "sd:/roms/nds" -> "sd:/roms", "sd:/roms" -> "sd:/". False at the root.
static bool go_up(char *dir, char *child, size_t childsz)
{
    if (is_root(dir))
        return false;
    char *slash = strrchr(dir, '/');
    if (slash == NULL)
        return false;
    snprintf(child, childsz, "%s", slash + 1);
    if (slash > dir && slash[-1] == ':')
        slash[1] = '\0';
    else
        *slash = '\0';
    return true;
}

// Lists the folders and matching files in `dir`, sorted (folders first).
static bool load_dir(const char *dir, const char *ext)
{
    free_entries();
    DIR *d = opendir(dir);
    if (d == NULL)
        return false;
    entries = calloc(MAX_ENTRIES, sizeof(Entry));
    if (entries == NULL)
    {
        closedir(d);
        return false;
    }
    struct dirent *e;
    while (entry_count < MAX_ENTRIES && (e = readdir(d)) != NULL)
    {
        // Skip ".", "..", and hidden files (like macOS's "._Game.nds")
        if (e->d_name[0] == '.')
            continue;
        bool is_dir = e->d_type == DT_DIR;
        if (e->d_type == DT_UNKNOWN)
        {
            char full[PATH_LEN];
            struct stat st;
            join(full, dir, e->d_name);
            is_dir = stat(full, &st) == 0 && S_ISDIR(st.st_mode);
        }
        if (!is_dir && !has_extension(e->d_name, ext))
            continue;
        char *name = strdup(e->d_name);
        if (name == NULL)
            break;
        entries[entry_count].name = name;
        entries[entry_count].dir = is_dir;
        entry_count++;
    }
    closedir(d);
    qsort(entries, entry_count, sizeof(Entry), compare_entries);
    return true;
}

static void draw(const char *title, const char *dir, int sel, int top)
{
    consoleClear();
    printf("%.31s\n", title);
    size_t n = strlen(dir);
    if (n > 31)
        printf("...%s\n", dir + n - 28);
    else
        printf("%s\n", dir);
    printf("-------------------------------\n");
    for (int row = 0; row < PAGE_ROWS; row++)
    {
        int i = top + row;
        if (i >= entry_count)
        {
            printf(row == 0 ? "  (nothing here)\n" : "\n");
            continue;
        }
        const Entry *e = &entries[i];
        int width = e->dir ? NAME_COLS - 1 : NAME_COLS;
        int len = (int)strlen(e->name);
        printf("%s%.*s%s%s\n", i == sel ? "> " : "  ",
               len > width ? width - 1 : width, e->name,
               len > width ? "~" : "", e->dir ? "/" : "");
    }
    printf("-------------------------------\n");
    if (entry_count > 0)
        printf("%d/%d\n", sel + 1, entry_count);
    else
        printf("\n");
    printf("A:open  B:up  START:back");
}

bool browse_for_file(const char *title, const char *start_dir, const char *extension,
                     char *out, size_t outsz)
{
    char dir[PATH_LEN];
    snprintf(dir, sizeof(dir), "%s", start_dir);
    size_t n = strlen(dir);
    if (n > 1 && dir[n - 1] == '/' && !is_root(dir))
        dir[n - 1] = '\0';
    if (!load_dir(dir, extension))
    {
        snprintf(dir, sizeof(dir), "sd:/");
        load_dir(dir, extension);
    }

    int sel = 0, top = 0;
    bool redraw = true;
    keysSetRepeat(15, 4);

    while (1)
    {
        if (redraw)
        {
            if (sel < top)
                top = sel;
            if (sel >= top + PAGE_ROWS)
                top = sel - PAGE_ROWS + 1;
            draw(title, dir, sel, top);
            redraw = false;
        }

        cothread_yield_irq(IRQ_VBLANK);
        scanKeys();
        u32 down = keysDown();
        u32 rep = keysDownRepeat();

        int old = sel;
        if (rep & KEY_UP)
            sel--;
        if (rep & KEY_DOWN)
            sel++;
        if (rep & KEY_LEFT)
            sel -= PAGE_ROWS;
        if (rep & KEY_RIGHT)
            sel += PAGE_ROWS;
        if (sel >= entry_count)
            sel = entry_count - 1;
        if (sel < 0)
            sel = 0;
        if (sel != old)
            redraw = true;

        if ((down & KEY_A) && entry_count > 0)
        {
            char path[PATH_LEN];
            join(path, dir, entries[sel].name);
            if (!entries[sel].dir)
            {
                snprintf(out, outsz, "%s", path);
                free_entries();
                return true;
            }
            if (load_dir(path, extension))
                snprintf(dir, sizeof(dir), "%s", path);
            else
                load_dir(dir, extension);
            sel = top = 0;
            redraw = true;
        }
        else if (down & KEY_B)
        {
            char child[256];
            if (!go_up(dir, child, sizeof(child)))
                break;
            load_dir(dir, extension);
            sel = top = 0;
            for (int i = 0; i < entry_count; i++)
            {
                if (entries[i].dir && strcasecmp(entries[i].name, child) == 0)
                {
                    sel = i;
                    break;
                }
            }
            redraw = true;
        }
        else if (down & KEY_START)
        {
            break;
        }
    }
    free_entries();
    return false;
}
