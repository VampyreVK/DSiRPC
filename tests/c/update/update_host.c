// The launcher's updates (launcher/source/update.c, with sync.c and
// settings.c) on the PC, driven by tests/test_console_update.py against
// DSiRPC's ConsoleSync on loopback (or a stand-in). One command per line on
// stdin, fields after the command separated by '|':
//
//   check launcher|bootstrap|index_dir   check r|needed|total|label|msg, then
//                                        file lines: id|path|size|crc|needed
//   download                             download r|msg
//   unlink path                          (a file disappearing between steps)
//   install                              install r|msg
//   discard
//   find                                 find r|DSiRPC's address|its TCP port|msg
//   settings path|on, off or -           writes the settings (- leaves
//                                        AUTO_UPDATE out), reads them back:
//                                        settings saved|auto_update
//
// argv[1]: DSiRPC's port (the console looks for it at 127.0.0.1).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "settings.h"
#include "update.h"

static SyncJob job;
static struct sockaddr_in server;
static const uint8_t mac[6] = { 0x00, 0x09, 0xBF, 0x12, 0x3F, 0x21 };
static UpdatePlan plan;

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

// Messages on one line
static const char *flat(char *msg)
{
    for (char *p = msg; *p; p++)
    {
        if (*p == '\n')
            *p = ' ';
    }
    return msg;
}

int main(int argc, char *argv[])
{
    if (argc < 2)
        return 2;
    job.server_addr = inet_addr("127.0.0.1");
    job.port = (uint16_t)atoi(argv[1]);
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_port = htons(job.port);
    server.sin_addr.s_addr = job.server_addr;

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

        if (strcmp(line, "check") == 0 && nf == 3)
        {
            int r = update_check(&job, mac, 0, &server, f[0], f[1], f[2], &plan, msg, sizeof(msg));
            printf("check %d|%d|%u|%s|%s\n", r, plan.needed, (unsigned)plan.total, plan.label, flat(msg));
            for (int i = 0; i < plan.count; i++)
            {
                UpdateFile *u = &plan.files[i];
                printf("file %d|%s|%u|%08X|%d\n", u->id, u->path, (unsigned)u->size, (unsigned)u->crc, u->needed);
            }
        }
        else if (strcmp(line, "download") == 0)
        {
            int r = update_download(&job, mac, 0, &server, &plan, NULL, msg, sizeof(msg));
            printf("download %d|%s\n", r, flat(msg));
        }
        else if (strcmp(line, "unlink") == 0 && nf == 1)
        {
            printf("unlink %d\n", remove(f[0]));
        }
        else if (strcmp(line, "install") == 0)
        {
            bool ok = update_install(&plan, msg, sizeof(msg));
            printf("install %d|%s\n", ok, flat(msg));
        }
        else if (strcmp(line, "discard") == 0)
        {
            update_discard(&plan);
            printf("discard\n");
        }
        else if (strcmp(line, "find") == 0)
        {
            struct sockaddr_in found;
            int r = sync_find(&job, &found, msg, sizeof(msg));
            struct in_addr a = { .s_addr = sync_found_addr };
            printf("find %d|%s|%d|%s\n", r, sync_found_addr ? inet_ntoa(a) : "-", sync_found_port, flat(msg));
        }
        else if (strcmp(line, "settings") == 0 && nf == 2)
        {
            LauncherSettings s;
            memset(&s, 0, sizeof(s));
            s.auto_update = strcmp(f[1], "on") == 0;
            int saved = settings_save(f[0], &s);
            if (strcmp(f[1], "-") == 0)
            {
                FILE *ini = fopen(f[0], "w");   // a launcher.ini from before AUTO_UPDATE
                saved = ini != NULL && fputs("[LAUNCHER]\r\nSAVE_MODE = sync\r\n", ini) >= 0;
                if (ini != NULL)
                    fclose(ini);
            }
            LauncherSettings back;
            settings_load(f[0], &back);
            printf("settings %d|%d\n", saved, back.auto_update);
        }
        else
        {
            printf("? %s\n", line);
        }
        fflush(stdout);
    }
    return 0;
}
