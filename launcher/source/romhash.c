// SPDX-License-Identifier: MIT
//
// RetroAchievements' DS hash (see romhash.h): a port of rcheevos 12.5's
// rc_hash_nintendo_ds() (src/rhash/hash_rom.c), the same as DSiRPC's
// core/ra_hash.py, read in chunks so a progress bar can move.

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "md5.h"
#include "romhash.h"

#define CHUNK     (32 * 1024)
#define HEADER    512
#define ICON_SIZE 0xA00

static uint8_t chunk[CHUNK];

static uint32_t get32(const uint8_t *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

// size bytes from at into the hash, zeros for any past the end of the file
// (as rcheevos pads a short block)
static bool add_part(FILE *f, uint32_t at, uint32_t size, Md5 *m, uint32_t *done, uint32_t total,
                     RomHashProgress progress, void *ctx)
{
    bool past_end = fseek(f, (long)at, SEEK_SET) != 0;
    while (size > 0)
    {
        size_t n = size < CHUNK ? size : CHUNK;
        size_t got = past_end ? 0 : fread(chunk, 1, n, f);
        if (got < n)
        {
            if (ferror(f))
                return false;
            memset(chunk + got, 0, n - got);
            past_end = true;
        }
        md5_update(m, chunk, n);
        size -= (uint32_t)n;
        *done += (uint32_t)n;
        if (progress != NULL)
            progress(*done, total, ctx);
    }
    return true;
}

int rom_hash(const char *path, uint8_t out[16], RomHashProgress progress, void *ctx)
{
    uint8_t header[HEADER];
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return ROMHASH_UNREADABLE;
    if (fread(header, 1, HEADER, f) != HEADER)
    {
        bool err = ferror(f);
        fclose(f);
        return err ? ROMHASH_UNREADABLE : ROMHASH_NOT_DS;
    }
    // A SuperCard's own header comes first: the game's is the next 512 bytes
    uint32_t offset = 0;
    static const uint8_t SC_START[4] = { 0x2E, 0x00, 0x00, 0xEA }, SC_MARK[4] = { 0x44, 0x46, 0x96, 0x00 };
    if (memcmp(header, SC_START, 4) == 0 && memcmp(header + 0xB0, SC_MARK, 4) == 0)
    {
        offset = HEADER;
        memset(header, 0, HEADER);
        if (fseek(f, HEADER, SEEK_SET) != 0 || (fread(header, 1, HEADER, f) == 0 && ferror(f)))
        {
            fclose(f);
            return ROMHASH_UNREADABLE;
        }
    }
    uint32_t arm9_at = get32(header + 0x20), arm9_size = get32(header + 0x2C);
    uint32_t arm7_at = get32(header + 0x30), arm7_size = get32(header + 0x3C);
    uint32_t icon_at = get32(header + 0x68);
    if (arm9_size > 16u * 1024 * 1024 || arm7_size > 16u * 1024 * 1024 - arm9_size)
    {
        fclose(f);
        return ROMHASH_NOT_DS;
    }
    uint32_t total = 0x160 + arm9_size + arm7_size + ICON_SIZE, done = 0x160;
    Md5 m;
    md5_init(&m);
    md5_update(&m, header, 0x160);
    bool ok = add_part(f, arm9_at + offset, arm9_size, &m, &done, total, progress, ctx) &&
              add_part(f, arm7_at + offset, arm7_size, &m, &done, total, progress, ctx) &&
              add_part(f, icon_at + offset, ICON_SIZE, &m, &done, total, progress, ctx);
    fclose(f);
    if (!ok)
        return ROMHASH_UNREADABLE;
    md5_final(&m, out);
    return ROMHASH_OK;
}
