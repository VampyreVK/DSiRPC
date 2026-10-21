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
//   2. Show the console's IP and MAC addresses.
//   3. Write the connection info to sd:/RPCHAND.TXT, which the in-game side
//      of nds-bootstrap reads to address its packets.
//   4. Sync with DSiRPC if it's on the network (source/sync.c): hand over
//      the unlocks from offline play, take the achievement sets. Then, if
//      DSiRPC has other versions of the launcher or nds-bootstrap than the
//      SD card, offer them (source/update.c; Auto-update in the settings):
//      A downloads and checks them, turns the Wi-Fi off, swaps them in and
//      exits, to be started again.
//   5. START: pick a game (.nds) in a file browser that opens in
//      sd:/roms/nds (or the launcher's folder without one); START there
//      picks the game last started from here (launcher.ini's LAST_GAME).
//      The launcher points sd:/_nds/nds-bootstrap.ini at it
//      (source/bootstrap_ini.c), syncs again (so DSiRPC can send that
//      game's set), puts the game's set in sd:/RPCSET.BIN and starts our
//      nds-bootstrap build, found next to the launcher (or picked in the
//      browser), still connected (source/chainload.c).
//      SELECT: disconnect cleanly, then exit.
//      X: exit without disconnecting (the old way: back to the menu, then
//      start our nds-bootstrap build from there). Not B, which the file
//      browser uses to go up a folder.
//      Y: the save sync (source/saveui.c, source/savesync.c): back the
//      games' saves up to DSiRPC, take newer ones from it.
//      L+R: the launcher's settings (source/settings.c): DSiRPC's address,
//      the save sync's mode.
//
// The top screen shows DSiRPC's pixel DSi, its Wi-Fi sign lighting up while
// it connects (source/topscreen.c). While the launcher waits for a key, it
// tells DSiRPC every few seconds that it's still there, and that it's
// leaving on SELECT or X (sync_frame() and sync_bye() in source/sync.c), so
// DSiRPC doesn't show it as connected after it's gone.
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
#include <sys/stat.h>

#include <fat.h>
#include <nds.h>
#include <dswifi9.h>

#include "bootstrap_ini.h"
#include "browser.h"
#include "chainload.h"
#include "saveui.h"
#include "savesync.h"
#include "settings.h"
#include "sync.h"
#include "topscreen.h"
#include "update.h"

#define CONNECT_TRIES     3
#define CONNECT_TIMEOUT_S 30   // per try, until associated
#define DHCP_TIMEOUT_S    10   // per try, then for an IPv4 address

// Our nds-bootstrap build, looked for next to the launcher (both go in
// sd:/DSiRPC/)
#define BOOTSTRAP_NAME    "nds-bootstrap-dsirpc.nds"
#define BOOTSTRAP_PREFIX  "nds-bootstrap"
#define LAUNCHER_NAME     "dsirpc-launcher.nds"

#define PATH_LEN          512

#define HANDOFF_PATH      "sd:/RPCHAND.TXT"
#define GAMES_DIR         "sd:/roms/nds"   // where the game picker opens, if it exists
#define UNIX_TIME_2000    946684800   // 2000-01-01 00:00 as a Unix time

static char ip_str[20], gw_str[20], mask_str[20], mac_str[20];
static u8 mac_bytes[6];
static bool online;                   // false: offline play, no Wi-Fi
static char sets_dir[PATH_LEN];       // the achievement sets (sync.c)
static char settings_path[PATH_LEN];  // launcher.ini (settings.c)
static char launcher_path[PATH_LEN];  // this launcher's own file, or "" (update.c)
static LauncherSettings settings;
static int saves_changed = -2;        // saves changed since the last save sync (-1: never synced)

static void wait_frames(int frames)
{
    for (int f = 0; f < frames; f++)
        cothread_yield_irq(IRQ_VBLANK);
}

static void wait_for_key_release(void)
{
    while (1)
    {
        sync_frame();
        scanKeys();
        if ((keysHeld() & (KEY_START | KEY_SELECT | KEY_A | KEY_B | KEY_X | KEY_Y | KEY_L | KEY_R)) == 0)
            break;
    }
}

