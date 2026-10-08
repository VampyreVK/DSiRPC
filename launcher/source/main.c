// SPDX-License-Identifier: MIT
//
// DSiRPC launcher (grew out of stage 4, the handoff spike).
//
// Connects the DSi's wifi in DSi mode, then starts our nds-bootstrap build
// with the game you pick, WITHOUT disconnecting, so the game side keeps
// using the connection (the "handoff").
//
// Flow:
//   1. Connect with DSWiFi in DSi mode using the saved WFC settings (the same
//      slots the DSi menu uses - no passphrase in any file on the SD card).
//      Up to 3 tries: a try fails if it can't connect, or if no IPv4 address
//      comes from DHCP (DSWiFi also reports "Associated" once an IPv6
//      address is ready, which can be before DHCP has answered).
//   2. Show IP, gateway, mask and the DSi's MAC address.
//   3. Broadcast a few UDP test packets on port 4242
//      (spikes/stage1-listen/pc/listener.py shows them). Broadcast, so no
//      PC address has to be configured anywhere.
//   4. Write the connection info to sd:/RPCHAND.TXT, which the in-game side
//      of nds-bootstrap reads to address its packets.
//   5. Sync with DSiRPC if it's on the network (source/sync.c): hand over
//      the unlocks from offline play, take the achievement sets.
//   6. START: pick a game (.nds) in a file browser that opens in the
//      launcher's folder. The launcher points sd:/_nds/nds-bootstrap.ini at
//      it (source/bootstrap_ini.c), syncs again (so DSiRPC can send that
//      game's set), puts the game's set in sd:/RPCSET.BIN and starts our
//      nds-bootstrap build, found next to the launcher (or picked in the
//      browser), still connected (source/chainload.c).
//      SELECT: disconnect cleanly, then exit.
//      Y: exit without disconnecting (the old way: back to the menu, then
//      start our nds-bootstrap build from there). Not B, which the file
//      browser uses to go up a folder and back out.
//
// Offline play: B while connecting, or START when it can't connect, skips
// the Wi-Fi. Games start the same way, without the syncs, and RPCHAND.TXT
// says mode=offline, so the in-game side leaves the network alone.

#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>
#include <time.h>
#include <unistd.h>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/stat.h>

#include <fat.h>
#include <nds.h>
#include <dswifi9.h>

#include "bootstrap_ini.h"
#include "browser.h"
#include "chainload.h"
#include "sync.h"

#define LISTENER_PORT     4242
#define CONNECT_TRIES     3
#define CONNECT_TIMEOUT_S 30   // per try, until associated
#define DHCP_TIMEOUT_S    10   // per try, then for an IPv4 address
#define HELLO_PACKETS     3

// Our nds-bootstrap build, looked for next to the launcher (the README
// suggests sd:/_nds/dsirpc/ for both)
#define BOOTSTRAP_NAME    "nds-bootstrap-dsirpc.nds"
#define BOOTSTRAP_PREFIX  "nds-bootstrap"

#define PATH_LEN          512

#define HANDOFF_PATH      "sd:/RPCHAND.TXT"
#define UNIX_TIME_2000    946684800   // 2000-01-01 00:00 as a Unix time

static char ip_str[20], gw_str[20], mask_str[20], mac_str[20];
static bool online;                   // false: offline play, no Wi-Fi
static char sets_dir[PATH_LEN];       // the achievement sets (sync.c)

static void wait_frames(int frames)
{
    for (int f = 0; f < frames; f++)
        cothread_yield_irq(IRQ_VBLANK);
}

static void wait_for_key_release(void)
{
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);
        scanKeys();
        if ((keysHeld() & (KEY_START | KEY_SELECT | KEY_A | KEY_B | KEY_Y)) == 0)
            break;
    }
}

static u32 wait_for_keys(u32 keys)
{
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);
        scanKeys();
        u32 down = keysDown() & keys;
        if (down & KEY_START)
            return KEY_START;
        if (down)
            return down & -down;  // lowest one
    }
}

static int wait_for_start_or_select(void)
{
    return wait_for_keys(KEY_START | KEY_SELECT);
}

