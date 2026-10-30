// The launcher's modern look on a PC (see ui_host.c)

#ifndef UI_HOST_H
#define UI_HOST_H

#include <stdbool.h>
#include <stdint.h>

extern uint32_t host_keys, host_battery;

// Both screens as a 256x384 PPM file (the top one above), the top screen's
// clear pixels in magenta (key) or with its diamonds under them
bool host_dump(const char *path, bool key);

// The screens as they're drawn: each goes to host_out/NAME.ppm (host_key as
// above), and host_shots counts them
extern const char *host_out;
extern bool host_key;
extern int host_shots;
void host_shot(const char *name);

// Each draws its screens (the picker's games from the SD card at sd, the
// starting screen's game rom)
void host_main_screens(const char *rom);
void host_connected(void);      // the connecting screen, done
void host_update_screens(void);
void host_settings_screens(void);
void host_picker_screens(const char *sd);
void host_save_screens(void);

// The demo's screens (ui_host.c's demo command): one state each, drawn
void host_demo_connecting(int done);
void host_demo_home(int tile, int changed);
void host_demo_games(const char *sd, const char *code, bool achievements);
void host_demo_saves(int row);
void host_demo_saves_progress(int pct);
void host_demo_saves_done(void);
void host_demo_settings(int row);

// maxmod's calls since it was last emptied (host_stubs.c)
extern char host_music_log[1024];

// The game list's findings, printed (picker)
void host_games(const char *sd, int sort);
void host_favorite(const char *sd, const char *path);
void host_started(const char *sd, const char *path);

#endif // UI_HOST_H
