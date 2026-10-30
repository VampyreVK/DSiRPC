// A stand-in for libnds, so the launcher's screens draw on a PC (see
// ../ui_host.c): only what they use, the screens' memory as plain arrays.

#ifndef STUB_NDS_H
#define STUB_NDS_H

#include <poll.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;

#define BIT(n) (1u << (n))
#define RGB15(r, g, b) ((r) | ((g) << 5) | ((b) << 10))

extern uint16_t BG_PALETTE[256], BG_PALETTE_SUB[256];

enum
{
    KEY_A = BIT(0), KEY_B = BIT(1), KEY_SELECT = BIT(2), KEY_START = BIT(3), KEY_RIGHT = BIT(4),
    KEY_LEFT = BIT(5), KEY_UP = BIT(6), KEY_DOWN = BIT(7), KEY_R = BIT(8), KEY_L = BIT(9), KEY_X = BIT(10),
    KEY_Y = BIT(11), KEY_TOUCH = BIT(12), KEY_LID = BIT(13),
};
void scanKeys(void);
u32 keysDown(void);
u32 keysHeld(void);
u32 keysDownRepeat(void);
void keysSetRepeat(u8 delay, u8 repeat);

typedef struct
{
    u16 rawx, rawy, px, py, z1, z2;
} touchPosition;
void touchRead(touchPosition *t);

#define MODE_0_2D       0x10000
#define MODE_5_2D       0x10005
#define VRAM_A_MAIN_BG  1
#define VRAM_C_SUB_BG   4
typedef enum { BgType_Text8bpp, BgType_Text4bpp, BgType_Rotation, BgType_ExRotation, BgType_Bmp8, BgType_Bmp16 } BgType;
typedef enum { BgSize_T_256x256, BgSize_B8_256x256 } BgSize;
void videoSetMode(u32 mode);
void videoSetModeSub(u32 mode);
void vramSetBankA(int bank);
void vramSetBankC(int bank);
int bgInit(int layer, BgType type, BgSize size, int map_base, int tile_base);
int bgInitSub(int layer, BgType type, BgSize size, int map_base, int tile_base);
void bgUpdate(void);
void bgSetPriority(int id, unsigned int priority);
void *bgGetGfxPtr(int id);
void *bgGetMapPtr(int id);
void lcdMainOnTop(void);
void setBrightness(int screen, int level);
extern volatile u16 REG_BLDCNT, REG_BG0HOFS, REG_BG0VOFS;

typedef struct ConsoleFont
{
    const void *gfx;
    const void *pal;
    u16 numColors;
    u8 bpp;
    u16 asciiOffset;
    u16 numChars;
} ConsoleFont;
typedef struct PrintConsole
{
    ConsoleFont font;
} PrintConsole;
PrintConsole *consoleDemoInit(void);
void consoleClear(void);
const PrintConsole *consoleGetDefault(void);

#define IRQ_VBLANK         1
#define COTHREAD_DETACHED  1
typedef int (*cothread_entrypoint_t)(void *arg);
int cothread_create(cothread_entrypoint_t entry, void *arg, size_t stack, unsigned int flags);
void cothread_yield_irq(u32 flags);

typedef enum { SoundFormat_8Bit, SoundFormat_16Bit } SoundFormat;
void soundEnable(void);
int soundPlaySample(const void *data, SoundFormat format, u32 size, u16 freq, u8 volume, u8 pan, bool loop,
                    u16 loop_point);

u32 getBatteryLevel(void);
#define BATTERY_CHARGER_CONNECTED  BIT(7)
#define BATTERY_LEVEL_MASK         0xF
void DC_FlushRange(const void *base, u32 size);
bool isDSiMode(void);

#define closesocket close

#endif // STUB_NDS_H