static void send_hello_packets(const char *dsi_ip)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        printf("socket() failed\n");
        return;
    }

    // lwIP refuses broadcast sends unless the socket allows them.
    int allow_broadcast = 1;
    setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &allow_broadcast, sizeof(allow_broadcast));

    struct sockaddr_in to;
    memset(&to, 0, sizeof(to));
    to.sin_family = AF_INET;
    to.sin_port = htons(LISTENER_PORT);
    to.sin_addr.s_addr = htonl(INADDR_BROADCAST);

    for (int i = 0; i < HELLO_PACKETS; i++)
    {
        char msg[96];
        int len = snprintf(msg, sizeof(msg),
                           "DSiRPC spike: hello %d/%d from %s (DSi-mode WPA2)",
                           i + 1, HELLO_PACKETS, dsi_ip);
        if (sendto(sock, msg, len, 0, (struct sockaddr *)&to, sizeof(to)) < 0)
            printf("sendto() failed (packet %d)\n", i + 1);

        // ~1 second between packets
        wait_frames(60);
    }

    closesocket(sock);
}

// ---------------------------------------------------------------------------
// Connecting

typedef enum
{
    CONNECTED,
    NOT_CONNECTED,
    SKIPPED,          // B: play offline
} ConnectResult;

static bool have_ipv4(void)
{
    u32 ip = Wifi_GetIP();
    return ip != 0 && ip != INADDR_NONE;
}

static bool b_pressed(void)
{
    scanKeys();
    return (keysDown() & KEY_B) != 0;
}

// One try: waits until associated (or not), then for an IPv4 address.
static ConnectResult connect_once(void)
{
    Wifi_AutoConnect();

    int status = -1;
    int old_status = -1;
    unsigned int frames = 0;
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);
        if (b_pressed())
            return SKIPPED;

        status = Wifi_AssocStatus();
        if (status != old_status)
        {
            printf("  %s\n", ASSOCSTATUS_STRINGS[status]);
            old_status = status;
        }

        if ((status == ASSOCSTATUS_ASSOCIATED) ||
            (status == ASSOCSTATUS_CANNOTCONNECT))
            break;

        frames++;
        if (frames > CONNECT_TIMEOUT_S * 60)
        {
            printf("  Timed out\n");
            break;
        }
    }

    if (status != ASSOCSTATUS_ASSOCIATED)
        return NOT_CONNECTED;
    if (have_ipv4())
        return CONNECTED;

    printf("  Waiting for an IPv4 address\n");
    for (frames = 0; frames < DHCP_TIMEOUT_S * 60; frames++)
    {
        cothread_yield_irq(IRQ_VBLANK);
        if (b_pressed())
            return SKIPPED;
        if (have_ipv4())
            return CONNECTED;
    }
    printf("  No IPv4 address (DHCP)\n");
    return NOT_CONNECTED;
}

static ConnectResult connect_with_retries(void)
{
    for (int attempt = 1; attempt <= CONNECT_TRIES; attempt++)
    {
        if (attempt > 1)
        {
            printf("Trying again (%d of %d)...\n", attempt, CONNECT_TRIES);
            Wifi_DisconnectAP();
            wait_frames(60);
        }
        ConnectResult result = connect_once();
        if (result != NOT_CONNECTED)
            return result;
    }
    return NOT_CONNECTED;
}

// ---------------------------------------------------------------------------
// Offline play and the sync with DSiRPC

// sd:/RPCHAND.TXT, for the in-game side. 8.3 name on purpose: nds-bootstrap's
// ARM7 file lookup only matches short names. The "end" line tells its parser
// where the real content stops. Offline, there's no ip or mac, so the in-game
// side leaves the network alone. time= is the console's clock (seconds since
// 2000, local time), so the in-game side can date its unlocks.
static bool write_handoff(void)
{
    FILE *f = fopen(HANDOFF_PATH, "w");
    if (f == NULL)
        return false;
    long now = (long)(time(NULL) - UNIX_TIME_2000);
    if (online)
        fprintf(f, "mode=dsi\nip=%s\ngateway=%s\nmask=%s\nmac=%s\ntime=%ld\nend\n",
                ip_str, gw_str, mask_str, mac_str, now);
    else
        fprintf(f, "mode=offline\ntime=%ld\nend\n", now);
    return fclose(f) == 0;
}

static void say_line(const char *text)
{
    printf("%s\n", text);
}

// Hands DSiRPC the unlocks waiting on the SD card and takes the achievement
// sets it has (game: the code of the game being started, or ""). B skips
// it. Returns true if there's something on the screen worth a moment to read.
static bool run_sync(const char *game)
{
    SyncJob job = {
        .sets_dir = sets_dir,
        .unlocks_path = UNLOCKS_PATH,
        .say = say_line,
        .cancelled = b_pressed,
    };
    snprintf(job.game, sizeof(job.game), "%s", game);

    printf("\nSyncing with DSiRPC (B: skip)\n");
    SyncResult result;
    char msg[160];
    int r = sync_with_dsirpc(&job, &result, msg, sizeof(msg));
    if (r == 1)
        printf("Synced: %d unlock(s) sent,\n%d achievement set(s) received\n",
               result.unlocks_sent, result.sets_received);
    if (msg[0] != '\0')
        printf("%s\n", msg);
    return r == -1 || (r == 1 && msg[0] != '\0');
}

