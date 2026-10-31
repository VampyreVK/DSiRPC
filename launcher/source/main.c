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
//   3. Write the connection info to RPCHAND.TXT (in its folder), which the in-game side
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
//      game's set), puts the game's set in RPCSET.BIN beside it and starts our
//      nds-bootstrap build, found next to the launcher (or picked in the
//      browser), still connected (source/chainload.c).
//      SELECT: disconnect cleanly, then exit.
//      X: exit without disconnecting (the old way: back to the menu, then
//      start our nds-bootstrap build from there). Not B, which the file
//      browser uses to go up a folder.
//      Y: the save sync (source/saveui.c, source/savesync.c): back the
//      games' saves up to DSiRPC, download newer ones from it.
//      L+R: the launcher's settings (source/settings.c): DSiRPC's address,
//      the save sync's mode.
//
// The top screen shows DSiRPC's pixel DSi, its Wi-Fi sign lighting up while
// it connects (source/topscreen.c). While the launcher waits for a key, it
// tells DSiRPC every few seconds that it's still there, and that it's
// leaving on SELECT or X (sync_frame() and sync_bye() in source/sync.c), so
// DSiRPC doesn't show it as connected after it's gone.
//
// Two looks (Look in the settings). The classic one is the text console, as
// it always was. The modern one (source/ui.c) draws the bottom screen: a
// checklist while it connects (a spinner on the step it's on, then the
// update's card), tiles for the main screen (Play, Saves, Settings, Exit:
// the D-pad and A, or a tap), the game picker with the games' icons
// (source/picker.c), and the same keys; START on its main screen starts the
// game last started straight away. After the first sync, the launcher also
// asks DSiRPC for its playtimes (source/stats.c), for the modern picker.
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
#include "music.h"
#include "picker.h"
#include "saveui.h"
#include "savesync.h"
#include "settings.h"
#include "stats.h"
#include "sync.h"
#include "topscreen.h"
#include "ui.h"
#include "update.h"
#include "watchdog.h"

#define CONNECT_TRIES     3
#define CONNECT_TIMEOUT_S 30   // per try, until associated
#define DHCP_TIMEOUT_S    10   // per try, then for an IPv4 address

// Our nds-bootstrap build, looked for next to the launcher (both go in
// sd:/roms/nds/DSiRPC/)
#define BOOTSTRAP_NAME    "nds-bootstrap-dsirpc.nds"
#define BOOTSTRAP_PREFIX  "nds-bootstrap"
#define LAUNCHER_NAME     "dsirpc-launcher.nds"

#define PATH_LEN          512

#define HANDOFF_FILE      "RPCHAND.TXT"    // in the launcher's folder, for the in-game side
#define GAMES_DIR         "sd:/roms/nds"   // where the game picker opens, if it exists
#define UNIX_TIME_2000    946684800   // 2000-01-01 00:00 as a Unix time

static char ip_str[20], gw_str[20], mask_str[20], mac_str[20];
// RPCHAND.TXT, RPCUNLK.BIN and RPCSET.BIN in the launcher's folder: nds-bootstrap
// finds them beside itself and hands them to the in-game side
static char handoff_path[PATH_LEN], unlocks_path[PATH_LEN], staged_set_path[PATH_LEN];
static u8 mac_bytes[6];
static bool online;                   // false: offline play, no Wi-Fi
static char sets_dir[PATH_LEN];       // the achievement sets (sync.c)
static char settings_path[PATH_LEN];  // launcher.ini (settings.c)
static char launcher_path[PATH_LEN];  // this launcher's own file, or "" (update.c)
static LauncherSettings settings;
static int saves_changed = -2;        // saves changed since the last save sync (-1: never synced)
static bool have_fat;
static char last_title[64];           // the game last started, for the Play tile

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
        u32 down = (keysDown() | ui_footer_key()) & keys;
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
    return ((keysDown() | ui_footer_key()) & KEY_B) != 0;
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

// The modern look's checklist: the connecting screen's steps, and the
// starting screen's (the classic look prints as it goes instead)

enum { STEP_WIFI, STEP_IP, STEP_DSIRPC, STEP_SETS, STEP_SAVES, STEPS };
static const char *step_label[STEPS] = { "Wi-Fi", "IP address", "DSiRPC", "Achievements", "Saves" };
static StepState step_state[STEPS];
static char step_value[STEPS][48];
static int row_dsirpc = STEP_DSIRPC, row_sets = STEP_SETS;   // where the syncs' steps are

