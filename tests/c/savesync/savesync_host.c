// The launcher's save sync (launcher/source/savesync.c, sync.c, settings.c)
// on the PC, driven by tests/test_save_sync.py against DSiRPC's ConsoleSync
// on loopback. One command per line on stdin, fields after the command
// separated by '|':
//
//   console MAC(12 hex)|model|sync or backup
//   scan games_dir|index_dir        item lines: name|slot|present|changed|excluded|crc|base|path
//   plan                            action lines: name|slot|action|pc_crc|versions|source
//                                   (saves.idx written after it, as the screen does)
//   sync name|slot[|keep or take]   (name "*": every item with something to do)
//   exclude name|slot
//   versions name|slot              version lines: version|size|crc|source
//   restore name|slot|version
//   quick games_dir|index_dir
//   done
//   settings path|ip or -|sync or backup[|last game]   (writes them, reads them back)
//
// argv[1]: DSiRPC's TCP port (the console looks for it at 127.0.0.1).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "savesync.h"
#include "settings.h"

static SyncJob job;
static SaveConsole console;
static SaveList list;
static struct sockaddr_in server;
static SaveCounts counts;

static int split(char *rest, char **field, int max)
{
    int n = 0;
    while (n < max)
    {
        field[n++] = rest;
        char *bar = strchr(rest, '|');
        if (bar == NULL)
            break;
        *bar = '\0';
        rest = bar + 1;
    }
    return n;
}

static SaveItem *find(const char *name, int slot)
{
    for (int i = 0; i < list.count; i++)
    {
        if (strcmp(list.items[i].name, name) == 0 && list.items[i].slot == slot)
            return &list.items[i];
    }
    return NULL;
}

static void print_items(void)
{
    printf("items %d roms %d\n", list.count, list.roms);
    for (int i = 0; i < list.count; i++)
    {
        SaveItem *it = &list.items[i];
        printf("item %s|%d|%d|%d|%d|%08X|%08X|%s\n", it->name, it->slot, it->present, it->changed, it->excluded,
               it->crc, it->base, it->path);
    }
}

static void sync_one(SaveItem *it, const char *how)
{
    if (how != NULL && strcmp(how, "keep") == 0)
        it->choice = SC_KEEP_CONSOLE;
    else if (how != NULL && strcmp(how, "take") == 0)
        it->choice = SC_TAKE_PC;
    char msg[160];
    int r = saves_sync_item(&job, &console, &server, &list, it, &counts, NULL, msg, sizeof(msg));
    printf("sync %s|%d %d %s\n", it->name, it->slot, r, msg);
}

