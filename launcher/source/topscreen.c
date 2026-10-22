// SPDX-License-Identifier: MIT
//
// The top screen (see topscreen.h), in the style of the desktop app's
// waiting screen (overlay/scenes.py's draw_waiting): its teal background of
// drifting diamonds, a header bar with "DSiRPC" and a signal meter, and the
// pixel DSi (overlay/ui.py's _DSI) drawn 4x.
//
// It's drawn once: the bar and the DSi into an 8-bit bitmap (BG3), the
// diamonds as a tiled layer under it (BG0). The animation only rewrites a
// few palette entries (the Wi-Fi sign's dot and arcs, the meter's bars) and
// BG0's scroll, from a cothread that runs whenever the launcher waits for a
// frame, so nothing else has to know about it.

#include <stdlib.h>
#include <string.h>

#include <nds.h>

#include "topscreen.h"

#define W          256
#define H          192
#define SCALE      4
#define BAR_H      20
#define DSI_W      35
#define DSI_H      40
#define DSI_X      ((W - DSI_W * SCALE) / 2)
#define DSI_Y      (BAR_H + (H - BAR_H - DSI_H * SCALE) / 2)

#define RGB(r, g, b)  RGB15((r) >> 3, (g) >> 3, (b) >> 3)
#define GREEN      RGB(88, 208, 128)
#define RED        RGB(232, 72, 56)
#define WIFI_ON    RGB(129, 148, 174)    // the overlay's arcs while it looks
#define WIFI_OFF   RGB(46, 56, 70)
#define METER_OFF  RGB(66, 90, 102)

// Palette entries (BG_PALETTE; 0 is the backdrop, and clear in the layers)
enum
{
    C_BACKDROP,
    C_TILE, C_DOT,              // the diamonds
    C_BAR, C_BAR_HI, C_BAR_LO,
    C_TEXT, C_TEXT_SHADOW,
    C_SHADOW,                   // under the DSi
    C_LINES,                    // the lines of text on its bottom screen
    C_METER,                    // 3: the meter's bars, shortest first
    C_WIFI = C_METER + 3,       // 4: the Wi-Fi sign's dot, then its arcs
    C_DSI = C_WIFI + 4,         // 8: the DSi, in DSI_KEYS' order
};

// overlay/ui.py's _DSI and _DSI_PALETTE: o outline, b lid, e speakers,
// H hinge, d base, k screen frames, s screens, p buttons
static const char *const DSI_ART[DSI_H] = {
    "..ooooooooooooooooooooooooooooooo..",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo",
    "obbbbbkkkkkkkkkkkkkkkkkkkkkkkbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obebebkssssssssssssssssssssskbebebo",
    "obbebbkssssssssssssssssssssskbbebbo",
    "obebebkssssssssssssssssssssskbebebo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbbo",
    "obbbbbkkkkkkkkkkkkkkkkkkkkkkkbbbbbo",
    "obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "..ooooooooooooooooooooooooooooooo..",
    "...oHHHHHHHHHHHHHHHHHHHHHHHHHHHo...",
    "..ooooooooooooooooooooooooooooooo..",
    ".odddddddddddddddddddddddddddddddo.",
    "odddddddddddddddddddddddddddddddddo",
    "oddddddkkkkkkkkkkkkkkkkkkkkkddddddo",
    "oddddddkssssssssssssssssssskddddddo",
    "odddpddkssssssssssssssssssskddpdddo",
    "oddpppdkssssssssssssssssssskdpdpddo",
    "odddpddkssssssssssssssssssskddpdddo",
    "oddddddkssssssssssssssssssskddddddo",
    "oddddddkssssssssssssssssssskddddddo",
    "oddddddkssssssssssssssssssskddddddo",
    "oddddddkssssssssssssssssssskddddddo",
    "oddddddkssssssssssssssssssskdpddddo",
    "oddddddkssssssssssssssssssskddddddo",
    "oddddpdkssssssssssssssssssskdpddddo",
    "oddddddkkkkkkkkkkkkkkkkkkkkkddddddo",
    "odddddddddddddddddddddddddddddddddo",
    ".odddddddddddddddddddddddddddddddo.",
    "..ooooooooooooooooooooooooooooooo..",
};
static const char DSI_KEYS[] = "obeHdksp";
static const uint8_t DSI_RGB[8][3] = {
    { 22, 27, 33 }, { 61, 75, 95 }, { 48, 62, 79 }, { 37, 45, 57 },
    { 51, 63, 80 }, { 17, 21, 27 }, { 28, 34, 43 }, { 154, 160, 173 },
};