static void show_step(int row, StepState state, const char *value)
{
    step_state[row] = state;
    snprintf(step_value[row], sizeof(step_value[row]), "%s", value != NULL ? value : "");
    if (!ui_on())
        return;
    ui_step(row, state, step_label[row], step_value[row]);
    ui_present();
}

static void draw_steps(const char *title, int rows, const UiKey *keys, int n)
{
    ui_clear();
    ui_header(title);
    for (int i = 0; i < rows; i++)
        ui_step(i, step_state[i], step_label[i], step_value[i]);
    if (keys != NULL)
        ui_footer(keys, n);
    ui_present();
}

static const UiKey KEYS_OFFLINE[] = { { "B", "Play offline", KEY_B } };

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
            show_step(STEP_WIFI, STEP_ACTIVE, status_text(status));
            old_status = status;
        }

        if ((status == ASSOCSTATUS_ASSOCIATED) ||
            (status == ASSOCSTATUS_CANNOTCONNECT))
            break;

        frames++;
        if (frames > CONNECT_TIMEOUT_S * 60)
        {
            say_status("Timed out");
            show_step(STEP_WIFI, STEP_ACTIVE, "Timed out");
            break;
        }
    }

    if (status != ASSOCSTATUS_ASSOCIATED)
        return NOT_CONNECTED;
    show_step(STEP_WIFI, STEP_DONE, "Connected");
    if (have_ipv4())
        return CONNECTED;

    say_status("Waiting for an IP address");
    show_step(STEP_IP, STEP_ACTIVE, "Asking the router");
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
    show_step(STEP_IP, STEP_ACTIVE, "None from DHCP");
    return NOT_CONNECTED;
}

