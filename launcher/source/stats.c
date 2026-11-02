// SPDX-License-Identifier: MIT
//
// DSiRPC playtime, kept with DSiRPC (see stats.h). DSiRPC's core/playtime.py
// is the other side and describes the exchange: the console sends its
// numbers, DSiRPC answers with its own, and each side keeps the higher of
// each. A DSiRPC from before playtimes takes the request for an offline
// sync, and turns it down at once ("DRSA"): nothing changes.
//
// stats.idx, written whole after each exchange:
//
//   DSiRPC stats 1
//   pc VIV-MACBOOK
//   ra VampyreVK                  (empty: not signed in)
//   discord 1
//   CPUE 148320 815443200         (code, seconds played, last played)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "stats.h"

#define PROTO_VERSION   2        // with the console's numbers; 1 for a DSiRPC that only knows that
#define BAD_REQUEST     4
#define REQUEST_SIZE    20       // as long as the offline sync's request
#define ANSWER_SIZE     12
#define ENTRY_SIZE      12
#define INDEX_MAGIC     "DSiRPC stats 1"
#define PATH_LEN        512
#define UNLOCK_SLOT     16
#define UNLOCK_FILE     (UNLOCK_SLOT * 256)     // RPCUNLK.BIN (sync.c)

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

static void join_path(char *out, size_t outsz, const char *dir, const char *name)
{
    size_t n = strlen(dir);
    snprintf(out, outsz, (n > 0 && dir[n - 1] == '/') ? "%s%s" : "%s/%s", dir, name);
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

// Printable ASCII only, so a line in stats.idx stays one line
static void clean(char *s)
{
    for (; *s != '\0'; s++)
    {
        if ((unsigned char)*s < 32 || (unsigned char)*s > 126)
            *s = '?';
    }
}

static bool write_index(const char *index_dir, const StatsList *s)
{
    char path[PATH_LEN], tmp[PATH_LEN + 4];
    join_path(path, sizeof(path), index_dir, STATS_INDEX);
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *f = fopen(tmp, "wb");
    if (f == NULL)
        return false;
    fprintf(f, "%s\npc %s\nra %s\ndiscord %d\n", INDEX_MAGIC, s->pc, s->ra_user, s->discord ? 1 : 0);
    for (int i = 0; i < s->count; i++)
        fprintf(f, "%s %u %u\n", s->games[i].code, (unsigned)s->games[i].seconds, (unsigned)s->games[i].last);
    if (fclose(f) != 0)
    {
        remove(tmp);
        return false;
    }
    remove(path);
    return rename(tmp, path) == 0;
}

// One exchange with DSiRPC at server: the request (version 2 with the
// console's numbers, local), the answer into got. 1: done, 0: DSiRPC is from
// before playtimes (or B), -1: failed (msg), -2: DSiRPC only knows version 1.
static int exchange(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                    int version, const StatsList *local, StatsList *got, char *msg, size_t msgsz)
{
    int sock;
    int r = sync_open(job, server, &sock, msg, msgsz);
    if (r <= 0)
        return r;

    int mine = version >= 2 ? local->count : 0;
    size_t size = REQUEST_SIZE + (version >= 2 ? 2 + (size_t)mine * ENTRY_SIZE : 0);
    uint8_t *req = calloc(1, size), *entries = NULL;
    uint8_t head[ANSWER_SIZE];
    if (req == NULL)
    {
        snprintf(msg, msgsz, "Out of memory");
        r = -1;
        goto done;
    }
    memcpy(req, "DRGS", 4);
    put16(req + 4, (uint16_t)version);
    memcpy(req + 6, mac, 6);
    req[12] = (uint8_t)model;
    if (version >= 2)
    {
        put16(req + REQUEST_SIZE, (uint16_t)mine);
        for (int i = 0; i < mine; i++)
        {
            uint8_t *e = req + REQUEST_SIZE + 2 + i * ENTRY_SIZE;
            memcpy(e, local->games[i].code, 4);
            put32(e + 4, local->games[i].seconds);
            put32(e + 8, local->games[i].last);
        }
    }
    if ((r = sync_send(job, sock, req, size, msg, msgsz)) <= 0 ||
        (r = sync_recv(job, sock, head, 4, msg, msgsz)) <= 0)
        goto done;
    if (memcmp(head, "DRGA", 4) != 0)
    {
        // A DSiRPC from before playtimes ("DRSA": not a sync it knows)
        r = 0;
        goto done;
    }
    if ((r = sync_recv(job, sock, head + 4, ANSWER_SIZE - 4, msg, msgsz)) <= 0)
        goto done;
    if (get16(head + 4) == BAD_REQUEST && version >= 2)
    {
        r = -2;
        goto done;
    }
    if (get16(head + 4) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC couldn't send the\nplaytimes (%d)", get16(head + 4));
        r = -1;
        goto done;
    }
    int n = get16(head + 6);
    int pc_len = head[9], ra_len = head[10];
    got->discord = head[8] & 1;
    if (n > STATS_MAX || pc_len >= STATS_TEXT_LEN || ra_len >= STATS_TEXT_LEN)
    {
        snprintf(msg, msgsz, "DSiRPC's playtimes are garbled");
        r = -1;
        goto done;
    }
    if ((r = sync_recv(job, sock, got->pc, pc_len, msg, msgsz)) <= 0 ||
        (r = sync_recv(job, sock, got->ra_user, ra_len, msg, msgsz)) <= 0)
        goto done;
    got->pc[pc_len] = got->ra_user[ra_len] = '\0';
    clean(got->pc);
    clean(got->ra_user);

    entries = malloc((size_t)(n ? n : 1) * ENTRY_SIZE);
    got->games = calloc(n ? n : 1, sizeof(GameStats));
    if (entries == NULL || got->games == NULL)
    {
        snprintf(msg, msgsz, "Out of memory");
        r = -1;
        goto done;
    }
    if (n > 0 && (r = sync_recv(job, sock, entries, (size_t)n * ENTRY_SIZE, msg, msgsz)) <= 0)
        goto done;
    for (int i = 0; i < n; i++)
    {
        const uint8_t *e = entries + i * ENTRY_SIZE;
        if (!valid_code(e))
            continue;
        GameStats *g = &got->games[got->count++];
        memcpy(g->code, e, 4);
        g->code[4] = '\0';
        g->seconds = get32(e + 4);
        g->last = get32(e + 8);
    }
    r = 1;

done:
    sync_close(sock);
    free(req);
    free(entries);
    return r;
}

int stats_fetch(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                const char *index_dir, char *msg, size_t msgsz)
{
    msg[0] = '\0';
    StatsList local, got;
    memset(&got, 0, sizeof(got));
    if (!stats_load(index_dir, &local))
    {
        snprintf(msg, msgsz, "Out of memory");
        return -1;
    }
    int r = exchange(job, mac, model, server, PROTO_VERSION, &local, &got, msg, msgsz);
    if (r < 0)
    {
        // A DSiRPC that only knows version 1 turns 2 down (and may hang up
        // on what it didn't read): ask it the old way, and keep the higher
        // numbers here
        stats_free(&got);
        memset(&got, 0, sizeof(got));
        r = exchange(job, mac, model, server, 1, &local, &got, msg, msgsz);
    }
    if (r == 1)
    {
        // Each game's higher numbers, the console's or the PC's
        GameStats *more = realloc(local.games, (size_t)(local.count + got.count + 1) * sizeof(GameStats));
        if (more == NULL)
        {
            snprintf(msg, msgsz, "Out of memory");
            r = -1;
        }
        else
        {
            local.games = more;
            for (int i = 0; i < got.count; i++)
            {
                const GameStats *pc = &got.games[i];
                GameStats *g = (GameStats *)stats_find(&local, pc->code);
                if (g == NULL && local.count < STATS_MAX)
                    *(g = &local.games[local.count++]) = *pc;
                else if (g != NULL)
                {
                    if (pc->seconds > g->seconds)
                        g->seconds = pc->seconds;
                    if (pc->last > g->last)
                        g->last = pc->last;
                }
            }
            memcpy(local.pc, got.pc, sizeof(local.pc));
            memcpy(local.ra_user, got.ra_user, sizeof(local.ra_user));
            local.discord = got.discord;
            if (!write_index(index_dir, &local))
            {
                snprintf(msg, msgsz, "Can't write %s", STATS_INDEX);
                r = -1;
            }
        }
    }
    stats_free(&local);
    stats_free(&got);
    return r;
}

int stats_add_played(const char *index_dir, const char *unlocks_path)
{
    // A playtime slot: PLAYTIME_ID | game code | seconds | slot u16 | check
    // u16 (the unlocks' check)
    static uint8_t buf[UNLOCK_FILE];
    FILE *f = fopen(unlocks_path, "rb");
    if (f == NULL)
        return 0;
    size_t n = fread(buf, 1, sizeof(buf), f);
    fclose(f);
    if (n < UNLOCK_SLOT || memcmp(buf, "DRUL", 4) != 0)
        return 0;
    StatsList s;
    if (!stats_load(index_dir, &s))
        return -1;
    int added = 0;
    for (size_t at = UNLOCK_SLOT; at + UNLOCK_SLOT <= n; at += UNLOCK_SLOT)
    {
        uint8_t *slot = buf + at;
        uint32_t sum = 0x5AA5;
        for (int w = 0; w < 7; w++)
            sum += get16(slot + w * 2);
        if (get32(slot) != PLAYTIME_ID || !valid_code(slot + 4) || (sum & 0xFFFF) != get16(slot + 14))
            continue;
        char code[5] = { slot[4], slot[5], slot[6], slot[7], '\0' };
        GameStats *g = (GameStats *)stats_find(&s, code);
        if (g == NULL && s.count < STATS_MAX)
        {
            GameStats *more = realloc(s.games, (size_t)(s.count + 1) * sizeof(GameStats));
            if (more == NULL)
                break;
            s.games = more;
            g = &s.games[s.count++];
            memset(g, 0, sizeof(*g));
            memcpy(g->code, code, 5);
        }
        if (g != NULL)
            g->seconds += get32(slot + 8);
        memset(slot, 0, UNLOCK_SLOT);
        added++;
    }
    if (added > 0)
    {
        f = fopen(unlocks_path, "r+b");
        bool ok = f != NULL && fwrite(buf, 1, n, f) == n;
        if (f != NULL && fclose(f) != 0)
            ok = false;
        if (!ok || !write_index(index_dir, &s))
            added = -1;
    }
    stats_free(&s);
    return added;
}

bool stats_load(const char *index_dir, StatsList *out)
{
    memset(out, 0, sizeof(*out));
    char path[PATH_LEN], line[96];
    join_path(path, sizeof(path), index_dir, STATS_INDEX);
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return true;
    if (fgets(line, sizeof(line), f) == NULL || strncmp(line, INDEX_MAGIC, strlen(INDEX_MAGIC)) != 0)
    {
        fclose(f);
        return true;
    }
    int cap = 0;
    while (fgets(line, sizeof(line), f) != NULL)
    {
        line[strcspn(line, "\r\n")] = '\0';
        if (strncmp(line, "pc ", 3) == 0)
        {
            snprintf(out->pc, sizeof(out->pc), "%.32s", line + 3);
            continue;
        }
        if (strncmp(line, "ra ", 3) == 0 || strcmp(line, "ra") == 0)
        {
            snprintf(out->ra_user, sizeof(out->ra_user), "%.32s", line[2] ? line + 3 : "");
            continue;
        }
        if (strncmp(line, "discord ", 8) == 0)
        {
            out->discord = line[8] == '1';
            continue;
        }
        char code[8];
        unsigned secs, last;
        if (sscanf(line, "%7s %u %u", code, &secs, &last) != 3 || strlen(code) != 4 ||
            !valid_code((const uint8_t *)code) || out->count >= STATS_MAX)
            continue;
        if (out->count == cap)
        {
            int ncap = cap ? cap * 2 : 32;
            GameStats *more = realloc(out->games, (size_t)ncap * sizeof(GameStats));
            if (more == NULL)
            {
                fclose(f);
                return false;
            }
            out->games = more;
            cap = ncap;
        }
        GameStats *g = &out->games[out->count++];
        memcpy(g->code, code, 5);
        g->seconds = secs;
        g->last = last;
    }
    fclose(f);
    return true;
}

void stats_free(StatsList *s)
{
    free(s->games);
    s->games = NULL;
    s->count = 0;
}

const GameStats *stats_find(const StatsList *s, const char *code)
{
    for (int i = 0; i < s->count; i++)
    {
        if (strncmp(s->games[i].code, code, 4) == 0)
            return &s->games[i];
    }
    return NULL;
}
