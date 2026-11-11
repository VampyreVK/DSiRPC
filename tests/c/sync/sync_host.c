// The launcher's achievement sync (launcher/source/sync.c) on the PC, against
// DSiRPC's ConsoleSync on this machine (tests/test_rom_hashes.py). Built with
// -DSYNC_VERSION=1 it stands in for a launcher from before the games' hashes.
//
//   sync_host <port> <sets dir> <unlocks file> <game code or -> [<hashes file>]
//
// The hashes file: a line each, "<code> <md5 hex> <started 0/1> <file name>". Prints
// "sync <result> <version> <unlocks sent> <sets received> <statuses>", then
// "status <md5 hex> <status>" for each, and "msg <text>" (and "say <text>"
// for what the screen shows as it goes).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>

#include "sync.h"

static void say_line(const char *text)
{
    printf("say %s\n", text);
}

int main(int argc, char **argv)
{
    if (argc < 5)
        return 2;
    static uint8_t roms[256 * (SYNC_ROM_RECORD + 64)];
    int n = 0;
    size_t size = 0;
    if (argc >= 6)
    {
        FILE *f = fopen(argv[5], "r");
        char code[8], hex[40], name[64];
        int started;
        while (f != NULL && n < 256 && fscanf(f, "%7s %39s %d %63s", code, hex, &started, name) == 4)
        {
            uint8_t *r = roms + size;
            memset(r, 0, SYNC_ROM_RECORD);
            memcpy(r, code, 4);
            for (int i = 0; i < 16; i++)
            {
                unsigned v;
                sscanf(hex + 2 * i, "%2x", &v);
                r[4 + i] = (uint8_t)v;
            }
            r[20] = (uint8_t)started;
            r[21] = (uint8_t)strlen(name);
            memcpy(r + SYNC_ROM_RECORD, name, r[21]);
            size += SYNC_ROM_RECORD + r[21];
            n++;
        }
        if (f != NULL)
            fclose(f);
    }
    SyncJob job = {
        .sets_dir = argv[2],
        .unlocks_path = argv[3],
        .server_addr = inet_addr("127.0.0.1"),
        .port = (uint16_t)atoi(argv[1]),
        .roms = n ? roms : NULL,
        .n_roms = n,
        .roms_size = size,
        .hashed = (uint16_t)n,
        .hash_ms = 1234,
        .say = say_line,
    };
    snprintf(job.game, sizeof(job.game), "%s", strcmp(argv[4], "-") == 0 ? "" : argv[4]);
    SyncResult result;
    char msg[160];
    int r = sync_with_dsirpc(&job, &result, msg, sizeof(msg));
    printf("sync %d %d %d %d %d\n", r, result.version, result.unlocks_sent, result.sets_received, result.n_status);
    for (int i = 0; i < result.n_status; i++)
    {
        const uint8_t *s = result.rom_status + i * SYNC_STATUS_RECORD;
        printf("status ");
        for (int k = 0; k < 16; k++)
            printf("%02x", s[k]);
        printf(" %d\n", s[16]);
    }
    free(result.rom_status);
    printf("msg %s\n", msg);
    return 0;
}