// Turns the Wi-Fi off and says the launcher is in offline play.
static void go_offline(bool wifi_ready, bool have_fat)
{
    online = false;
    if (wifi_ready)
    {
        Wifi_DisconnectAP();
        Wifi_DisableWifi();
    }
    printf("\nPlaying offline (no Wi-Fi).\n");
    if (have_fat)
        write_handoff();
}

// ---------------------------------------------------------------------------
// Starting a game

static void launcher_dir(int argc, char *argv[], char *out, size_t outsz)
{
    if (argc > 0 && argv != NULL && argv[0] != NULL && strncasecmp(argv[0], "sd:/", 4) == 0)
    {
        snprintf(out, outsz, "%s", argv[0]);
        char *slash = strrchr(out, '/');
        if (slash != NULL)
        {
            if (slash > out && slash[-1] == ':')
                slash[1] = '\0';
            else
                *slash = '\0';
        }
        return;
    }
    if (getcwd(out, outsz) == NULL || strncasecmp(out, "sd:/", 4) != 0)
        snprintf(out, outsz, "sd:/");
}

static void join_path(char *out, size_t outsz, const char *dir, const char *name)
{
    size_t n = strlen(dir);
    snprintf(out, outsz, (n > 0 && dir[n - 1] == '/') ? "%s%s" : "%s/%s", dir, name);
}

static bool file_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISREG(st.st_mode);
}

// Our nds-bootstrap build in `dir`: nds-bootstrap-dsirpc.nds, or the only
// nds-bootstrap*.nds there.
static bool find_bootstrap(const char *dir, char *out, size_t outsz)
{
    join_path(out, outsz, dir, BOOTSTRAP_NAME);
    if (file_exists(out))
        return true;

    DIR *d = opendir(dir);
    if (d == NULL)
        return false;
    int found = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL)
    {
        size_t n = strlen(e->d_name);
        if (e->d_type != DT_DIR && n > 4 && strncasecmp(e->d_name, BOOTSTRAP_PREFIX, strlen(BOOTSTRAP_PREFIX)) == 0 &&
            strcasecmp(e->d_name + n - 4, ".nds") == 0)
        {
            if (found++ == 0)
                join_path(out, outsz, dir, e->d_name);
        }
    }
    closedir(d);
    return found == 1;
}

static void show_message(const char *text)
{
    consoleClear();
    printf("%s\n\nPress A to go back\n", text);
    wait_for_key_release();
    wait_for_keys(KEY_A | KEY_B | KEY_START);
}

// Picks a game and starts it. Only returns if that didn't happen.
static void start_game(const char *dir)
{
    char game[PATH_LEN], bootstrap[PATH_LEN], msg[256];

    if (!browse_for_file("Pick a game", dir, ".nds", game, sizeof(game)))
        return;

    if (!find_bootstrap(dir, bootstrap, sizeof(bootstrap)))
    {
        if (!browse_for_file("Where is our nds-bootstrap?", dir, ".nds", bootstrap, sizeof(bootstrap)))
            return;
    }

    if (bootstrap_ini_prepare(game, msg, sizeof(msg)) != 0)
    {
        show_message(msg);
        return;
    }

    consoleClear();
    char code[5];
    read_game_code(game, code);
    bool pause = online && run_sync(code);

    // The files the in-game side uses for achievements in offline play
    int waiting = unlocks_prepare(UNLOCKS_PATH);
    bool have_set = stage_set(sets_dir, code, STAGED_SET_PATH);
    write_handoff();

    const char *name = strrchr(game, '/');
    const char *loader = strrchr(bootstrap, '/');
    printf("%sStarting\n%s\nwith %s\n", online ? "\n" : "", name ? name + 1 : game,
           loader ? loader + 1 : bootstrap);
    if (code[0] != '\0')
    {
        if (have_set)
            printf("Achievement set: %s\n", code);
        else
            printf("No achievement set for %s\n", code);
    }
    if (waiting < 0)
        printf("Can't write RPCUNLK.BIN\n");
    else if (waiting > 0)
        printf("%d unlock(s) wait for DSiRPC\n", waiting);
    wait_frames(pause ? 150 : 30);

    chainload(bootstrap, msg, sizeof(msg));
    show_message(msg);  // only if it didn't work
}

