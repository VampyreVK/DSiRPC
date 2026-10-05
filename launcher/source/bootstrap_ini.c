// SPDX-License-Identifier: MIT
//
// Pointing nds-bootstrap at the game picked in the launcher (see
// bootstrap_ini.h). Plain C with no NDS calls, so it can be tested on a PC.

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

#include "bootstrap_ini.h"

#define PATH_LEN 512
#define LINE_LEN 1024

#define TWLM_SAVES        "sd:/_nds/TWiLightMenu/saves"
#define TWLM_GAMESETTINGS "sd:/_nds/TWiLightMenu/gamesettings"
#define CHEAT_DATA        "sd:/_nds/nds-bootstrap/cheatData.bin"
#define WIDE_CHEAT_DATA   "sd:/_nds/nds-bootstrap/wideCheatData.bin"

// ---------------------------------------------------------------------------
// ini files

static char *trim(char *s)
{
    while (*s == ' ' || *s == '\t')
        s++;
    char *end = s + strlen(s);
    while (end > s && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\r' || end[-1] == '\n'))
        end--;
    *end = '\0';
    return s;
}

// If `line` is a section header, copies its name to `name` and returns true.
static bool section_name(const char *line, char *name, size_t namesz)
{
    while (*line == ' ' || *line == '\t')
        line++;
    if (*line != '[')
        return false;
    const char *end = strchr(line, ']');
    if (end == NULL)
        return false;
    size_t n = (size_t)(end - line - 1);
    if (n >= namesz)
        n = namesz - 1;
    memcpy(name, line + 1, n);
    name[n] = '\0';
    return true;
}

// If `line` is "key = value", returns true with both trimmed (line is
// modified).
static bool key_value(char *line, char **key, char **value)
{
    char *eq = strchr(line, '=');
    if (eq == NULL)
        return false;
    *eq = '\0';
    *key = trim(line);
    *value = trim(eq + 1);
    return **key != '\0' && **key != ';' && **key != '#';
}

int ini_get(const char *path, const char *section, const char *key, char *out, size_t outsz)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return -1;

    char line[LINE_LEN];
    char current[64] = "";
    int found = 0;
    while (fgets(line, sizeof(line), f) != NULL)
    {
        char name[64];
        if (section_name(line, name, sizeof(name)))
        {
            snprintf(current, sizeof(current), "%s", name);
            continue;
        }
        char *k, *v;
        if (strcasecmp(current, section) == 0 && key_value(line, &k, &v) && strcasecmp(k, key) == 0)
        {
            snprintf(out, outsz, "%s", v);
            found = 1;
            break;
        }
    }
    fclose(f);
    return found;
}

static char *read_all(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return NULL;
    char *buf = NULL;
    if (fseek(f, 0, SEEK_END) == 0)
    {
        long size = ftell(f);
        if (size >= 0 && fseek(f, 0, SEEK_SET) == 0)
        {
            buf = malloc((size_t)size + 1);
            if (buf != NULL && fread(buf, 1, (size_t)size, f) != (size_t)size)
            {
                free(buf);
                buf = NULL;
            }
            if (buf != NULL)
            {
                buf[size] = '\0';
                *len = (size_t)size;
            }
        }
    }
    fclose(f);
    return buf;
}

// Writes the keys of `done` that are still false as "key = value" lines.
static void write_missing(FILE *f, const char *const *keys, const char *const *values,
                          bool *done, int count, const char *nl)
{
    for (int i = 0; i < count; i++)
    {
        if (!done[i])
        {
            fprintf(f, "%s = %s%s", keys[i], values[i], nl);
            done[i] = true;
        }
    }
}

