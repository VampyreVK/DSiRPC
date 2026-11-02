// main.c's screens: the connecting screen, the main screen, the starting
// screen (main.c is included whole: its screens are its own)

#include <stdlib.h>

#define main launcher_main
#include "main.c"
#undef main

#include "ui_host.h"

void host_connected(void)
{
    draw_connecting();
    top_set(TOP_CONNECTED);
    show_step(STEP_WIFI, STEP_DONE, "Connected");
    show_step(STEP_IP, STEP_DONE, "192.168.2.186");
    show_step(STEP_DSIRPC, STEP_DONE, "192.168.2.10");
    show_step(STEP_SETS, STEP_DONE, "2 down, 1 sent");
    top_note("DSiRPC on GAMING-PC", "Discord on, RA: VampyreVK");
}

void host_main_screens(const char *rom)
{
    settings_load("/nonexistent/launcher.ini", &settings);   // the defaults: the modern look
    settings_apply(&settings);
    snprintf(last_title, sizeof(last_title), "Pokemon Platinum Version");

    draw_connecting();
    show_step(STEP_WIFI, STEP_ACTIVE, "Signing in");
    host_shot("connecting");

    host_connected();
    show_step(STEP_SETS, STEP_ACTIVE, "CPUE");
    host_shot("syncing");

    host_connected();
    show_step(STEP_SAVES, STEP_DONE, "2 to sync");
    host_shot("ready");

    restore_steps();
    draw_connecting();
    top_set(TOP_FAILED);
    show_step(STEP_WIFI, STEP_FAILED, "Can't connect");
    top_note(NULL, NULL);
    static const UiKey keys[] = { { "START", "Play offline", KEY_START }, { "SELECT", "Exit", KEY_SELECT } };
    ui_card_at(UI_TOP + STEPS * 18 + 4, "Couldn't connect",
               "Check connection 4, 5 or 6 in System Settings > Internet.", UI_RED, keys, 2);
    host_shot("no_wifi");

    online = true;
    have_fat = true;
    snprintf(ip_str, sizeof(ip_str), "192.168.2.186");
    mac_bytes[4] = 0xCC;
    mac_bytes[5] = 0x5D;
    saves_changed = 3;
    top_set(TOP_CONNECTED);
    top_note("DSiRPC on GAMING-PC", "Discord on, RA: VampyreVK");
    draw_main();
    host_shot("home");
    home_tile = TILE_SETTINGS;
    draw_home();
    host_shot("home_settings");

    online = false;
    home_tile = TILE_GAMES;
    top_set(TOP_OFFLINE);
    top_note("Playing offline", "Unlocks wait on the SD card for DSiRPC");
    draw_main();
    host_shot("home_offline");

    online = true;
    top_set(TOP_CONNECTED);
    draw_starting(rom, "CPUE");
    show_step(0, STEP_DONE, "192.168.2.10");
    show_step(1, STEP_DONE, "CPUE");
    show_step(2, STEP_DONE, "2 for DSiRPC");
    host_shot("starting");
    restore_steps();
    top_note("DSiRPC on GAMING-PC", "Discord on, RA: VampyreVK");
}

// The demo's (ui_host.c): the connecting screen with done of its steps
// ticked off and the next one going, and the main screen with a tile picked
// (changed: the Saves tile's count)
void host_demo_connecting(int done)
{
    static const char *const doing[STEPS] = { "Signing in", "Asking the router", "Looking", "CPUE", "Asking DSiRPC" };
    static const char *const result[STEPS] = { "Connected", "192.168.2.186", "192.168.2.10",
                                               "2 down, 1 sent", "2 to sync" };
    settings_load("/nonexistent/launcher.ini", &settings);
    settings_apply(&settings);
    top_set(done >= 2 ? TOP_CONNECTED : TOP_CONNECTING);
    draw_connecting();
    if (done >= 3)
        top_note("DSiRPC on GAMING-PC", "Discord on, RA: VampyreVK");
    for (int i = 0; i < done && i < STEPS; i++)
        show_step(i, STEP_DONE, result[i]);
    if (done < STEPS)
        show_step(done, STEP_ACTIVE, doing[done]);
}

void host_demo_home(int tile, int changed)
{
    online = true;
    have_fat = true;
    snprintf(ip_str, sizeof(ip_str), "192.168.2.186");
    mac_bytes[4] = 0xCC;
    mac_bytes[5] = 0x5D;
    snprintf(last_title, sizeof(last_title), "Pokemon Platinum Version");
    saves_changed = changed;
    home_tile = tile;
    top_set(TOP_CONNECTED);
    top_note("DSiRPC on GAMING-PC", "Discord on, RA: VampyreVK");
    draw_main();
}
