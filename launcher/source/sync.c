// SPDX-License-Identifier: MIT
//
// Offline play: the launcher's half of the sync with DSiRPC (see sync.h).
// The files and the exchange are described in DSiRPC's core/offline.py. The
// launcher only moves bytes: it never looks past a set's header, and it hands
// the unlock file over as it is.
//
// The sockets are non-blocking, and every wait yields a frame at a time, so
// B can stop it and the screen stays responsive. It also builds on a PC
// (without __NDS__), which is how it's tested against DSiRPC.

#include <dirent.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/ioctl.h>
#include <sys/socket.h>

#include "sync.h"

#ifdef __NDS__
#include <nds.h>
#define next_frame()     cothread_yield_irq(IRQ_VBLANK)
#define close_socket(s)  closesocket(s)
#define SEND_FLAGS       0
#else
#include <poll.h>
#define next_frame()     usleep(16667)
#define close_socket(s)  close(s)
#define SEND_FLAGS       MSG_NOSIGNAL
#endif

#ifndef SYNC_DISCOVER_ADDR
#define SYNC_DISCOVER_ADDR INADDR_BROADCAST
#endif

#define SYNC_VERSION      1

#define UNLOCK_SLOT       16
#define UNLOCK_SLOTS      256
#define UNLOCK_FILE_SIZE  (UNLOCK_SLOT * UNLOCK_SLOTS)

#define SET_HEADER_SIZE   32
#define MAX_SETS          512                // cached sets named in a request
#define MAX_SET_SIZE      (1024 * 1024)

#define REQUEST_SIZE      20
#define ANSWER_SIZE       16

#define DISCOVER_FRAMES   90                 // 1.5 s for DSiRPC to answer
#define RESEND_FRAMES     30                 // asking again every 0.5 s
#define CONNECT_FRAMES    (5 * 60)
#define IDLE_FRAMES       (30 * 60)          // DSiRPC may be downloading a set

#define PATH_LEN          512
#define CHUNK             4096

static const char DISCOVER[12] = "DSiRPC sync?";   // + u8 version
static const char ANSWER[12]   = "DSiRPC sync!";   // + u8 version + u16 TCP port

static uint8_t unlock_buf[UNLOCK_FILE_SIZE];
static uint8_t stamp_buf[MAX_SETS * 8];
static uint8_t chunk_buf[CHUNK];

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