int ini_set(const char *path, const char *section, const char *const *keys,
            const char *const *values, int count)
{
    size_t len = 0;
    char *text = read_all(path, &len);
    if (text == NULL)
        return -1;

    const char *nl = strstr(text, "\r\n") != NULL ? "\r\n" : "\n";
    bool *done = calloc((size_t)count, sizeof(bool));
    FILE *f = done != NULL ? fopen(path, "wb") : NULL;
    if (f == NULL)
    {
        free(done);
        free(text);
        return -1;
    }

    bool in_section = false;
    bool seen_section = false;
    char *p = text;
    while (*p != '\0')
    {
        // One line, with its line ending
        char *end = strchr(p, '\n');
        size_t n = end != NULL ? (size_t)(end - p) + 1 : strlen(p);
        char line[LINE_LEN];
        bool fits = n < sizeof(line);
        if (fits)
        {
            memcpy(line, p, n);
            line[n] = '\0';
        }

        char name[64];
        if (fits && section_name(line, name, sizeof(name)))
        {
            if (in_section)  // leaving it: add what wasn't there
                write_missing(f, keys, values, done, count, nl);
            in_section = strcasecmp(name, section) == 0;
            seen_section |= in_section;
        }
        else if (fits && in_section)
        {
            char copy[LINE_LEN];
            memcpy(copy, line, n + 1);
            char *k, *v;
            if (key_value(copy, &k, &v))
            {
                int i;
                for (i = 0; i < count; i++)
                {
                    if (!done[i] && strcasecmp(k, keys[i]) == 0)
                        break;
                }
                if (i < count)
                {
                    fprintf(f, "%s = %s%s", keys[i], values[i], nl);
                    done[i] = true;
                    p += n;
                    continue;
                }
            }
        }
        fwrite(p, 1, n, f);
        if (end == NULL && (in_section || !seen_section))
            fputs(nl, f);  // the last line had no line ending
        p += n;
    }
    if (!seen_section)
        fprintf(f, "[%s]%s", section, nl);
    write_missing(f, keys, values, done, count, nl);

    bool ok = !ferror(f);
    ok &= fclose(f) == 0;
    free(done);
    free(text);
    return ok ? 0 : -1;
}

// ---------------------------------------------------------------------------
// Save files

static bool file_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISREG(st.st_mode);
}

static bool ends_with(const char *s, const char *suffix)
{
    size_t a = strlen(s), b = strlen(suffix);
    return a >= b && strcasecmp(s + a - b, suffix) == 0;
}

// "sd:/roms/nds/Game.nds" -> dir "sd:/roms/nds", name "Game.nds". The
// root gives "sd:", like TWiLight's folder paths without the trailing slash.
static void split_path(const char *path, char *dir, size_t dirsz, const char **name)
{
    const char *slash = strrchr(path, '/');
    if (slash == NULL)
    {
        snprintf(dir, dirsz, "%s", "");
        *name = path;
        return;
    }
    size_t n = (size_t)(slash - path);
    if (n >= dirsz)
        n = dirsz - 1;
    memcpy(dir, path, n);
    dir[n] = '\0';
    *name = slash + 1;
}

// snprintf() into a PATH_LEN buffer; false if the path didn't fit.
static bool make_path(char *out, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int n = vsnprintf(out, PATH_LEN, fmt, args);
    va_end(args);
    return n >= 0 && n < PATH_LEN;
}

// TWiLight's per-game save slot (0 = the plain .sav).
static int save_number(const char *filename)
{
    char path[PATH_LEN], value[16];
    if (!make_path(path, "%s/%s.ini", TWLM_GAMESETTINGS, filename))
        return 0;
    if (ini_get(path, "GAMESETTINGS", "SAVE_NUMBER", value, sizeof(value)) != 1)
        return 0;
    int n = atoi(value);
    return (n >= 1 && n <= 9) ? n : 0;
}

