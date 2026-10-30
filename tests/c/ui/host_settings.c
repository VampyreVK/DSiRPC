// settings.c's screen, in the modern look

#include "settings.c"

#include "ui_host.h"

void host_settings_screens(void)
{
    LauncherSettings s;
    memset(&s, 0, sizeof(s));
    s.auto_update = true;
    s.sounds = true;
    int octet[4] = { 192, 168, 2, 10 };
    draw_modern(&s, ROW_LOOK, false, octet, -1);
    host_shot("settings");
    draw_modern(&s, ROW_ADDRESS, true, octet, 3);
    host_shot("settings_address");
}