// A game code: 4 of A-Z and 0-9. Stops at the first other byte, so a
// shorter string is safe to pass.
static bool valid_code(const void *code)
{
    const uint8_t *c = code;
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

static void set_path(char *out, size_t outsz, const char *dir, const void *code, const char *ext)
{
    char name[16];
    snprintf(name, sizeof(name), "%.4s.%s", (const char *)code, ext);
    join_path(out, outsz, dir, name);
}

static size_t read_file(const char *path, uint8_t *buf, size_t max, bool *longer)
{
    *longer = false;
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return 0;
    size_t n = fread(buf, 1, max, f);
    if (n == max && fgetc(f) != EOF)
        *longer = true;
    fclose(f);
    return n;
}

static bool copy_file(const char *from, const char *to)
{
    FILE *in = fopen(from, "rb");
    if (in == NULL)
        return false;
    FILE *out = fopen(to, "wb");
    if (out == NULL)
    {
        fclose(in);
        return false;
    }
    bool ok = true;
    size_t n;
    while ((n = fread(chunk_buf, 1, sizeof(chunk_buf), in)) > 0)
    {
        if (fwrite(chunk_buf, 1, n, out) != n)
        {
            ok = false;
            break;
        }
    }
    if (ferror(in))
        ok = false;
    fclose(in);
    if (fclose(out) != 0)
        ok = false;
    if (!ok)
        remove(to);
    return ok;
}

// ---------------------------------------------------------------------------
// RPCUNLK.BIN

static bool unlock_header_ok(const uint8_t *buf, size_t n)
{
    return n >= UNLOCK_SLOT && memcmp(buf, "DRUL", 4) == 0 && get16(buf + 4) == SYNC_VERSION &&
           get16(buf + 6) == UNLOCK_SLOT && get16(buf + 8) == UNLOCK_SLOTS;
}

// The slots DSiRPC will take: an ID, a valid code and a matching check
// (core/offline.py counts them the same way).
static int count_unlocks(const uint8_t *buf, size_t n)
{
    if (!unlock_header_ok(buf, n))
        return 0;
    size_t slots = n / UNLOCK_SLOT;
    if (slots > UNLOCK_SLOTS)
        slots = UNLOCK_SLOTS;

    int count = 0;
    for (size_t i = 1; i < slots; i++)
    {
        const uint8_t *s = buf + i * UNLOCK_SLOT;
        uint32_t sum = 0x5AA5;
        for (int w = 0; w < 7; w++)
            sum += get16(s + w * 2);
        if (get32(s) != 0 && valid_code(s + 4) && (sum & 0xFFFF) == get16(s + 14))
            count++;
    }
    return count;
}

int unlocks_prepare(const char *path)
{
    bool longer;
    size_t n = read_file(path, unlock_buf, sizeof(unlock_buf), &longer);
    bool ours = unlock_header_ok(unlock_buf, n);
    if (ours && n == UNLOCK_FILE_SIZE && !longer)
        return count_unlocks(unlock_buf, n);

    // Missing, the wrong size or not ours: write it out at full size,
    // keeping any unlocks that were in it.
    if (ours)
        memset(unlock_buf + n, 0, sizeof(unlock_buf) - n);
    else
        memset(unlock_buf, 0, sizeof(unlock_buf));
    memcpy(unlock_buf, "DRUL", 4);
    put16(unlock_buf + 4, SYNC_VERSION);
    put16(unlock_buf + 6, UNLOCK_SLOT);
    put16(unlock_buf + 8, UNLOCK_SLOTS);

    FILE *f = fopen(path, "wb");
    if (f == NULL)
        return -1;
    bool ok = fwrite(unlock_buf, 1, sizeof(unlock_buf), f) == sizeof(unlock_buf);
    if (fclose(f) != 0 || !ok)
        return -1;
    return count_unlocks(unlock_buf, sizeof(unlock_buf));
}

// Zeroes every unlock slot in place (DSiRPC has them), keeping the header.
static bool clear_unlocks(const char *path)
{
    static const uint8_t zeros[UNLOCK_FILE_SIZE - UNLOCK_SLOT];
    FILE *f = fopen(path, "r+b");
    if (f == NULL)
        return false;
    bool ok = fseek(f, UNLOCK_SLOT, SEEK_SET) == 0 &&
              fwrite(zeros, 1, sizeof(zeros), f) == sizeof(zeros);
    if (fclose(f) != 0)
        ok = false;
    return ok;
}

// ---------------------------------------------------------------------------
// Sets

static bool read_set_header(const char *path, uint8_t header[SET_HEADER_SIZE])
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return false;
    size_t n = fread(header, 1, SET_HEADER_SIZE, f);
    fclose(f);
    return n == SET_HEADER_SIZE && memcmp(header, "DRSE", 4) == 0 &&
           get16(header + 4) == SYNC_VERSION && valid_code(header + 8);
}

// The sets already on the SD card, as (code, stamp) pairs in stamp_buf.
static int list_cached_sets(const char *dir)
{
    DIR *d = opendir(dir);
    if (d == NULL)
        return 0;

    int count = 0;
    struct dirent *e;
    char path[PATH_LEN];
    uint8_t header[SET_HEADER_SIZE];
    while ((e = readdir(d)) != NULL && count < MAX_SETS)
    {
        if (e->d_type == DT_DIR || strlen(e->d_name) != 8 || strcasecmp(e->d_name + 4, ".DRS") != 0)
            continue;
        join_path(path, sizeof(path), dir, e->d_name);
        if (!read_set_header(path, header) || strncasecmp((const char *)header + 8, e->d_name, 4) != 0)
            continue;
        memcpy(stamp_buf + count * 8, header + 8, 4);
        memcpy(stamp_buf + count * 8 + 4, header + 16, 4);
        count++;
    }
    closedir(d);
    return count;
}