bool find_save(const char *game, const char *prev_nds, const char *prev_sav,
               char *out, size_t outsz)
{
    char dir[PATH_LEN], base[PATH_LEN], ext[] = ".sav0";
    const char *filename;
    split_path(game, dir, sizeof(dir), &filename);
    snprintf(base, sizeof(base), "%s", filename);
    char *dot = strrchr(base, '.');
    if (dot != NULL)
        *dot = '\0';

    int slot = save_number(filename);
    if (slot > 0)
        ext[4] = (char)('0' + slot);
    else
        ext[4] = '\0';

    char cands[4][PATH_LEN];
    int n = 0;
    bool ok = true;

    // Where the last game's save was, relative to the last game
    if (prev_nds != NULL && prev_sav != NULL && prev_sav[0] != '\0' && ends_with(prev_nds, ".nds"))
    {
        char pdir[PATH_LEN], sdir[PATH_LEN], psaves[PATH_LEN + 8];
        const char *unused;
        split_path(prev_nds, pdir, sizeof(pdir), &unused);
        split_path(prev_sav, sdir, sizeof(sdir), &unused);
        snprintf(psaves, sizeof(psaves), "%s/saves", pdir);
        if (strcasecmp(sdir, psaves) == 0)
            ok &= make_path(cands[n++], "%s/saves/%s%s", dir, base, ext);
        else if (strcasecmp(sdir, pdir) == 0)  // "games folder": always .sav
            ok &= make_path(cands[n++], "%s/%s.sav", dir, base);
        else
            ok &= make_path(cands[n++], "%s/%s%s", sdir, base, ext);
    }
    // TWiLight's three save locations
    ok &= make_path(cands[n++], "%s/saves/%s%s", dir, base, ext);
    ok &= make_path(cands[n++], "%s/%s.sav", dir, base);
    ok &= make_path(cands[n++], "%s/%s%s", TWLM_SAVES, base, ext);
    if (!ok)
        return false;  // a path too long to be right

    for (int i = 0; i < n; i++)
    {
        if (file_exists(cands[i]))
        {
            snprintf(out, outsz, "%s", cands[i]);
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------------------------

int bootstrap_ini_prepare(const char *game, char *msg, size_t msgsz)
{
    char prev_nds[PATH_LEN] = "", prev_sav[PATH_LEN] = "";
    int r = ini_get(BOOTSTRAP_INI_PATH, BOOTSTRAP_SECTION, "NDS_PATH", prev_nds, sizeof(prev_nds));
    if (r < 0)
    {
        snprintf(msg, msgsz, "Can't read %s.\nLaunch any game from TWiLight\nMenu++ once, then try again.",
                 BOOTSTRAP_INI_PATH);
        return -1;
    }
    if (r == 1 && strcasecmp(prev_nds, game) == 0)
        return 0;  // already set up for this game

    ini_get(BOOTSTRAP_INI_PATH, BOOTSTRAP_SECTION, "SAV_PATH", prev_sav, sizeof(prev_sav));

    char sav[PATH_LEN];
    if (!find_save(game, prev_nds, prev_sav, sav, sizeof(sav)))
    {
        snprintf(msg, msgsz, "This game has no save file\nyet. Start it once from\nTWiLight Menu++ to make one.");
        return -1;
    }

    const char *keys[] = {
        "NDS_PATH", "SAV_PATH", "HOMEBREW_ARG", "MANUAL_PATH",
        "DONOR_SDK_VER", "PATCH_MPU_REGION", "PATCH_MPU_SIZE",
    };
    const char *values[] = {
        game, sav, "", "",
        "0", "0", "0",
    };
    if (ini_set(BOOTSTRAP_INI_PATH, BOOTSTRAP_SECTION, keys, values, 7) != 0)
    {
        snprintf(msg, msgsz, "Can't write %s.", BOOTSTRAP_INI_PATH);
        return -1;
    }

    // The last game's cheats (and 3DS widescreen patch) must not be applied
    // to this one. TWiLight removes or rewrites these on every launch.
    remove(CHEAT_DATA);
    remove(WIDE_CHEAT_DATA);
    return 0;
}