static u32 wait_for_keys(u32 keys)
{
    while (1)
    {
        sync_frame();
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

// Wifi_AssocStatus() in words (DSWiFi's ASSOCSTATUS_STRINGS are the enum's
// own names)
static const char *status_text(int status)
{
    switch (status)
    {
        case ASSOCSTATUS_SEARCHING:      return "Looking for the network";
        case ASSOCSTATUS_AUTHENTICATING: return "Signing in";
        case ASSOCSTATUS_ASSOCIATING:    return "Joining the network";
        case ASSOCSTATUS_ACQUIRINGDHCP:  return "Getting an IP address";
        case ASSOCSTATUS_ASSOCIATED:     return "Connected";
        case ASSOCSTATUS_CANNOTCONNECT:  return "Can't connect";
        default:                         return "Connecting";
    }
}

// A try's progress, on one line that's rewritten in place
static void say_status(const char *text)
{
    printf("\r\x1b[2K  %s", text);
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
            say_status(status_text(status));
            old_status = status;
        }

        if ((status == ASSOCSTATUS_ASSOCIATED) ||
            (status == ASSOCSTATUS_CANNOTCONNECT))
            break;

        frames++;
        if (frames > CONNECT_TIMEOUT_S * 60)
        {
            say_status("Timed out");
            break;
        }
    }

    if (status != ASSOCSTATUS_ASSOCIATED)
        return NOT_CONNECTED;
    if (have_ipv4())
        return CONNECTED;

    say_status("Waiting for an IP address");
    for (frames = 0; frames < DHCP_TIMEOUT_S * 60; frames++)
    {
        cothread_yield_irq(IRQ_VBLANK);
        if (b_pressed())
            return SKIPPED;
        if (have_ipv4())
        {
            say_status("Connected");
            return CONNECTED;
        }
    }
    say_status("No IP address (DHCP)");
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
        printf("\n");   // ends the try's status line
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
        .console_model = console_model(),
        .server_addr = settings_server_addr(&settings),
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
    top_set(TOP_OFFLINE);
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

static bool dir_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISDIR(st.st_mode);
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

// This launcher's own file: argv[0] (TWiLight Menu++ passes it), or
// dsirpc-launcher.nds in its folder; "" if neither is there.
static void find_self(int argc, char *argv[], const char *dir, char *out, size_t outsz)
{
    if (argc > 0 && argv != NULL && argv[0] != NULL && strncasecmp(argv[0], "sd:/", 4) == 0 && file_exists(argv[0]))
    {
        snprintf(out, outsz, "%s", argv[0]);
        return;
    }
    join_path(out, outsz, dir, LAUNCHER_NAME);
    if (!file_exists(out))
        out[0] = '\0';
}

// Offers the update if DSiRPC has other versions of the console's files
// (update.c). false if the launcher should exit now (the Wi-Fi went off).
static bool offer_update(const char *dir, bool *redraw)
{
    char bootstrap[PATH_LEN];
    if (!find_bootstrap(dir, bootstrap, sizeof(bootstrap)))
        join_path(bootstrap, sizeof(bootstrap), dir, BOOTSTRAP_NAME);
    UpdateUi ui = {
        .launcher_path = launcher_path,
        .bootstrap_path = bootstrap,
        .index_dir = dir,
        .mac = mac_bytes,
        .console_model = console_model(),
        .server_addr = sync_found_addr,
        .server_port = sync_found_port,
    };
    UpdateOutcome outcome = update_offer(&ui);
    *redraw = outcome == UPDATE_SHOWN;
    return outcome != UPDATE_EXIT;
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

    // TWiLight's usual games folder, or the launcher's own; START there
    // picks the game last started from here, if it's still there
    const char *last = settings.last_game[0] != '\0' && file_exists(settings.last_game) ? settings.last_game : NULL;
    if (!browse_for_file("Pick a game", dir_exists(GAMES_DIR) ? GAMES_DIR : dir, ".nds", last, game, sizeof(game)))
        return;

    if (!find_bootstrap(dir, bootstrap, sizeof(bootstrap)))
    {
        if (!browse_for_file("Pick " BOOTSTRAP_NAME, dir, ".nds", NULL, bootstrap, sizeof(bootstrap)))
            return;
    }

    if (bootstrap_ini_prepare(game, msg, sizeof(msg)) != 0)
    {
        show_message(msg);
        return;
    }
    if (strcmp(settings.last_game, game) != 0)
    {
        snprintf(settings.last_game, sizeof(settings.last_game), "%s", game);
        settings_save(settings_path, &settings);
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
    printf("%sStarting\n%s\n", online ? "\n" : "", name ? name + 1 : game);
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
    printf("\nIP:     %s\n", ip_str);
    printf("GW:     %s\n", gw_str);
    printf("MAC:    %s\n", mac_str);
    if (sync_found_addr != 0)
    {
        struct in_addr dsirpc = { .s_addr = sync_found_addr };
        printf("DSiRPC: %s\n", inet_ntoa(dsirpc));
    }
}

// Where the save sync looks for games: TWiLight's usual folder, or the whole
// SD card without one
static const char *games_dir(void)
{
    return dir_exists(GAMES_DIR) ? GAMES_DIR : "sd:/";
}

static void print_keys(void)
{
    printf("\nSTART:  pick a game\n");
    if (online)
    {
        printf("SELECT: disconnect, then exit\n");
        printf("X:      exit, stay connected\n");
        printf("Y:      sync saves");
        if (saves_changed > 0)
            printf(" \x1b[32;1m(%d changed)\x1b[39;0m", saves_changed);
        else if (saves_changed == -1)
            printf(" (not synced)");
        printf("\n");
    }
    else
    {
        printf("SELECT: exit\n");
    }
    printf("L+R:    settings\n");
}

// The main screen, after coming back from a game that didn't start, the save
// sync or the settings
static void draw_main(void)
{
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
}

// START, SELECT, X or Y (the lowest pressed of `keys`), or KEY_L | KEY_R
// when both shoulder buttons are held
static u32 wait_main_keys(u32 keys)
{
    while (1)
    {
        sync_frame();
        scanKeys();
        u32 held = keysHeld(), down = keysDown();
        if ((held & (KEY_L | KEY_R)) == (KEY_L | KEY_R) && (down & (KEY_L | KEY_R)))
            return KEY_L | KEY_R;
        down &= keys;
        if (down & KEY_START)
            return KEY_START;
        if (down)
            return down & -down;
    }
}

int main(int argc, char *argv[])
{
    consoleDemoInit();
    top_init();

    printf("DSiRPC launcher\n");
    printf("---------------\n");

    if (!isDSiMode())
    {
        top_set(TOP_FAILED);
        printf("\nThe launcher needs DSi mode\n");
        printf("(for WPA2). Set it in TWiLight\n");
        printf("Menu++'s per-game settings.\n\n");
        printf("START: exit\n");
        while (wait_for_start_or_select() != KEY_START)
            ;
        return 0;
    }

    bool have_fat = fatInitDefault();
    if (!have_fat)
        printf("Can't read the SD card\n");

    char dir[PATH_LEN];
    launcher_dir(argc, argv, dir, sizeof(dir));
    join_path(sets_dir, sizeof(sets_dir), dir, SETS_FOLDER);
    join_path(settings_path, sizeof(settings_path), dir, SETTINGS_FILE);
    settings_load(settings_path, &settings);
    find_self(argc, argv, dir, launcher_path, sizeof(launcher_path));
    if (have_fat)
        saves_changed = saves_quick_check(games_dir(), dir);

    printf("Connecting to Wi-Fi...\n");
    printf("B: skip, play offline\n");

    bool redraw = false;
    bool wifi_ready = Wifi_InitDefault(INIT_ONLY | WIFI_ATTEMPT_DSI_MODE);
    ConnectResult connected = NOT_CONNECTED;
    if (wifi_ready)
        connected = connect_with_retries();
    else
        printf("The Wi-Fi didn't start\n");

    if (connected == NOT_CONNECTED)
    {
        top_set(TOP_FAILED);
        if (wifi_ready)
        {
            printf("\nCouldn't connect. Check\n");
            printf("connection 4, 5 or 6 in\nSystem Settings > Internet.\n");
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
        top_set(TOP_CONNECTED);

        struct in_addr gateway = { 0 }, mask = { 0 }, dns1 = { 0 }, dns2 = { 0 };
        struct in_addr ip = Wifi_GetIPInfo(&gateway, &mask, &dns1, &dns2);

        // inet_ntoa() returns a static buffer, so copy each result before the
        // next call.
        snprintf(ip_str, sizeof(ip_str), "%s", inet_ntoa(ip));
        snprintf(gw_str, sizeof(gw_str), "%s", inet_ntoa(gateway));
        snprintf(mask_str, sizeof(mask_str), "%s", inet_ntoa(mask));

        u8 *mac = mac_bytes;
        Wifi_GetData(WIFIGETDATA_MACADDRESS, sizeof(mac_bytes), mac);
        snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

        print_connection();

        if (have_fat && !write_handoff())
            printf("Can't write sd:/RPCHAND.TXT\n");

        if (have_fat)
        {
            run_sync("");
            if (settings.auto_update && sync_found_addr != 0 && !offer_update(dir, &redraw))
                return 0;
        }
    }

    wait_for_key_release();
    if (redraw)
        draw_main();    // the update's screens were up
    else
        print_keys();

    while (1)
    {
        u32 keys = online ? (KEY_START | KEY_SELECT | KEY_X | KEY_Y) : (KEY_START | KEY_SELECT);
        u32 key = wait_main_keys(keys);

        if (key == KEY_START)
        {
            if (have_fat)
                start_game(dir);
            else
                show_message("The SD card can't be read,\nso no game can be started.");
            // Back here: the game wasn't started
            draw_main();
            wait_for_key_release();
            continue;
        }

        if (key == KEY_Y)
        {
            if (have_fat)
            {
                SaveUi ui = {
                    .games_dir = games_dir(),
                    .index_dir = dir,
                    .settings = &settings,
                    .mac = mac_bytes,
                    .console_model = console_model(),
                };
                save_sync_screen(&ui);
                saves_changed = saves_quick_check(games_dir(), dir);
            }
            else
            {
                show_message("The SD card can't be read,\nso there are no saves to sync.");
            }
            draw_main();
            wait_for_key_release();
            continue;
        }

        if (key == (KEY_L | KEY_R))
        {
            settings_screen(settings_path, &settings, online ? ip_str : "192.168.1.2");
            draw_main();
            wait_for_key_release();
            continue;
        }

        // SELECT or X: leaving
        sync_bye();
        if (key == KEY_SELECT && online)
        {
            printf("Disconnecting...\n");
            Wifi_DisconnectAP();
            Wifi_DisableWifi();
            wait_frames(30);
        }
        break;
    }

    // No Wifi_DisconnectAP()/Wifi_DisableWifi() on the X path, on purpose:
    // the chip is left associated when control returns to the loader.
    return 0;
}