bool stage_set(const char *sets_dir, const char *game, const char *dest)
{
    char src[PATH_LEN];
    uint8_t header[SET_HEADER_SIZE];
    if (valid_code(game))
    {
        set_path(src, sizeof(src), sets_dir, game, "DRS");
        if (read_set_header(src, header) && memcmp(header + 8, game, 4) == 0 && copy_file(src, dest))
            return true;
    }
    remove(dest);
    return false;
}

void read_game_code(const char *nds_path, char code[5])
{
    uint8_t c[4];
    code[0] = '\0';
    FILE *f = fopen(nds_path, "rb");
    if (f == NULL)
        return;
    bool ok = fseek(f, 0x0C, SEEK_SET) == 0 && fread(c, 1, 4, f) == 4;
    fclose(f);
    if (ok && valid_code(c))
    {
        memcpy(code, c, 4);
        code[4] = '\0';
    }
}

// ---------------------------------------------------------------------------
// The network

static void say(const SyncJob *job, const char *text)
{
    if (job->say != NULL)
        job->say(text);
}

static bool stop_requested(const SyncJob *job)
{
    return job->cancelled != NULL && job->cancelled();
}

static void set_nonblocking(int sock)
{
    int on = 1;
    ioctl(sock, FIONBIO, &on);
}

static bool would_block(void)
{
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINPROGRESS;
}

// Asks for DSiRPC with a broadcast. 1: found (server set), 0: no answer or
// skipped, -1: failed (msg).
static int discover(const SyncJob *job, struct sockaddr_in *server, char *msg, size_t msgsz)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        snprintf(msg, msgsz, "Can't open a UDP socket");
        return -1;
    }
    int on = 1;
    setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &on, sizeof(on));  // lwIP needs it
    set_nonblocking(sock);

    struct sockaddr_in to;
    memset(&to, 0, sizeof(to));
    to.sin_family = AF_INET;
    to.sin_port = htons(SYNC_PORT);
    to.sin_addr.s_addr = htonl(SYNC_DISCOVER_ADDR);

    uint8_t ask[sizeof(DISCOVER) + 1];
    memcpy(ask, DISCOVER, sizeof(DISCOVER));
    ask[sizeof(DISCOVER)] = SYNC_VERSION;

    int result = 0;
    snprintf(msg, msgsz, "DSiRPC wasn't found");
    for (int frame = 0; frame < DISCOVER_FRAMES && result == 0; frame++)
    {
        if (frame % RESEND_FRAMES == 0)
            sendto(sock, ask, sizeof(ask), 0, (struct sockaddr *)&to, sizeof(to));
        next_frame();
        if (stop_requested(job))
        {
            snprintf(msg, msgsz, "Sync skipped");
            break;
        }

        uint8_t got[32];
        struct sockaddr_in from;
        socklen_t fromlen = sizeof(from);
        int n;
        while (result == 0 &&
               (n = recvfrom(sock, got, sizeof(got), 0, (struct sockaddr *)&from, &fromlen)) > 0)
        {
            if (n >= (int)sizeof(ANSWER) + 3 && memcmp(got, ANSWER, sizeof(ANSWER)) == 0)
            {
                if (got[sizeof(ANSWER)] != SYNC_VERSION)
                {
                    snprintf(msg, msgsz, "DSiRPC and this launcher\nare from different releases\n(sync version %d, not %d)",
                             got[sizeof(ANSWER)], SYNC_VERSION);
                    result = -1;
                }
                else
                {
                    *server = from;
                    server->sin_port = htons(get16(got + sizeof(ANSWER) + 1));
                    msg[0] = '\0';
                    result = 1;
                }
            }
            fromlen = sizeof(from);
        }
    }
    close_socket(sock);
    return result;
}

// 1: connected, 0: skipped, -1: failed (msg).
static int connect_to(const SyncJob *job, int sock, const struct sockaddr_in *server, char *msg, size_t msgsz)
{
    if (connect(sock, (const struct sockaddr *)server, sizeof(*server)) == 0)
        return 1;

    for (int frame = 0; frame < CONNECT_FRAMES; frame++)
    {
        struct pollfd p = { .fd = sock, .events = POLLOUT, .revents = 0 };
        int r = poll(&p, 1, 0);
        if (r < 0)
            break;
        if (r > 0)
        {
            int err = -1;
            socklen_t len = sizeof(err);
            if ((p.revents & POLLOUT) && getsockopt(sock, SOL_SOCKET, SO_ERROR, &err, &len) == 0 && err == 0)
                return 1;
            break;
        }
        next_frame();
        if (stop_requested(job))
        {
            snprintf(msg, msgsz, "Sync skipped");
            return 0;
        }
    }
    snprintf(msg, msgsz, "DSiRPC answered, but its\nport %d can't be reached\n(a firewall?)", ntohs(server->sin_port));
    return -1;
}