// The Wi-Fi sign on its top screen (overlay/ui.py's DSI_WIFI): x, y, and
// which part (0 the dot, 1-3 the arcs from the smallest out)
static const uint8_t WIFI[][3] = {
    { 17, 13, 0 },
    { 16, 10, 1 }, { 17, 10, 1 }, { 18, 10, 1 }, { 15, 11, 1 }, { 19, 11, 1 },
    { 15, 8, 2 }, { 16, 8, 2 }, { 17, 8, 2 }, { 18, 8, 2 }, { 19, 8, 2 }, { 14, 9, 2 }, { 20, 9, 2 },
    { 14, 6, 3 }, { 15, 6, 3 }, { 16, 6, 3 }, { 17, 6, 3 }, { 18, 6, 3 }, { 19, 6, 3 }, { 20, 6, 3 },
    { 13, 7, 3 }, { 21, 7, 3 }, { 12, 8, 3 }, { 22, 8, 3 },
};

// The bottom screen's lines of text (overlay/ui.py's DSI_LINES), 4x: rows
// from the DSi's top, from LINES_X0 to LINES_X1
static const uint8_t LINES[][2] = {
    { 104, 105 }, { 109, 111 }, { 115, 118 }, { 122, 125 }, { 129, 132 }, { 136, 140 },
};
#define LINES_X0   39
#define LINES_X1   101

// "DSiRPC" in a 5x7 pixel font, drawn 2x in the header
static const char *const TITLE[6][7] = {
    { "####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####." },
    { ".###.", "#...#", "#....", ".###.", "....#", "#...#", ".###." },
    { "..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###." },
    { "####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#" },
    { "####.", "#...#", "#...#", "####.", "#....", "#....", "#...." },
    { ".###.", "#...#", "#....", "#....", "#....", "#...#", ".###." },
};

static uint8_t *canvas;     // W x H palette entries, while it's drawn
static volatile TopState state = TOP_CONNECTING;

static void fill(int x, int y, int w, int h, uint8_t c)
{
    for (int yy = y; yy < y + h; yy++)
    {
        for (int xx = x; xx < x + w; xx++)
        {
            if (xx >= 0 && xx < W && yy >= 0 && yy < H)
                canvas[yy * W + xx] = c;
        }
    }
}

// One of the DSi's pixels, SCALE x SCALE (off: where its shadow falls)
static void dsi_pixel(int x, int y, int off, uint8_t c)
{
    fill(DSI_X + x * SCALE + off, DSI_Y + y * SCALE + off, SCALE, SCALE, c);
}

static void title(int x, int y, uint8_t c)
{
    for (int g = 0; g < 6; g++)
    {
        // Each letter as wide as it is, a pixel apart
        int first = 5, last = -1;
        for (int row = 0; row < 7; row++)
        {
            for (int col = 0; col < 5; col++)
            {
                if (TITLE[g][row][col] == '#')
                {
                    first = col < first ? col : first;
                    last = col > last ? col : last;
                }
            }
        }
        for (int row = 0; row < 7; row++)
        {
            for (int col = first; col <= last; col++)
            {
                if (TITLE[g][row][col] == '#')
                    fill(x + (col - first) * 2, y + row * 2, 2, 2, c);
            }
        }
        x += (last - first + 2) * 2;
    }
}

static void draw(void)
{
    // The header bar, its name and the meter
    fill(0, 0, W, BAR_H, C_BAR);
    fill(0, 0, W, 1, C_BAR_HI);
    fill(0, BAR_H - 1, W, 1, C_BAR_LO);
    title(10, 5, C_TEXT_SHADOW);
    title(8, 3, C_TEXT);
    for (int i = 0; i < 3; i++)
        fill(W - 30 + i * 8, 16 - 4 * (i + 1), 5, 4 * (i + 1), C_METER + i);

    // The DSi's shadow, the DSi, its Wi-Fi sign and the lines on its bottom
    // screen
    for (int y = 0; y < DSI_H; y++)
    {
        for (int x = 0; x < DSI_W; x++)
        {
            if (DSI_ART[y][x] != '.')
                dsi_pixel(x, y, SCALE, C_SHADOW);
        }
    }
    for (int y = 0; y < DSI_H; y++)
    {
        for (int x = 0; x < DSI_W; x++)
        {
            const char *k = strchr(DSI_KEYS, DSI_ART[y][x]);
            if (DSI_ART[y][x] != '.' && k != NULL)
                dsi_pixel(x, y, 0, C_DSI + (k - DSI_KEYS));
        }
    }
    for (size_t i = 0; i < sizeof(WIFI) / sizeof(WIFI[0]); i++)
        dsi_pixel(WIFI[i][0], WIFI[i][1], 0, C_WIFI + WIFI[i][2]);
    for (size_t i = 0; i < sizeof(LINES) / sizeof(LINES[0]); i++)
        fill(DSI_X + LINES_X0, DSI_Y + LINES[i][0], LINES_X1 - LINES_X0, LINES[i][1] - LINES[i][0], C_LINES);
}

