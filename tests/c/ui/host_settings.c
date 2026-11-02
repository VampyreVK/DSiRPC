// settings.c's screen, in the modern look

#include "settings.c"

#include "ui_host.h"

void host_settings_screens(void)
{
    LauncherSettings s;
    memset(&s, 0, sizeof(s));
    s.auto_update = true;
    s.sounds = true;
    s.music = MUSIC_BRIGHT;
    int octet[4] = { 192, 168, 2, 10 };
    draw_modern(&s, ROW_LOOK, false, octet, -1);
    host_shot("settings");
    draw_modern(&s, ROW_ADDRESS, true, octet, 3);
    host_shot("settings_address");
    draw_modern(&s, ROW_MUSIC, false, octet, -1);
    host_shot("settings_music");
}

// The demo's (ui_host.c): the settings with a row picked
void host_demo_settings(int row)
{
    LauncherSettings s;
    memset(&s, 0, sizeof(s));
    s.auto_update = true;
    s.sounds = true;
    s.music = MUSIC_BRIGHT;
    int octet[4] = { 192, 168, 2, 10 };
    draw_modern(&s, row, false, octet, -1);
}
