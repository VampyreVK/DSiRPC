// The libnds stand-in's workings (stub/nds.h), and host_dump(): both screens
// as one PPM file.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <dswifi9.h>
#include <fat.h>
#include <nds.h>
#include <maxmod9.h>

#include "font.h"
#include "ui_host.h"

uint16_t BG_PALETTE[256], BG_PALETTE_SUB[256];
volatile u16 REG_BLDCNT, REG_BG0HOFS, REG_BG0VOFS;

// The screens' memory: the top screen's diamonds (BG0's tiles and map) and
// bitmap (BG3), and the bottom screen's bitmap
static uint8_t main_tiles[65536] __attribute__((aligned(4)));
static uint16_t main_map[1024];
static uint8_t main_bmp[65536] __attribute__((aligned(4)));
static uint8_t sub_bmp[65536] __attribute__((aligned(4)));
static PrintConsole console = { { default_font, NULL, 0, 1, 32, 96 } };

uint32_t host_keys = KEY_B;     // what every scan finds pressed
uint32_t host_battery = 11;

void scanKeys(void) {}
u32 keysDown(void) { return host_keys; }
u32 keysHeld(void) { return 0; }
u32 keysDownRepeat(void) { return host_keys; }
void keysSetRepeat(u8 delay, u8 repeat) { (void)delay; (void)repeat; }
void touchRead(touchPosition *t) { memset(t, 0, sizeof(*t)); }

void videoSetMode(u32 mode) { (void)mode; }
void videoSetModeSub(u32 mode) { (void)mode; }
void vramSetBankA(int bank) { (void)bank; }
void vramSetBankC(int bank) { (void)bank; }
int bgInit(int layer, BgType type, BgSize size, int map_base, int tile_base)
{
    (void)type; (void)size; (void)map_base; (void)tile_base;
    return layer;
}
int bgInitSub(int layer, BgType type, BgSize size, int map_base, int tile_base)
{
    (void)type; (void)size; (void)map_base; (void)tile_base;
    return 4 + layer;
}
void bgUpdate(void) {}
void bgSetPriority(int id, unsigned int priority) { (void)id; (void)priority; }
void *bgGetGfxPtr(int id) { return id == 0 ? (void *)main_tiles : id == 3 ? (void *)main_bmp : (void *)sub_bmp; }
void *bgGetMapPtr(int id) { (void)id; return main_map; }
void lcdMainOnTop(void) {}
void setBrightness(int screen, int level) { (void)screen; (void)level; }

PrintConsole *consoleDemoInit(void) { return &console; }
void consoleClear(void) {}
const PrintConsole *consoleGetDefault(void) { return &console; }

int cothread_create(cothread_entrypoint_t entry, void *arg, size_t stack, unsigned int flags)
{
    (void)entry; (void)arg; (void)stack; (void)flags;
    return 1;
}
void cothread_yield_irq(u32 flags) { (void)flags; }

void soundEnable(void) {}
int soundPlaySample(const void *data, SoundFormat format, u32 size, u16 freq, u8 volume, u8 pan, bool loop,
                    u16 loop_point)
{
    (void)data; (void)format; (void)size; (void)freq; (void)volume; (void)pan; (void)loop; (void)loop_point;
    return 0;
}

int soundPlaySampleChannel(int channel, const void *data, SoundFormat format, u32 size, u16 freq, u8 volume,
                           u8 pan, bool loop, u16 loop_point)
{
    (void)data; (void)format; (void)size; (void)freq; (void)volume; (void)pan; (void)loop; (void)loop_point;
    return channel;
}

// maxmod (music.c): each call noted, comma-separated
char host_music_log[1024];
const unsigned char soundbank_bin[4];

static void music_note(const char *what, int value)
{
    size_t n = strlen(host_music_log);
    snprintf(host_music_log + n, sizeof(host_music_log) - n, "%s%s%s", n ? "," : "", what, value >= 0 ? " " : "");
    if (value >= 0)
    {
        n = strlen(host_music_log);
        snprintf(host_music_log + n, sizeof(host_music_log) - n, "%d", value);
    }
}

bool mmInitDefaultMem(mm_addr soundbank)
{
    (void)soundbank;
    music_note("init", -1);
    return true;
}

void mmLockChannels(mm_word bitmask)
{
    music_note("lock", (int)bitmask);
}

mm_word mmLoad(mm_word module_ID)
{
    music_note("load", (int)module_ID);
    return 0;
}

mm_word mmUnload(mm_word module_ID)
{
    music_note("unload", (int)module_ID);
    return 0;
}

void mmStart(mm_word module_ID, mm_pmode mode)
{
    music_note(mode == MM_PLAY_LOOP ? "loop" : "once", (int)module_ID);
}

void mmStop(void)
{
    music_note("stop", -1);
}

void mmSetModuleVolume(mm_word volume)
{
    music_note("volume", (int)volume);
}

u32 getBatteryLevel(void) { return host_battery; }
void DC_FlushRange(const void *base, u32 size) { (void)base; (void)size; }
bool isDSiMode(void) { return true; }
bool fatInitDefault(void) { return true; }

bool Wifi_InitDefault(int flags) { (void)flags; return true; }
void Wifi_AutoConnect(void) {}
int Wifi_AssocStatus(void) { return ASSOCSTATUS_ASSOCIATED; }
unsigned Wifi_GetIP(void) { return 0; }
struct in_addr Wifi_GetIPInfo(struct in_addr *gateway, struct in_addr *mask, struct in_addr *dns1,
                              struct in_addr *dns2)
{
    (void)gateway; (void)mask; (void)dns1; (void)dns2;
    struct in_addr none = { 0 };
    return none;
}
int Wifi_GetData(int what, int size, unsigned char *out)
{
    (void)what;
    memset(out, 0, size);
    return 1;
}
void Wifi_DisconnectAP(void) {}
void Wifi_DisableWifi(void) {}

// chainload.c needs the DS
void chainload(const char *path, char *msg, unsigned int msgsz)
{
    (void)path;
    snprintf(msg, msgsz, "not on a PC");
}

static void rgb(uint16_t c, FILE *f)
{
    fputc((c & 31) << 3, f);
    fputc(((c >> 5) & 31) << 3, f);
    fputc(((c >> 10) & 31) << 3, f);
}

const char *host_out = ".";
bool host_key;
int host_shots;

void host_shot(const char *name)
{
    char path[600];
    snprintf(path, sizeof(path), "%s/%s.ppm", host_out, name);
    if (host_dump(path, host_key))
        host_shots++;
}

bool host_dump(const char *path, bool key)
{
    FILE *f = fopen(path, "wb");
    if (f == NULL)
        return false;
    fprintf(f, "P6\n256 384\n255\n");
    for (int y = 0; y < 192; y++)
    {
        for (int x = 0; x < 256; x++)
        {
            uint8_t b = main_bmp[y * 256 + x];
            if (b != 0)
            {
                rgb(BG_PALETTE[b], f);
            }
            else if (key)
            {
                // Clear: where the diamonds show (drawn by whoever reads it)
                fputc(255, f);
                fputc(0, f);
                fputc(255, f);
            }
            else
            {
                uint16_t t = main_map[(y / 8) * 32 + x / 8] & 0x3FF;
                rgb(BG_PALETTE[main_tiles[t * 64 + (y % 8) * 8 + x % 8]], f);
            }
        }
    }
    for (int i = 0; i < 256 * 192; i++)
        rgb(BG_PALETTE_SUB[sub_bmp[i]], f);
    return fclose(f) == 0;
}