// 1: all sent, 0: skipped, -1: failed (msg).
static int send_all(const SyncJob *job, int sock, const void *data, size_t len, char *msg, size_t msgsz)
{
    const uint8_t *p = data;
    int idle = 0;
    while (len > 0)
    {
        int n = send(sock, p, len, SEND_FLAGS);
        if (n > 0)
        {
            p += n;
            len -= n;
            idle = 0;
            continue;
        }
        if (n < 0 && !would_block())
        {
            snprintf(msg, msgsz, "Lost DSiRPC while sending");
            return -1;
        }
        next_frame();
        if (stop_requested(job))
        {
            snprintf(msg, msgsz, "Sync skipped");
            return 0;
        }
        if (++idle > IDLE_FRAMES)
        {
            snprintf(msg, msgsz, "DSiRPC stopped answering");
            return -1;
        }
    }
    return 1;
}

// 1: got all len bytes, 0: skipped, -1: failed (msg).
static int recv_all(const SyncJob *job, int sock, void *data, size_t len, char *msg, size_t msgsz)
{
    uint8_t *p = data;
    int idle = 0;
    while (len > 0)
    {
        int n = recv(sock, p, len, 0);
        if (n > 0)
        {
            p += n;
            len -= n;
            idle = 0;
            continue;
        }
        if (n == 0 || !would_block())
        {
            snprintf(msg, msgsz, "Lost DSiRPC while receiving");
            return -1;
        }
        next_frame();
        if (stop_requested(job))
        {
            snprintf(msg, msgsz, "Sync skipped");
            return 0;
        }
        if (++idle > IDLE_FRAMES)
        {
            snprintf(msg, msgsz, "DSiRPC stopped answering");
            return -1;
        }
    }
    return 1;
}

// Receives one set into sets_dir/CODE.DRS (through CODE.TMP, so a set that
// doesn't arrive whole never replaces the old one). 1: received (with a
// warning in msg if it wasn't saved), 0: skipped, -1: failed (msg).
static int receive_set(const SyncJob *job, int sock, const uint8_t code[4], uint32_t size,
                       bool *saved, char *msg, size_t msgsz)
{
    char tmp[PATH_LEN], final[PATH_LEN];
    set_path(tmp, sizeof(tmp), job->sets_dir, code, "TMP");
    set_path(final, sizeof(final), job->sets_dir, code, "DRS");

    FILE *f = fopen(tmp, "wb");
    bool ok = f != NULL;
    bool garbled = false;
    uint32_t done = 0;
    while (done < size)
    {
        size_t n = size - done < CHUNK ? size - done : CHUNK;
        int r = recv_all(job, sock, chunk_buf, n, msg, msgsz);
        if (r <= 0)
        {
            if (f != NULL)
                fclose(f);
            remove(tmp);
            return r;
        }
        if (done == 0 && (n < SET_HEADER_SIZE || memcmp(chunk_buf, "DRSE", 4) != 0 ||
                          memcmp(chunk_buf + 8, code, 4) != 0))
            garbled = true;  // not what it says it is: read past it, keep the old one
        if (ok && !garbled && fwrite(chunk_buf, 1, n, f) != n)
            ok = false;
        done += n;
    }
    if (f != NULL && fclose(f) != 0)
        ok = false;
    if (ok && !garbled)
    {
        remove(final);
        ok = rename(tmp, final) == 0;
    }
    *saved = ok && !garbled;
    if (!*saved)
    {
        remove(tmp);
        snprintf(msg, msgsz, garbled ? "DSiRPC's %.4s set is garbled;\nkept the old one"
                                     : "Can't save the %.4s set\n(is the SD card full?)",
                 (const char *)code);
    }
    return 1;
}