// The diamonds: one 16x16 cell (overlay/ui.py's tiled_background) as four
// 8x8 tiles, 8 bits a pixel, repeated across the map
static void make_pattern(uint16_t *tiles, uint16_t *map)
{
    uint8_t cell[16][16];
    memset(cell, 0, sizeof(cell));
    for (int i = 0; i < 4; i++)
    {
        for (int x = 8 - i; x <= 8 + i; x++)
            cell[4 + i][x] = cell[11 - i][x] = C_TILE;
    }
    cell[7][8] = C_DOT;
    for (int t = 0; t < 4; t++)
    {
        for (int y = 0; y < 8; y++)
        {
            for (int x = 0; x < 8; x += 2)
            {
                int cy = (t / 2) * 8 + y, cx = (t % 2) * 8 + x;
                tiles[(t * 64 + y * 8 + x) / 2] = cell[cy][cx] | (cell[cy][cx + 1] << 8);
            }
        }
    }
    for (int y = 0; y < 32; y++)
    {
        for (int x = 0; x < 32; x++)
            map[y * 32 + x] = (y & 1) * 2 + (x & 1);
    }
}

static void set_parts(int first, int n, int lit, uint16_t on, uint16_t off)
{
    for (int i = 0; i < n; i++)
        BG_PALETTE[first + i] = i < lit ? on : off;
}

static void animate(unsigned frame)
{
    // The diamonds drift down and right, a pixel every 7 frames (the
    // overlay's 120 ms)
    uint16_t shift = (frame / 7) % 16;
    REG_BG0HOFS = (uint16_t)-shift;
    REG_BG0VOFS = (uint16_t)-shift;

    switch (state)
    {
    case TOP_CONNECTING:
        // The overlay's pace: an arc every 400 ms, a bar every 350 ms
        set_parts(C_WIFI, 4, 1 + (frame / 24) % 4, WIFI_ON, WIFI_OFF);
        set_parts(C_METER, 3, (frame / 21) % 4, GREEN, METER_OFF);
        break;
    case TOP_CONNECTED:
        set_parts(C_WIFI, 4, 4, GREEN, GREEN);
        set_parts(C_METER, 3, 3, GREEN, GREEN);
        break;
    case TOP_FAILED:
        set_parts(C_WIFI, 4, 4, RED, RED);
        set_parts(C_METER, 3, 0, GREEN, METER_OFF);
        break;
    default:
        set_parts(C_WIFI, 4, 0, WIFI_ON, WIFI_OFF);
        set_parts(C_METER, 3, 0, GREEN, METER_OFF);
        break;
    }
}

static int top_thread(void *arg)
{
    (void)arg;
    for (unsigned frame = 1;; frame++)
    {
        cothread_yield_irq(IRQ_VBLANK);
        animate(frame);
    }
    return 0;
}

void top_init(void)
{
    canvas = calloc(W * H, 1);
    if (canvas == NULL)
        return;

    lcdMainOnTop();
    videoSetMode(MODE_5_2D);
    vramSetBankA(VRAM_A_MAIN_BG);
    setBrightness(1, 0);
    REG_BLDCNT = 0;
    int pattern = bgInit(0, BgType_Text8bpp, BgSize_T_256x256, 0, 1);
    int art = bgInit(3, BgType_Bmp8, BgSize_B8_256x256, 4, 0);
    bgSetPriority(art, 0);
    bgSetPriority(pattern, 1);

    static const uint8_t rgb[][3] = {
        [C_BACKDROP] = { 40, 104, 112 }, [C_TILE] = { 52, 122, 130 }, [C_DOT] = { 70, 142, 148 },
        [C_BAR] = { 32, 48, 58 }, [C_BAR_HI] = { 66, 90, 102 }, [C_BAR_LO] = { 16, 24, 32 },
        [C_TEXT] = { 248, 248, 248 }, [C_TEXT_SHADOW] = { 24, 32, 40 },
        [C_SHADOW] = { 30, 84, 92 }, [C_LINES] = { 201, 208, 220 },
    };
    for (int i = 0; i <= C_LINES; i++)
        BG_PALETTE[i] = RGB(rgb[i][0], rgb[i][1], rgb[i][2]);
    for (int i = 0; i < 8; i++)
        BG_PALETTE[C_DSI + i] = RGB(DSI_RGB[i][0], DSI_RGB[i][1], DSI_RGB[i][2]);

    make_pattern(bgGetGfxPtr(pattern), bgGetMapPtr(pattern));
    draw();
    // VRAM takes 16-bit writes only; the bitmap is 256 rows, 192 shown
    uint16_t *bmp = bgGetGfxPtr(art);
    for (int i = 0; i < W * 256 / 2; i++)
        bmp[i] = i < W * H / 2 ? canvas[2 * i] | (canvas[2 * i + 1] << 8) : 0;
    free(canvas);
    canvas = NULL;

    animate(0);
    bgUpdate();
    cothread_create(top_thread, NULL, 4096, COTHREAD_DETACHED);
}

void top_set(TopState s)
{
    state = s;
}