static void print_connection(void)
{
    printf("\nIP:   %s\n", ip_str);
    printf("GW:   %s\n", gw_str);
    printf("Mask: %s\n", mask_str);
    printf("MAC:  %s\n", mac_str);
}

static void print_keys(void)
{
    printf("\nSTART:  pick a game, start it\n");
    printf("        with nds-bootstrap\n");
    if (online)
    {
        printf("SELECT: disconnect, then exit\n");
        printf("Y:      exit, stay connected\n");
    }
    else
    {
        printf("SELECT: exit\n");
    }
}

int main(int argc, char *argv[])
{
    consoleDemoInit();

    printf("DSiRPC launcher\n");
    printf("---------------\n");

    if (!isDSiMode())
    {
        printf("\nRunning in DS mode!\n");
        printf("Slots 4-6 and WPA2 need DSi\n");
        printf("mode. Relaunch this app in\n");
        printf("DSi mode.\n\n");
        printf("Press START to exit\n");
        while (wait_for_start_or_select() != KEY_START)
            ;
        return 0;
    }
    printf("Mode: DSi\n");

    bool have_fat = fatInitDefault();
    if (!have_fat)
        printf("SD init failed (can't write\nRPCHAND.TXT)\n");

    char dir[PATH_LEN];
    launcher_dir(argc, argv, dir, sizeof(dir));
    join_path(sets_dir, sizeof(sets_dir), dir, SETS_FOLDER);

    printf("\nConnecting with saved\nsettings (slots 1-6)...\n");
    printf("B: skip, play offline\n");

    bool wifi_ready = Wifi_InitDefault(INIT_ONLY | WIFI_ATTEMPT_DSI_MODE);
    ConnectResult connected = NOT_CONNECTED;
    if (wifi_ready)
        connected = connect_with_retries();
    else
        printf("Wifi_InitDefault() failed\n");

    if (connected == NOT_CONNECTED)
    {
        if (wifi_ready)
        {
            printf("\nCould not connect.\n");
            printf("Check slot 4-6 settings in\nSystem Settings > Internet.\n");
        }
        printf("\nSTART:  play offline\n");
        printf("SELECT: exit\n");
        if (wait_for_start_or_select() != KEY_START)
            return 0;
    }

    if (connected != CONNECTED)
    {
        go_offline(wifi_ready, have_fat);
    }
    else
    {
        online = true;

        struct in_addr gateway = { 0 }, mask = { 0 }, dns1 = { 0 }, dns2 = { 0 };
        struct in_addr ip = Wifi_GetIPInfo(&gateway, &mask, &dns1, &dns2);

        // inet_ntoa() returns a static buffer, so copy each result before the
        // next call.
        snprintf(ip_str, sizeof(ip_str), "%s", inet_ntoa(ip));
        snprintf(gw_str, sizeof(gw_str), "%s", inet_ntoa(gateway));
        snprintf(mask_str, sizeof(mask_str), "%s", inet_ntoa(mask));

        u8 mac[6] = { 0 };
        Wifi_GetData(WIFIGETDATA_MACADDRESS, sizeof(mac), mac);
        snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

        print_connection();

        if (have_fat && write_handoff())
            printf("Wrote sd:/RPCHAND.TXT\n");

        printf("\nBroadcasting %d UDP packets\n(port %d)...\n", HELLO_PACKETS, LISTENER_PORT);
        send_hello_packets(ip_str);
        printf("Done.\n");

        if (have_fat)
            run_sync("");
    }

    wait_for_key_release();
    print_keys();

    while (1)
    {
        u32 keys = online ? (KEY_START | KEY_SELECT | KEY_Y) : (KEY_START | KEY_SELECT);
        u32 key = wait_for_keys(keys);

        if (key == KEY_START)
        {
            if (have_fat)
                start_game(dir);
            else
                show_message("The SD card can't be read,\nso no game can be started.");
            // Back here: the game wasn't started
            consoleClear();
            printf("DSiRPC launcher\n");
            printf("---------------\n");
            if (online)
            {
                printf("Connected.\n");
                print_connection();
            }
            else
            {
                printf("Playing offline (no Wi-Fi).\n");
            }
            print_keys();
            wait_for_key_release();
            continue;
        }

        if (key == KEY_SELECT && online)
        {
            printf("Disconnecting...\n");
            Wifi_DisconnectAP();
            Wifi_DisableWifi();
            wait_frames(30);
        }
        break;
    }

    // No Wifi_DisconnectAP()/Wifi_DisableWifi() on the Y path, on purpose:
    // the chip is left associated when control returns to the loader.
    return 0;
}