int main(int argc, char *argv[])
{
    if (argc < 2)
        return 2;
    job.server_addr = inet_addr("127.0.0.1");
    job.port = (uint16_t)atoi(argv[1]);

    char line[1024];
    while (fgets(line, sizeof(line), stdin) != NULL)
    {
        line[strcspn(line, "\r\n")] = '\0';
        char *rest = strchr(line, ' ');
        if (rest != NULL)
            *rest++ = '\0';
        else
            rest = line + strlen(line);
        char *f[4] = { 0 };
        int nf = split(rest, f, 4);
        char msg[160] = "";

        if (strcmp(line, "console") == 0 && nf == 3)
        {
            for (int i = 0; i < 6; i++)
            {
                unsigned b;
                sscanf(f[0] + i * 2, "%2x", &b);
                console.mac[i] = (uint8_t)b;
            }
            console.model = atoi(f[1]);
            console.backup_only = strcmp(f[2], "backup") == 0;
            printf("console ok\n");
        }
        else if (strcmp(line, "scan") == 0 && nf == 2)
        {
            saves_free(&list);
            printf("scan %d\n", saves_scan(&list, f[0], f[1], NULL));
            print_items();
        }
        else if (strcmp(line, "plan") == 0)
        {
            int r = saves_plan(&job, &console, &list, &server, msg, sizeof(msg));
            if (r > 0)
                saves_write_index(&list);
            printf("plan %d %s\n", r, msg);
            for (int i = 0; i < list.count; i++)
            {
                SaveItem *it = &list.items[i];
                if (it->action != SA_UNKNOWN)
                    printf("action %s|%d|%d|%08X|%d|%s\n", it->name, it->slot, it->action, it->pc_crc, it->versions,
                           it->pc_source);
            }
        }
        else if (strcmp(line, "sync") == 0 && nf >= 1)
        {
            if (strcmp(f[0], "*") == 0)
            {
                const char *how = nf >= 2 ? f[1] : NULL;
                for (int i = 0; i < list.count; i++)
                {
                    SaveAction a = list.items[i].action;
                    if (a != SA_IN_SYNC && a != SA_UNKNOWN && a != SA_EXCLUDED)
                        sync_one(&list.items[i], how);
                }
                printf("counts %d %d %d %d\n", counts.uploaded, counts.downloaded, counts.backed_up, counts.failed);
            }
            else
            {
                SaveItem *it = nf >= 2 ? find(f[0], atoi(f[1])) : NULL;
                if (it == NULL)
                    printf("sync missing\n");
                else
                    sync_one(it, nf >= 3 ? f[2] : NULL);
            }
        }
        else if (strcmp(line, "exclude") == 0 && nf == 2)
        {
            SaveItem *it = find(f[0], atoi(f[1]));
            if (it != NULL)
            {
                it->excluded = !it->excluded;
                printf("exclude %d %d\n", it->excluded, saves_write_index(&list));
            }
            else
            {
                printf("exclude missing\n");
            }
        }
        else if (strcmp(line, "versions") == 0 && nf == 2)
        {
            SaveItem *it = find(f[0], atoi(f[1]));
            SaveVersion v[SAVE_MAX_VERSIONS];
            int n = it ? saves_versions(&job, &console, &server, it, v, SAVE_MAX_VERSIONS, msg, sizeof(msg)) : -1;
            printf("versions %d %s\n", n, msg);
            for (int i = 0; i < n; i++)
                printf("version %d|%u|%08X|%s\n", v[i].version, v[i].size, v[i].crc, v[i].source);
        }
        else if (strcmp(line, "restore") == 0 && nf == 3)
        {
            SaveItem *it = find(f[0], atoi(f[1]));
            int r = it ? saves_restore(&job, &console, &server, &list, it, (uint8_t)atoi(f[2]), NULL, &counts, NULL,
                                       msg, sizeof(msg))
                       : -2;
            printf("restore %d %s\n", r, msg);
        }
        else if (strcmp(line, "quick") == 0 && nf == 2)
        {
            printf("quick %d\n", saves_quick_check(f[0], f[1]));
        }
        else if (strcmp(line, "done") == 0)
        {
            saves_done(&job, &console, &server, &counts);
            printf("done\n");
        }
        else if (strcmp(line, "settings") == 0 && nf >= 3)
        {
            LauncherSettings s;
            memset(&s, 0, sizeof(s));
            if (strcmp(f[1], "-") != 0)
                snprintf(s.dsirpc_ip, sizeof(s.dsirpc_ip), "%s", f[1]);
            s.backup_only = strcmp(f[2], "backup") == 0;
            if (nf == 4)
                snprintf(s.last_game, sizeof(s.last_game), "%s", f[3]);
            int saved = settings_save(f[0], &s);
            LauncherSettings back;
            settings_load(f[0], &back);
            printf("settings %d %s %d %08X %s\n", saved, back.dsirpc_ip[0] ? back.dsirpc_ip : "-", back.backup_only,
                   ntohl(settings_server_addr(&back)), back.last_game[0] ? back.last_game : "-");
        }
        else
        {
            printf("? %s\n", line);
        }
        fflush(stdout);
    }
    saves_free(&list);
    return 0;
}