static ConnectResult connect_with_retries(void)
{
    for (int attempt = 1; attempt <= CONNECT_TRIES; attempt++)
    {
        if (attempt > 1)
        {
            printf("Trying again (%d of %d)...\n", attempt, CONNECT_TRIES);
            char again[32];
            snprintf(again, sizeof(again), "Trying again (%d of %d)", attempt, CONNECT_TRIES);
            show_step(STEP_WIFI, STEP_ACTIVE, again);
            show_step(STEP_IP, STEP_WAITING, NULL);
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

// RPCHAND.TXT, for the in-game side (8.3 names for all three, as
// nds-bootstrap's older root lookup only matched short names). The "end" line tells its parser
// where the real content stops. Offline, there's no ip or mac, so the in-game
// side leaves the network alone. time= is the console's clock (seconds since
// 2000, local time), so the in-game side can date its unlocks.
static bool write_handoff(void)
{
    FILE *f = fopen(handoff_path, "w");
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
    // The modern look's steps, from sync.c's lines
    if (strncmp(text, "Looking for DSiRPC", 18) == 0)
        show_step(row_dsirpc, STEP_ACTIVE, "Looking");
    else if (strncmp(text, "Found DSiRPC at ", 16) == 0)
        show_step(row_dsirpc, STEP_ACTIVE, text + 16);
    else if (strncmp(text, "Saving the ", 11) == 0)
    {
        char code[5];
        snprintf(code, sizeof(code), "%s", text + 11);
        show_step(row_sets, STEP_ACTIVE, code);
    }
}

// Hands DSiRPC the unlocks waiting on the SD card and takes the achievement
// sets it has (game: the code of the game being started, or ""). B skips
// it. Returns true if there's something on the screen worth a moment to read.
static bool run_sync(const char *game)
{
    SyncJob job = {
        .sets_dir = sets_dir,
        .unlocks_path = unlocks_path,
        .console_model = console_model(),
        .server_addr = settings_server_addr(&settings),
        .say = say_line,
        .cancelled = b_pressed,
    };
    snprintf(job.game, sizeof(job.game), "%s", game);

    printf("\nSyncing with DSiRPC (B: skip)\n");
    if (ui_on())
    {
        static const UiKey keys[] = { { "B", "Skip", KEY_B } };
        ui_footer(keys, 1);
        ui_present();
    }
    SyncResult result;
    char msg[160];
    int r = sync_with_dsirpc(&job, &result, msg, sizeof(msg));
    if (r == 1)
        printf("Synced: %d unlock(s) sent,\n%d achievement set(s) received\n",
               result.unlocks_sent, result.sets_received);
    if (msg[0] != '\0')
        printf("%s\n", msg);

    // The modern look: how it went, on the steps, and a warning in the top
    // screen's note
    char text[48];
    if (r == 1)
    {
        show_step(row_dsirpc, STEP_DONE, result.server);
        // (short: the row has about 110 pixels after its label): sets
        // down from DSiRPC, unlocks sent to it
        if (result.sets_received && result.unlocks_sent)
            snprintf(text, sizeof(text), "%d down, %d sent", result.sets_received, result.unlocks_sent);
        else if (result.sets_received)
            snprintf(text, sizeof(text), "%d new set%s", result.sets_received, result.sets_received == 1 ? "" : "s");
        else if (result.unlocks_sent)
            snprintf(text, sizeof(text), "%d unlock%s sent", result.unlocks_sent, result.unlocks_sent == 1 ? "" : "s");
        else
            snprintf(text, sizeof(text), "Up to date");
        show_step(row_sets, msg[0] != '\0' ? STEP_FAILED : STEP_DONE, text);
    }
    else
    {
        bool skipped = strcmp(msg, "Sync skipped") == 0;
        show_step(row_dsirpc, skipped ? STEP_SKIPPED : STEP_FAILED, skipped ? "Skipped" : "Not found");
        show_step(row_sets, STEP_SKIPPED, "Not synced");
    }
    if (ui_on() && r != 0 && msg[0] != '\0')
    {
        char first[48];
        const char *nl = strchr(msg, '\n');
        snprintf(first, sizeof(first), "%.*s", nl != NULL ? (int)(nl - msg) : (int)strlen(msg), msg);
        top_note(first, nl != NULL ? nl + 1 : NULL);
    }
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
    top_note("Playing offline", "Unlocks wait on the SD card for DSiRPC");
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

static void show_message(const char *title, const char *text)
{
    if (ui_on())
    {
        static const UiKey keys[] = { { "A", "Back", KEY_A } };
        ui_sound(SND_ERROR);
        ui_card(title, text, UI_AMBER, keys, 1);
    }
    else
    {
        consoleClear();
        printf("%s\n\nPress A to go back\n", text);
    }
    wait_for_key_release();
    wait_for_keys(KEY_A | KEY_B | KEY_START);
}

// The modern look's starting screen: the game, then the sync's steps and
// what the in-game side gets
static void draw_starting(const char *game, const char *code)
{
    static UiBanner icon;
    char title[64] = "";
    if (!picker_banner(game, &icon, title, sizeof(title), NULL, 0) || title[0] == '\0')
    {
        const char *name = strrchr(game, '/');
        snprintf(title, sizeof(title), "%.63s", name != NULL ? name + 1 : game);
    }
    step_label[0] = "DSiRPC";
    step_label[1] = "Achievement set";
    step_label[2] = "Unlocks waiting";
    row_dsirpc = 0;
    row_sets = 1;
    step_state[0] = online ? STEP_WAITING : STEP_SKIPPED;
    snprintf(step_value[0], sizeof(step_value[0]), "%s", online ? "" : "Offline");
    step_state[1] = step_state[2] = STEP_WAITING;
    snprintf(step_value[1], sizeof(step_value[1]), "%s", code);
    step_value[2][0] = '\0';
    draw_steps("Starting", 3, NULL, 0);
    top_note("Starting", title);

    Canvas *c = ui_screen();
    ui_panel(8, 84, UI_W - 16, 52, UI_EDGE);
    if (icon.ok)
        ui_banner(c, 16, 94, &icon, 1, ui_banner_slot(0, &icon));
    int lines = ui_text_wrap(NULL, 0, 0, title, UI_W - 80, 2, UI_TEXT);
    ui_text_wrap(c, 58, lines > 1 ? 100 : 106, title, UI_W - 80, 2, UI_TEXT);
    ui_present();
}

static void restore_steps(void)
{
    step_label[0] = "Wi-Fi";
    step_label[1] = "IP address";
    step_label[2] = "DSiRPC";
    row_dsirpc = STEP_DSIRPC;
    row_sets = STEP_SETS;
}

// Picks a game and starts it (quick: the game last started, without the
// picker, in the modern look). Only returns if that didn't happen.
static void start_game(const char *dir, bool quick)
{
    char game[PATH_LEN], bootstrap[PATH_LEN], msg[256];

    // TWiLight's usual games folder, or the launcher's own; START there
    // picks the game last started from here, if it's still there
    const char *last = settings.last_game[0] != '\0' && file_exists(settings.last_game) ? settings.last_game : NULL;
    if (ui_on())
    {
        PickerUi ui = {
            .games_dir = dir_exists(GAMES_DIR) ? GAMES_DIR : dir,
            .index_dir = dir,
            .sets_dir = sets_dir,
            .unlocks_path = unlocks_path,
            .last = last,
            .settings = &settings,
            .settings_path = settings_path,
        };
        if (quick && last != NULL)
            snprintf(game, sizeof(game), "%s", last);
        else if (!pick_game(&ui, game, sizeof(game)))
            return;
    }
    else if (!browse_for_file("Pick a game", dir_exists(GAMES_DIR) ? GAMES_DIR : dir, ".nds", last, game, sizeof(game)))
    {
        return;
    }

    if (!find_bootstrap(dir, bootstrap, sizeof(bootstrap)))
    {
        // (the file browser is the classic look's)
        bool modern = ui_on();
        if (modern)
            ui_leave();
        bool picked = browse_for_file("Pick " BOOTSTRAP_NAME, dir, ".nds", NULL, bootstrap, sizeof(bootstrap));
        if (modern)
            ui_enter();
        if (!picked)
            return;
    }

    if (bootstrap_ini_prepare(game, msg, sizeof(msg)) != 0)
    {
        show_message("Can't start the game", msg);
        return;
    }
    if (strcmp(settings.last_game, game) != 0)
    {
        snprintf(settings.last_game, sizeof(settings.last_game), "%s", game);
        settings_save(settings_path, &settings);
    }
    picker_started(dir, game);

    consoleClear();
    char code[5];
    read_game_code(game, code);
    if (ui_on())
        draw_starting(game, code);
    bool pause = online && run_sync(code);

    // The files the in-game side uses for achievements in offline play
    int waiting = unlocks_prepare(unlocks_path);
    bool have_set = stage_set(sets_dir, code, staged_set_path);
    write_handoff();
    if (ui_on())
    {
        char text[48];
        if (code[0] == '\0')
            show_step(1, STEP_SKIPPED, "No game code");
        else if (have_set)
            show_step(1, STEP_DONE, code);
        else
        {
            snprintf(text, sizeof(text), "None for %s yet", code);
            show_step(1, STEP_SKIPPED, text);
        }
        if (waiting < 0)
            show_step(2, STEP_FAILED, "Can't write RPCUNLK.BIN");
        else if (waiting > 0)
        {
            snprintf(text, sizeof(text), "%d for DSiRPC", waiting);
            show_step(2, STEP_DONE, text);
        }
        else
            show_step(2, STEP_DONE, "None");
        ui_footer(NULL, 0);
        ui_present();
    }

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

    watchdog_pause(true);       // the ARM7 is handed over to nds-bootstrap
    music_stop();
    chainload(bootstrap, msg, sizeof(msg));
    music_play(settings.classic_look ? MUSIC_OFF : (MusicChoice)settings.music);
    watchdog_pause(false);
    top_note("The game didn't start", NULL);
    show_message("Can't start the game", msg);  // only if it didn't work
    restore_steps();
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

// ---------------------------------------------------------------------------
// The modern look's main screen: four tiles

enum { TILE_GAMES, TILE_SAVES, TILE_SETTINGS, TILE_EXIT, TILES };
#define TILE_W  117
#define TILE_H  66

static int home_tile;

// The tiles' icons, 8x8, drawn 2x: 1-3 their colors
// A game: its screen and its label
static const char *const ICON_GAMES[8] = {
    "11111111", "12222221", "12222221", "12222221", "12222221", "11111111", "13331111", "11111111",
};
static const char *const ICON_SAVES[8] = {
    "11222211", "11222211", "11222211", "11111111", "11111111", "13333331", "13333331", "13333331",
};
static const char *const ICON_SETTINGS[8] = {
    "...11...", ".111111.", ".111111.", "11122111", "11122111", ".111111.", ".111111.", "...11...",
};
static const char *const ICON_EXIT[8] = {
    ".111111.", ".122221.", ".122221.", ".122221.", ".122231.", ".122221.", ".122221.", ".122221.",
};

static bool saves_ready(void)
{
    return online && have_fat;
}

static void tile_rect(int i, int *x, int *y)
{
    *x = 8 + (i % 2) * (TILE_W + 6);
    *y = UI_TOP + 2 + (i / 2) * (TILE_H + 6);
}

static void draw_tile(int i)
{
    Canvas *c = ui_screen();
    int x, y;
    tile_rect(i, &x, &y);
    bool enabled = i != TILE_SAVES || saves_ready();
    ui_fill(c, x, y, TILE_W, TILE_H, i == home_tile ? UI_GREEN : UI_EDGE);
    ui_fill(c, x + 2, y + 2, TILE_W - 4, TILE_H - 4, UI_PANEL);
    ui_fill(c, x + 2, y + 2, TILE_W - 4, 2, UI_PANEL_HI);
    ui_fill(c, x + 2, y + TILE_H - 4, TILE_W - 4, 2, UI_PANEL_LO);

    static const char *const *const ICONS[TILES] = { ICON_GAMES, ICON_SAVES, ICON_SETTINGS, ICON_EXIT };
    static const uint8_t COLORS[TILES][3] = {
        { UI_SLATE, UI_SKY, UI_ICON }, { UI_CYAN, UI_TEXT, UI_BG }, { UI_ICON, UI_PANEL, 0 },
        { UI_DIM, UI_BAR, UI_AMBER },
    };
    static const uint8_t DIMMED[3] = { UI_SCROLL, UI_PANEL_HI, UI_PANEL_LO };
    for (int py = 0; py < 8; py++)
    {
        for (int px = 0; px < 8; px++)
        {
            char k = ICONS[i][py][px];
            if (k >= '1' && k <= '3')
                ui_fill(c, x + 8 + px * 2, y + 8 + py * 2, 2, 2, enabled ? COLORS[i][k - '1'] : DIMMED[k - '1']);
        }
    }

    static const char *const TITLES[TILES] = { "Games", "Saves", "Settings", "Exit" };
    char sub[48];
    switch (i)
    {
    case TILE_GAMES:
        if (last_title[0] != '\0')
            snprintf(sub, sizeof(sub), "Last: %.41s", last_title);
        else
            snprintf(sub, sizeof(sub), "Pick a game");
        break;
    case TILE_SAVES:
        if (!saves_ready())
            snprintf(sub, sizeof(sub), have_fat ? "Needs DSiRPC" : "No SD card");
        else if (saves_changed > 0)
            snprintf(sub, sizeof(sub), "%d changed", saves_changed);
        else if (saves_changed == -1)
            snprintf(sub, sizeof(sub), "Not synced yet");
        else
            snprintf(sub, sizeof(sub), "All backed up");
        break;
    case TILE_SETTINGS:
        snprintf(sub, sizeof(sub), "PC, saves, music");
        break;
    default:
        snprintf(sub, sizeof(sub), online ? "X: stay online" : "Back to the menu");
        break;
    }
    ui_text(c, x + 8, y + 28, TITLES[i], enabled ? UI_TEXT : UI_DIM);
    ui_text_wrap(c, x + 8, y + 40, sub, TILE_W - 16, 2, UI_DIM);
    if (i == TILE_SAVES && saves_ready() && saves_changed > 0)
    {
        char n[16];
        snprintf(n, sizeof(n), "%d", saves_changed > 99 ? 99 : saves_changed);
        ui_chip(c, x + TILE_W - 8 - ui_chip_width(n), y + 8, n, UI_AMBER, UI_AMBER_DARK);
    }
    ui_touch_add(x, y, TILE_W, TILE_H, i);
}

static void draw_home(void)
{
    Canvas *c = ui_screen();
    ui_clear();
    ui_header(NULL);
    char chip[16];
    const char *model = console_model() >= 2 ? "3DS" : "DSi";
    if (mac_bytes[4] || mac_bytes[5])
        snprintf(chip, sizeof(chip), "%s %02X%02X", model, mac_bytes[4], mac_bytes[5]);
    else
        snprintf(chip, sizeof(chip), "%s", model);
    // As ui_chip(), with the text a pixel lower: at the chip's top edge it
    // smudges when the 3DS scales the screen
    ui_fill(c, 6, 3, ui_chip_width(chip), 12, UI_CHIP);
    ui_text(c, 10, 6, chip, UI_TEXT);
    ui_header_right(online ? ip_str : "Offline", UI_DIM);
    for (int i = 0; i < TILES; i++)
        draw_tile(i);
    static const UiKey keys[] = { { "A", "Open", KEY_A }, { "START", "Last game", KEY_START }, { "Y", "Sync", KEY_Y } };
    ui_footer(keys, saves_ready() ? 3 : 2);
    ui_present();
}

// The main screen's keys in the modern look, as the classic look's: START
// (the picker; quick: the game last started), Y, L+R, SELECT or X
static u32 home_key(bool *quick)
{
    *quick = false;
    while (1)
    {
        sync_frame();
        scanKeys();
        u32 held = keysHeld(), down = keysDown(), rep = keysDownRepeat();
        if ((held & (KEY_L | KEY_R)) == (KEY_L | KEY_R) && (down & (KEY_L | KEY_R)))
        {
            ui_sound(SND_SELECT);
            return KEY_L | KEY_R;
        }
        down |= ui_footer_key();
        int tile = ui_tapped();
        int old = home_tile;
        if (rep & KEY_LEFT)
            home_tile &= ~1;
        if (rep & KEY_RIGHT)
            home_tile |= 1;
        if (rep & KEY_UP)
            home_tile &= ~2;
        if (rep & KEY_DOWN)
            home_tile |= 2;
        if (tile >= 0)
        {
            home_tile = tile;
            down |= KEY_A;
        }
        if (home_tile != old)
        {
            ui_sound(SND_MOVE);
            draw_tile(old);
            draw_tile(home_tile);
            ui_present();
        }

        if (down & KEY_START)
        {
            ui_sound(SND_SELECT);
            *quick = settings.last_game[0] != '\0' && file_exists(settings.last_game);
            return KEY_START;
        }
        if (down & KEY_A)
        {
            if (home_tile == TILE_SAVES && !saves_ready())
            {
                ui_sound(SND_ERROR);
                continue;
            }
            ui_sound(SND_SELECT);
            static const u32 OPENS[TILES] = { KEY_START, KEY_Y, KEY_L | KEY_R, KEY_SELECT };
            return OPENS[home_tile];
        }
        if ((down & KEY_Y) && saves_ready())
        {
            ui_sound(SND_SELECT);
            return KEY_Y;
        }
        if (down & (KEY_SELECT | KEY_X))
        {
            ui_sound(SND_BACK);
            return (down & KEY_SELECT) || !online ? KEY_SELECT : KEY_X;
        }
    }
}

// The main screen, after coming back from a game that didn't start, the save
// sync or the settings
static void draw_main(void)
{
    if (ui_on())
    {
        top_dsi();
        draw_home();
        return;
    }
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

// Asks DSiRPC for its playtimes (stats.c) and, in the modern look, says
// on the top screen which PC it is and how it's doing
static void fetch_stats(const char *dir, bool warned)
{
    SyncJob job = {
        .console_model = console_model(),
        .cancelled = b_pressed,
    };
    struct sockaddr_in server;
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_port = htons(sync_found_port);
    server.sin_addr.s_addr = sync_found_addr;
    char msg[96];
    int r = stats_fetch(&job, mac_bytes, console_model(), &server, dir, msg, sizeof(msg));
    if (warned)
        return;     // the sync's warning stays on the top screen

    char line1[48], line2[64];
    struct in_addr found = { .s_addr = sync_found_addr };
    StatsList st;
    if (r == 1 && stats_load(dir, &st) && st.pc[0] != '\0')
    {
        snprintf(line1, sizeof(line1), "DSiRPC on %.32s", st.pc);
        if (st.ra_user[0] != '\0')
            snprintf(line2, sizeof(line2), "Discord %s, RA: %.32s", st.discord ? "on" : "off", st.ra_user);
        else
            snprintf(line2, sizeof(line2), "Discord %s, RA signed out", st.discord ? "on" : "off");
        stats_free(&st);
    }
    else
    {
        snprintf(line1, sizeof(line1), "DSiRPC at %s", inet_ntoa(found));
        snprintf(line2, sizeof(line2), "Saves, sets and updates come from it");
    }
    top_note(line1, line2);
}

// The connecting screen's last step: what the saves need, asked of DSiRPC as
// the Saves screen does, so the Saves tile counts what changed on the PC
// (another console's newer save) too, not only what changed here. B skips
// it, and the count stays the one from the SD card.
static void check_saves(const char *dir)
{
    if (sync_found_addr == 0)
    {
        show_step(STEP_SAVES, STEP_SKIPPED, "Not synced");
        return;
    }
    printf("\nChecking the saves (B: skip)\n");
    if (ui_on())
    {
        static const UiKey keys[] = { { "B", "Skip", KEY_B } };
        ui_footer(keys, 1);
    }
    show_step(STEP_SAVES, STEP_ACTIVE, "Looking");
    SaveList list;
    int found = saves_scan(&list, games_dir(), dir, NULL);
    if (found < 0 || list.roms == 0)
    {
        show_step(STEP_SAVES, STEP_SKIPPED, found < 0 ? "Out of memory" : "No games");
        saves_free(&list);
        return;
    }

    show_step(STEP_SAVES, STEP_ACTIVE, "Asking DSiRPC");
    SyncJob job = {
        .console_model = console_model(),
        .server_addr = settings_server_addr(&settings),
        .cancelled = b_pressed,
    };
    SaveConsole console = { .model = console_model(), .backup_only = settings.backup_only };
    memcpy(console.mac, mac_bytes, sizeof(console.mac));
    struct sockaddr_in server;
    char msg[160];
    int r = saves_plan(&job, &console, &list, &server, msg, sizeof(msg));
    if (r > 0)
    {
        saves_write_index(&list);   // as the Saves screen does: what stage 2 found, and what's in sync
        int n = 0;
        for (int i = 0; i < list.count; i++)
            n += saves_needs_sync(&list.items[i], console.backup_only);
        saves_changed = n;
        char text[32];
        if (n == 0)
            snprintf(text, sizeof(text), "All backed up");
        else
            snprintf(text, sizeof(text), "%d to %s", n, console.backup_only ? "back up" : "sync");
        printf("Saves: %s\n", text);
        show_step(STEP_SAVES, STEP_DONE, text);
    }
    else
    {
        if (msg[0] != '\0')
            printf("%s\n", msg);
        show_step(STEP_SAVES, r == 0 && msg[0] == '\0' ? STEP_SKIPPED : STEP_FAILED,
                  r == 0 && msg[0] == '\0' ? "Skipped" : "Not checked");
    }
    saves_free(&list);
}

// The modern look's connecting screen, as it starts
static void draw_connecting(void)
{
    restore_steps();
    for (int i = 0; i < STEPS; i++)
    {
        step_state[i] = STEP_WAITING;
        step_value[i][0] = '\0';
    }
    step_state[STEP_WIFI] = STEP_ACTIVE;
    snprintf(step_value[STEP_WIFI], sizeof(step_value[STEP_WIFI]), "Starting");
    draw_steps("Getting ready", STEPS, KEYS_OFFLINE, 1);
    top_note("B: play offline", NULL);
}

// The game last started, for the Games tile: its banner's name, or its file's
static void find_last_title(void)
{
    last_title[0] = '\0';
    if (settings.last_game[0] == '\0' || !file_exists(settings.last_game))
        return;
    if (picker_banner(settings.last_game, NULL, last_title, sizeof(last_title), NULL, 0) && last_title[0] != '\0')
    {
        // The first line only ("Pokemon Platinum Version", not the publisher's)
        char *nl = strchr(last_title, '\n');
        if (nl != NULL)
            *nl = '\0';
        return;
    }
    const char *name = strrchr(settings.last_game, '/');
    snprintf(last_title, sizeof(last_title), "%.63s", name != NULL ? name + 1 : settings.last_game);
    size_t n = strlen(last_title);
    if (n > 4 && strcasecmp(last_title + n - 4, ".nds") == 0)
        last_title[n - 4] = '\0';
}

int main(int argc, char *argv[])
{
    defaultExceptionHandler();      // a crash shows its registers, not just its kind
    consoleDemoInit();
    top_init();
    ui_init();
    watchdog_start();

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

    have_fat = fatInitDefault();
    if (!have_fat)
        printf("Can't read the SD card\n");

    char dir[PATH_LEN];
    launcher_dir(argc, argv, dir, sizeof(dir));
    join_path(sets_dir, sizeof(sets_dir), dir, SETS_FOLDER);
    join_path(settings_path, sizeof(settings_path), dir, SETTINGS_FILE);
    settings_load(settings_path, &settings);
    settings_apply(&settings);
    find_self(argc, argv, dir, launcher_path, sizeof(launcher_path));
    join_path(handoff_path, sizeof(handoff_path), dir, HANDOFF_FILE);
    join_path(unlocks_path, sizeof(unlocks_path), dir, UNLOCKS_FILE);
    join_path(staged_set_path, sizeof(staged_set_path), dir, STAGED_SET_FILE);
    if (have_fat)
    {
        // From before they moved to the launcher's folder: the unlocks (and
        // playtime) waiting come along, the rest is written again anyway
        rename("sd:/" UNLOCKS_FILE, unlocks_path);
        remove("sd:/" HANDOFF_FILE);
        remove("sd:/" STAGED_SET_FILE);
        saves_changed = saves_quick_check(games_dir(), dir);
        stats_add_played(dir, unlocks_path);   // the last game's playtime, before any sync
    }
    find_last_title();

    printf("Connecting to Wi-Fi...\n");
    printf("B: skip, play offline\n");
    if (ui_on())
        draw_connecting();

    bool redraw = false;
    bool wifi_ready = Wifi_InitDefault(INIT_ONLY | WIFI_ATTEMPT_DSI_MODE);
    ConnectResult connected = NOT_CONNECTED;
    if (wifi_ready)
    {
        Wifi_GetData(WIFIGETDATA_MACADDRESS, sizeof(mac_bytes), mac_bytes);   // for the modern look's chip
        connected = connect_with_retries();
    }
    else
    {
        printf("The Wi-Fi didn't start\n");
    }

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
        if (ui_on())
        {
            static const UiKey keys[] = { { "START", "Play offline", KEY_START }, { "SELECT", "Exit", KEY_SELECT } };
            show_step(STEP_WIFI, STEP_FAILED, wifi_ready ? "Can't connect" : "Didn't start");
            ui_sound(SND_ERROR);
            top_note(NULL, NULL);
            ui_card_at(UI_TOP + STEPS * 18 + 4, "Couldn't connect",
                       wifi_ready ? "Check connection 4, 5 or 6 in System Settings > Internet."
                                  : "The Wi-Fi didn't start.", UI_RED, keys, 2);
        }
        if (wait_for_start_or_select() != KEY_START)
            return 0;
    }

    if (connected != CONNECTED)
    {
        if (connected == SKIPPED)
            show_step(STEP_WIFI, STEP_SKIPPED, "Skipped");
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
        show_step(STEP_WIFI, STEP_DONE, "Connected");
        show_step(STEP_IP, STEP_DONE, ip_str);

        u8 *mac = mac_bytes;
        Wifi_GetData(WIFIGETDATA_MACADDRESS, sizeof(mac_bytes), mac);
        snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

        print_connection();

        if (have_fat && !write_handoff())
            printf("Can't write RPCHAND.TXT\n");

        if (have_fat)
        {
            bool warned = run_sync("");
            if (sync_found_addr != 0)
                fetch_stats(dir, warned);
            else if (!warned)
                top_note("DSiRPC wasn't found", "Saves+achievements not synced");
            if (settings.auto_update && sync_found_addr != 0 && !offer_update(dir, &redraw))
                return 0;
            if (redraw && ui_on())
                draw_steps("Getting ready", STEPS, NULL, 0);   // back from the update's card, for the last step
            check_saves(dir);
        }
        else
        {
            show_step(STEP_DSIRPC, STEP_SKIPPED, "No SD card");
            show_step(STEP_SETS, STEP_SKIPPED, NULL);
            show_step(STEP_SAVES, STEP_SKIPPED, NULL);
        }
        if (ui_on())
            wait_frames(30);    // the checklist, done, for a moment
    }

    wait_for_key_release();
    if (redraw || ui_on())
        draw_main();    // the update's screens were up (or the modern look's main screen)
    else
        print_keys();
    watchdog_pause(false);      // connected (or not): the ARM7 should keep beating from here

    while (1)
    {
        u32 key;
        bool quick = false;
        if (ui_on())
        {
            key = home_key(&quick);
        }
        else
        {
            u32 keys = online ? (KEY_START | KEY_SELECT | KEY_X | KEY_Y) : (KEY_START | KEY_SELECT);
            key = wait_main_keys(keys);
        }

        if (key == KEY_START)
        {
            if (have_fat)
                start_game(dir, quick);
            else
                show_message("Can't start a game", "The SD card can't be read,\nso no game can be started.");
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
                show_message("No saves to sync", "The SD card can't be read,\nso there are no saves to sync.");
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
        watchdog_pause(true);
        sync_bye();
        music_stop();
        if (ui_on())
        {
            ui_card(key == KEY_SELECT && online ? "Turning the Wi-Fi off" : "See you soon!",
                    key == KEY_SELECT || !online ? "Back to your menu." : "Back to your menu, still connected.",
                    UI_CYAN, NULL, 0);
            top_note(NULL, NULL);
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

    // No Wifi_DisconnectAP()/Wifi_DisableWifi() on the X path, on purpose:
    // the chip is left associated when control returns to the loader.
    return 0;
}