int sync_with_dsirpc(const SyncJob *job, SyncResult *result, char *msg, size_t msgsz)
{
    memset(result, 0, sizeof(*result));
    msg[0] = '\0';

    say(job, "Looking for DSiRPC...");
    struct sockaddr_in server;
    int r = discover(job, &server, msg, msgsz);
    if (r <= 0)
        return r;
    snprintf(result->server, sizeof(result->server), "%s", inet_ntoa(server.sin_addr));

    char text[48];
    snprintf(text, sizeof(text), "Found DSiRPC at %s", result->server);
    say(job, text);

    // What the console has: the sets' stamps and the waiting unlocks
    mkdir(job->sets_dir, 0777);
    int n_cached = list_cached_sets(job->sets_dir);
    bool longer;
    size_t unlock_len = read_file(job->unlocks_path, unlock_buf, sizeof(unlock_buf), &longer);
    if (!unlock_header_ok(unlock_buf, unlock_len))
        unlock_len = 0;
    int waiting = count_unlocks(unlock_buf, unlock_len);

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0)
    {
        snprintf(msg, msgsz, "Can't open a TCP socket");
        return -1;
    }
    set_nonblocking(sock);

    r = connect_to(job, sock, &server, msg, msgsz);
    if (r <= 0)
        goto done;

    uint8_t head[REQUEST_SIZE];
    memcpy(head, "DRSQ", 4);
    put16(head + 4, SYNC_VERSION);
    put16(head + 6, n_cached);
    memset(head + 8, 0, 4);
    if (valid_code(job->game))
        memcpy(head + 8, job->game, 4);
    put32(head + 12, unlock_len);
    put32(head + 16, 0);

    if ((r = send_all(job, sock, head, sizeof(head), msg, msgsz)) <= 0 ||
        (r = send_all(job, sock, stamp_buf, n_cached * 8, msg, msgsz)) <= 0 ||
        (r = send_all(job, sock, unlock_buf, unlock_len, msg, msgsz)) <= 0)
        goto done;

    uint8_t answer[ANSWER_SIZE];
    if ((r = recv_all(job, sock, answer, sizeof(answer), msg, msgsz)) <= 0)
        goto done;
    if (memcmp(answer, "DRSA", 4) != 0 || get16(answer + 4) != SYNC_VERSION)
    {
        snprintf(msg, msgsz, "DSiRPC's answer is garbled");
        r = -1;
        goto done;
    }
    if (get16(answer + 6) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC couldn't read what\nthe launcher sent (%d)", get16(answer + 6));
        r = -1;
        goto done;
    }

    // DSiRPC has the unlocks now. It counts them the way the launcher does,
    // so a different count means something went wrong on the way: keep them
    // for the next time, rather than lose any.
    int taken = get16(answer + 8);
    if (waiting > 0 && taken == waiting)
    {
        if (clear_unlocks(job->unlocks_path))
            result->unlocks_sent = taken;
        else
            snprintf(msg, msgsz, "Can't clear RPCUNLK.BIN;\nDSiRPC gets them again next\ntime (no harm done)");
    }
    else if (taken != waiting)
    {
        snprintf(msg, msgsz, "DSiRPC took %d of %d unlocks;\nthey stay on the SD card", taken, waiting);
    }

    int n_sets = get16(answer + 10);
    for (int i = 0; i < n_sets; i++)
    {
        uint8_t entry[8];
        if ((r = recv_all(job, sock, entry, sizeof(entry), msg, msgsz)) <= 0)
            goto done;
        uint32_t size = get32(entry + 4);
        if (!valid_code(entry) || size < SET_HEADER_SIZE || size > MAX_SET_SIZE)
        {
            snprintf(msg, msgsz, "DSiRPC's answer is garbled");
            r = -1;
            goto done;
        }
        snprintf(text, sizeof(text), "Saving the %.4s set...", (const char *)entry);
        say(job, text);

        bool saved;
        if ((r = receive_set(job, sock, entry, size, &saved, msg, msgsz)) <= 0)
            goto done;
        if (saved)
            result->sets_received++;
    }
    r = 1;

done:
    close_socket(sock);
    return r;
}
