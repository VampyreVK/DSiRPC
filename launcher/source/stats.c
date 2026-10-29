// SPDX-License-Identifier: MIT
//
// Playtime from DSiRPC (see stats.h). DSiRPC's core/playtime.py is the other
// side and describes the exchange. A DSiRPC from before it takes the request
// for an offline sync, and turns it down at once ("DRSA"): nothing to show.
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

#define PROTO_VERSION   1
#define REQUEST_SIZE    20       // as long as the offline sync's request
#define ANSWER_SIZE     12
#define ENTRY_SIZE      12
#define INDEX_MAGIC     "DSiRPC stats 1"
#define PATH_LEN        512

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

int stats_fetch(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                const char *index_dir, char *msg, size_t msgsz)
{
    msg[0] = '\0';
    int sock;
    int r = sync_open(job, server, &sock, msg, msgsz);
    if (r <= 0)
        return r;

    uint8_t req[REQUEST_SIZE];
    memset(req, 0, sizeof(req));
    memcpy(req, "DRGS", 4);
    put16(req + 4, PROTO_VERSION);
    memcpy(req + 6, mac, 6);
    req[12] = (uint8_t)model;

    StatsList s;
    memset(&s, 0, sizeof(s));
    uint8_t *entries = NULL;
    uint8_t head[ANSWER_SIZE];
    if ((r = sync_send(job, sock, req, sizeof(req), msg, msgsz)) <= 0 ||
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
    if (get16(head + 4) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC couldn't send the\nplaytimes (%d)", get16(head + 4));
        r = -1;
        goto done;
    }
    int n = get16(head + 6);
    int pc_len = head[9], ra_len = head[10];
    s.discord = head[8] & 1;
    if (n > STATS_MAX || pc_len >= STATS_TEXT_LEN || ra_len >= STATS_TEXT_LEN)
    {
        snprintf(msg, msgsz, "DSiRPC's playtimes are garbled");
        r = -1;
        goto done;
    }
    if ((r = sync_recv(job, sock, s.pc, pc_len, msg, msgsz)) <= 0 ||
        (r = sync_recv(job, sock, s.ra_user, ra_len, msg, msgsz)) <= 0)
        goto done;
    s.pc[pc_len] = s.ra_user[ra_len] = '\0';
    clean(s.pc);
    clean(s.ra_user);

    entries = malloc((size_t)(n ? n : 1) * ENTRY_SIZE);
    s.games = calloc(n ? n : 1, sizeof(GameStats));
    if (entries == NULL || s.games == NULL)
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
        GameStats *g = &s.games[s.count++];
        memcpy(g->code, e, 4);
        g->code[4] = '\0';
        g->seconds = get32(e + 4);
        g->last = get32(e + 8);
    }
    if (!write_index(index_dir, &s))
    {
        snprintf(msg, msgsz, "Can't write %s", STATS_INDEX);
        r = -1;
        goto done;
    }
    r = 1;

done:
    sync_close(sock);
    free(entries);
    free(s.games);
    return r;
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
