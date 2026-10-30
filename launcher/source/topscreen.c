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
//
// The modern look keeps the bitmap's pixels in memory, so its parts can be
// drawn again (with ui.h's calls) and the rows that changed copied over: the
// status chip, the battery (read every 2 s by the same cothread), the note
// under the DSi (drawn 3x there, to make room for it), and the picked game's
// or save's details in the DSi's place.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <nds.h>

#include "topscreen.h"
#include "ui.h"

#define W          256
#define H          192
#define SCALE      4
#define BAR_H      20
#define DSI_W      35
#define DSI_H      40
#define DSI_X      ((W - DSI_W * SCALE) / 2)
#define DSI_Y      (BAR_H + (H - BAR_H - DSI_H * SCALE) / 2)
#define M_SCALE    3        // the modern look's DSi
#define M_DSI_X    ((W - DSI_W * M_SCALE) / 2)
#define M_DSI_Y    (BAR_H + 6)
#define NOTE_Y     152
#define BATTERY_FRAMES 120

#define RGB(r, g, b)  RGB15((r) >> 3, (g) >> 3, (b) >> 3)
#define GREEN      RGB(88, 208, 128)
#define RED        RGB(232, 72, 56)
#define WIFI_ON    RGB(129, 148, 174)    // the overlay's arcs while it looks
#define WIFI_OFF   RGB(46, 56, 70)
#define METER_OFF  RGB(66, 90, 102)
#define AMBER      RGB(240, 192, 48)

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
    // The modern look's (the bar's colors are its panels' too)
    C_GREEN = C_DSI + 8, C_GREEN_DARK,
    C_AMBER, C_AMBER_DARK,
    C_RED, C_RED_DARK,
    C_CYAN, C_CYAN_DARK,
    C_GREY, C_DIM, C_WHITE,
    C_BANNER = 224,             // 2 x 16: the picked game's banner icon, in turns
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
static int scale = SCALE, dsi_x = DSI_X, dsi_y = DSI_Y;

// The modern look
static bool modern;
static Canvas cv;           // canvas, as ui.h draws on it
static char note[2][48];
static int battery_pct = -1;
static bool battery_charging;
static enum { VIEW_DSI, VIEW_GAME, VIEW_SAVE, VIEW_CHEEVO } view;
static int icon_bank;       // the half of C_BANNER's entries the new icon uses

// The battery (14x8, its level drawn inside) and the charging bolt
static const char *const BATTERY[8] = {
    "111111111111..", "1..........1..", "1..........111", "1..........111",
    "1..........111", "1..........111", "1..........1..", "111111111111..",
};
static const char *const BOLT[8] = {
    "...1", "..11", ".11.", "1111", "1111", ".11.", "11..", "1...",
};
static const char *const STAR[7] = {
    "...1...", "...1...", "1111111", ".11111.", "..111..", ".11.11.", ".1...1.",
};

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
    if (y < cv.dirty_top)
        cv.dirty_top = y;
    if (y + h > cv.dirty_bottom)
        cv.dirty_bottom = y + h;
}

// One of the DSi's pixels, SCALE x SCALE (off: where its shadow falls)
static void dsi_pixel(int x, int y, int off, uint8_t c)
{
    fill(dsi_x + x * scale + off, dsi_y + y * scale + off, scale, scale, c);
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

static void draw_dsi(void);

static void draw_bar(void)
{
    fill(0, 0, W, BAR_H, C_BAR);
    fill(0, 0, W, 1, C_BAR_HI);
    fill(0, BAR_H - 1, W, 1, C_BAR_LO);
    title(10, 5, C_TEXT_SHADOW);
    title(8, 3, C_TEXT);
}

static void draw(void)
{
    // The header bar, its name and the meter
    draw_bar();
    for (int i = 0; i < 3; i++)
        fill(W - 30 + i * 8, 16 - 4 * (i + 1), 5, 4 * (i + 1), C_METER + i);
    draw_dsi();
}

static void draw_dsi(void)
{
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
    {
        // (LINES is at 4x)
        int top = LINES[i][0] * scale / 4, bottom = LINES[i][1] * scale / 4;
        fill(dsi_x + LINES_X0 * scale / 4, dsi_y + top, (LINES_X1 - LINES_X0) * scale / 4,
             bottom > top ? bottom - top : 1, C_LINES);
    }
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

void top_animate(unsigned frame)
{
    // The diamonds drift down and right, a pixel every 7 frames (the
    // overlay's 120 ms)
    uint16_t shift = (frame / 7) % 16;
    REG_BG0HOFS = (uint16_t)-shift;
    REG_BG0VOFS = (uint16_t)-shift;

    switch (state)
    {
    case TOP_CONNECTING:
        // The overlay's pace: an arc every 400 ms, a bar every 350 ms (in
        // the modern look, the lit arcs are amber, like its chip)
        if (modern)
            set_parts(C_WIFI, 4, 1 + (frame / 24) % 4, AMBER, WIFI_ON);
        else
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

// ---------------------------------------------------------------------------
// The modern look

static uint16_t *bitmap;    // BG3's pixels

// Copies the rows that changed to the screen
static void present(void)
{
    if (canvas == NULL || cv.dirty_top >= cv.dirty_bottom)
        return;
    if (cv.dirty_bottom - cv.dirty_top >= 48)
        cothread_yield_irq(IRQ_VBLANK);
    // (looked at again after the wait: the animation's cothread may have
    // copied them meanwhile)
    if (cv.dirty_top >= cv.dirty_bottom)
        return;
    int top = cv.dirty_top < 0 ? 0 : cv.dirty_top, bottom = cv.dirty_bottom > H ? H : cv.dirty_bottom;
    cv.dirty_top = H;
    cv.dirty_bottom = 0;
    volatile uint32_t *dst = (volatile uint32_t *)bitmap + top * (W / 4);
    const uint32_t *src = (const uint32_t *)(canvas + top * W);
    for (int i = 0; i < (bottom - top) * (W / 4); i++)
        dst[i] = src[i];
}

static void panel(int x, int y, int w, int h)
{
    ui_fill(&cv, x, y, w, h, C_BAR_LO);
    ui_fill(&cv, x + 2, y + 2, w - 4, h - 4, C_BAR);
}

// The bar's right end: the status chip, and the battery left of it
static void draw_status(void)
{
    static const char *const WORDS[] = {
        [TOP_CONNECTING] = "Connecting", [TOP_CONNECTED] = "Connected",
        [TOP_FAILED] = "No Wi-Fi", [TOP_OFFLINE] = "Offline",
    };
    static const uint8_t FILLS[] = {
        [TOP_CONNECTING] = C_AMBER, [TOP_CONNECTED] = C_GREEN, [TOP_FAILED] = C_RED, [TOP_OFFLINE] = C_GREY,
    };
    static const uint8_t INKS[] = {
        [TOP_CONNECTING] = C_AMBER_DARK, [TOP_CONNECTED] = C_GREEN_DARK,
        [TOP_FAILED] = C_RED_DARK, [TOP_OFFLINE] = C_LINES,
    };
    TopState st = state;
    fill(96, 1, W - 96, BAR_H - 2, C_BAR);
    int x = W - 6 - ui_chip_width(WORDS[st]);
    ui_chip(&cv, x, 4, WORDS[st], FILLS[st], INKS[st]);
    if (battery_pct < 0)
        return;
    // Only the icon: the DSi reports its battery in a few steps, so a
    // percent would claim more than it knows
    x -= 6 + 14;
    const uint8_t outline[4] = { C_LINES, 0, 0, 0 };
    ui_art(&cv, x, 6, BATTERY, 8, outline);
    uint8_t level = battery_charging ? C_CYAN : battery_pct <= 10 ? C_RED : battery_pct <= 25 ? C_AMBER : C_GREEN;
    ui_fill(&cv, x + 2, 8, (battery_pct * 8 + 99) / 100, 4, level);
    if (battery_charging)
    {
        const uint8_t bolt[4] = { C_AMBER, 0, 0, 0 };
        ui_art(&cv, x - 6, 6, BOLT, 8, bolt);
    }
}

static void check_battery(void)
{
    bool charging;
    int pct = ui_battery(&charging);
    if (pct == battery_pct && charging == battery_charging)
        return;
    battery_pct = pct;
    battery_charging = charging;
    draw_status();
    present();
}

static void draw_note(void)
{
    fill(0, NOTE_Y, W, H - NOTE_Y, 0);
    if (note[0][0] == '\0' && note[1][0] == '\0')
        return;
    panel(8, NOTE_Y, W - 16, 34);
    int y = note[1][0] != '\0' ? NOTE_Y + 7 : NOTE_Y + 13;
    ui_text_fit(&cv, 16, y, note[0], W - 32, C_TEXT);
    if (note[1][0] != '\0')
        ui_text_fit(&cv, 16, y + 11, note[1], W - 32, C_LINES);
}

static void draw_modern_dsi(void)
{
    fill(0, BAR_H, W, H - BAR_H, 0);
    scale = M_SCALE;
    dsi_x = M_DSI_X;
    dsi_y = M_DSI_Y;
    draw_dsi();
    draw_note();
}

// "41h 12m"
static void format_playtime(char *out, size_t outsz, uint32_t secs)
{
    if (secs == 0)
        snprintf(out, outsz, "None yet");
    else if (secs < 60)
        snprintf(out, outsz, "Under a minute");
    else if (secs < 3600)
        snprintf(out, outsz, "%um", (unsigned)(secs / 60));
    else
        snprintf(out, outsz, "%uh %02um", (unsigned)(secs / 3600), (unsigned)(secs / 60 % 60));
}

// "Today", "3 days ago", "Oct 20"
static void format_ago(char *out, size_t outsz, uint32_t then, uint32_t now)
{
    static const char *const MONTHS[] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
    if (then == 0)
    {
        snprintf(out, outsz, "Never");
        return;
    }
    int days = (int)(now / 86400) - (int)(then / 86400);
    if (days <= 0)
        snprintf(out, outsz, "Today");
    else if (days == 1)
        snprintf(out, outsz, "Yesterday");
    else if (days < 30)
        snprintf(out, outsz, "%d days ago", days);
    else
    {
        time_t t = (time_t)then + 946684800;   // 2000-01-01 as a Unix time
        struct tm *tm = gmtime(&t);
        snprintf(out, outsz, "%s %d, %d", MONTHS[tm->tm_mon], tm->tm_mday, tm->tm_year + 1900);
    }
}

void top_modern(bool on)
{
    if (!on && !modern)
        return;     // the classic screen's already there
    if (on)
    {
        if (canvas == NULL)
            canvas = calloc(W * H, 1);
        if (canvas == NULL)
            return;
        cv = (Canvas){ canvas, W, H, H, 0 };
        modern = true;
        view = VIEW_DSI;
        battery_pct = ui_battery(&battery_charging);
        memset(canvas, 0, W * H);
        draw_bar();
        draw_status();
        draw_modern_dsi();
    }
    else
    {
        // The classic screen again, as top_init() drew it
        modern = false;
        if (canvas == NULL)
            canvas = calloc(W * H, 1);
        if (canvas == NULL)
            return;
        cv = (Canvas){ canvas, W, H, H, 0 };
        memset(canvas, 0, W * H);
        scale = SCALE;
        dsi_x = DSI_X;
        dsi_y = DSI_Y;
        draw();
    }
    cv.dirty_top = 0;
    cv.dirty_bottom = H;
    present();
    if (!on)
    {
        free(canvas);
        canvas = NULL;
    }
}

void top_note(const char *line1, const char *line2)
{
    snprintf(note[0], sizeof(note[0]), "%s", line1 != NULL ? line1 : "");
    snprintf(note[1], sizeof(note[1]), "%s", line2 != NULL ? line2 : "");
    if (modern && canvas != NULL && view == VIEW_DSI)
    {
        draw_note();
        present();
    }
}

void top_dsi(void)
{
    if (!modern || canvas == NULL || view == VIEW_DSI)
        return;
    view = VIEW_DSI;
    draw_modern_dsi();
    present();
}

void top_game(const TopGame *g)
{
    if (!modern || canvas == NULL)
        return;
    view = VIEW_GAME;
    fill(0, BAR_H, W, H - BAR_H, 0);
    char line[48];

    // The game: its icon twice its size on white, its name, publisher and code
    panel(8, 26, W - 16, 82);
    fill(14, 33, 68, 68, C_BAR_LO);
    fill(16, 35, 64, 64, C_WHITE);
    if (g->icon != NULL && g->icon->ok)
    {
        // Its colors where the icon on the screen isn't looking, until the
        // new one is copied over
        icon_bank ^= 1;
        uint8_t first = C_BANNER + icon_bank * 16;
        for (int i = 1; i < 16; i++)
            BG_PALETTE[first + i - 1] = g->icon->pal[i];
        ui_banner(&cv, 16, 35, g->icon, 2, first);
    }
    int tx = 90, tw = W - 16 - tx - 4;
    int lines = ui_text_wrap(&cv, tx, 36, g->title, tw - (g->favorite ? 10 : 0), 3, C_TEXT);
    int y = 36 + lines * UI_LINE + 4;
    if (g->publisher != NULL && g->publisher[0] != '\0')
    {
        ui_text_fit(&cv, tx, y, g->publisher, tw, C_LINES);
        y += UI_LINE + 2;
    }
    if (g->code != NULL && g->code[0] != '\0' && y <= 92)
    {
        if (g->version > 0)
            snprintf(line, sizeof(line), "%s, Rev %d", g->code, g->version);
        else
            snprintf(line, sizeof(line), "%s", g->code);
        ui_text(&cv, tx, y, line, C_DIM);
    }
    if (g->favorite)
    {
        const uint8_t star[4] = { C_AMBER, 0, 0, 0 };
        ui_art(&cv, W - 16 - 4 - 7, 34, STAR, 7, star);
    }

    // Its achievements, playtime and when it was last played
    panel(8, 114, W - 16, 72);
    int ry = 122;
    ui_text(&cv, 16, ry, "Achievements", C_LINES);
    if (g->total > 0)
    {
        snprintf(line, sizeof(line), "%d / %d", g->earned, g->total);
        ui_text_right(&cv, W - 16, ry, line, C_TEXT);
        ui_fill(&cv, 16, ry + 11, W - 32, 6, C_BAR_LO);
        ui_fill(&cv, 17, ry + 12, (W - 34) * g->earned / g->total, 4, C_GREEN);
    }
    else
    {
        ui_text_right(&cv, W - 16, ry, "No set yet", C_DIM);
    }
    ry += 25;
    ui_text(&cv, 16, ry, "Playtime", C_LINES);
    format_playtime(line, sizeof(line), g->playtime);
    ui_text_right(&cv, W - 16, ry, line, g->playtime ? C_TEXT : C_DIM);
    ry += 14;
    ui_text(&cv, 16, ry, "Last played", C_LINES);
    format_ago(line, sizeof(line), g->last_played, g->now);
    ui_text_right(&cv, W - 16, ry, line, g->last_played ? C_TEXT : C_DIM);
    present();
}

void top_save(const TopSave *s)
{
    if (!modern || canvas == NULL)
        return;
    view = VIEW_SAVE;
    fill(0, BAR_H, W, H - BAR_H, 0);
    char line[48];

    // Its name and size
    panel(8, 26, W - 16, 22);
    int sw = ui_text_width(s->size);
    ui_text_fit(&cv, 16, 33, s->name, W - 32 - sw - 8, C_TEXT);
    ui_text_right(&cv, W - 16, 33, s->size, C_LINES);

    // What the sync does with it, in its color
    static const uint8_t TONE_FILL[] = { C_GREEN, C_CYAN, C_AMBER, C_RED, C_GREY };
    static const uint8_t TONE_INK[] = { C_GREEN_DARK, C_CYAN_DARK, C_AMBER_DARK, C_RED_DARK, C_LINES };
    fill(8, 54, W - 16, 30, C_BAR_LO);
    fill(10, 56, W - 20, 26, TONE_FILL[s->tone]);
    int lines = ui_text_wrap(NULL, 0, 0, s->status, W - 32, 2, 0);
    ui_text_wrap(&cv, 16, lines > 1 ? 59 : 65, s->status, W - 32, 2, TONE_INK[s->tone]);

    // When each side's was saved
    int cw = (W - 16 - 6) / 2, rx = 8 + cw + 6;
    panel(8, 90, cw, 50);
    panel(rx, 90, cw, 50);
    snprintf(line, sizeof(line), "This %s", s->console);
    ui_text(&cv, 16, 98, line, C_LINES);
    ui_text_fit(&cv, 16, 111, s->here != NULL ? s->here : "No save", cw - 16, s->here != NULL ? C_GREEN : C_DIM);
    ui_text(&cv, rx + 8, 98, "On the PC", C_LINES);
    ui_text_fit(&cv, rx + 8, 111, s->there != NULL ? s->there : "Nothing yet", cw - 16,
                s->there != NULL ? C_CYAN : C_DIM);
    if (s->from != NULL && s->from[0] != '\0')
    {
        snprintf(line, sizeof(line), "from %s", s->from);
        ui_text_fit(&cv, rx + 8, 124, line, cw - 16, C_DIM);
    }

    // The versions DSiRPC keeps
    panel(8, 146, W - 16, 38);
    if (s->versions > 0)
    {
        snprintf(line, sizeof(line), "%d version%s on the PC", s->versions, s->versions == 1 ? "" : "s");
        ui_text(&cv, 16, 153, line, C_TEXT);
        ui_text(&cv, 16, 166, "X restores an older one", C_DIM);
    }
    else
    {
        ui_text(&cv, 16, 159, "No versions on the PC yet", C_DIM);
    }
    present();
}

void top_cheevo(const TopCheevo *a)
{
    if (!modern || canvas == NULL)
        return;
    view = VIEW_CHEEVO;
    fill(0, BAR_H, W, H - BAR_H, 0);
    char line[48];

    // The game, and the achievement's title
    panel(8, 26, W - 16, 46);
    ui_text_fit(&cv, 16, 33, a->game, W - 32, C_DIM);
    ui_text_wrap(&cv, 16, 46, a->title, W - 32, 2, C_TEXT);

    // What it asks for
    panel(8, 78, W - 16, 72);
    ui_text_wrap(&cv, 16, 86, a->description, W - 32, 6, C_LINES);

    // Its points, and whether it's earned
    panel(8, 156, W - 16, 28);
    snprintf(line, sizeof(line), "%d point%s", a->points, a->points == 1 ? "" : "s");
    ui_text(&cv, 16, 166, line, C_TEXT);
    if (a->state == 1 && a->when != 0)
    {
        static const char *const MONTHS[] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
        time_t t = (time_t)a->when + 946684800;
        struct tm *tm = gmtime(&t);
        snprintf(line, sizeof(line), "Earned %s %d, %d", MONTHS[tm->tm_mon], tm->tm_mday, tm->tm_year + 1900);
    }
    else
    {
        snprintf(line, sizeof(line), "%s",
                 a->state == 1 ? "Earned" : a->state == 2 ? "Waiting for DSiRPC" : "Not earned yet");
    }
    ui_text_right(&cv, W - 16, 166, line, a->state == 1 ? C_GREEN : a->state == 2 ? C_AMBER : C_DIM);
    present();
}

static int top_thread(void *arg)
{
    (void)arg;
    for (unsigned frame = 1;; frame++)
    {
        cothread_yield_irq(IRQ_VBLANK);
        top_animate(frame);
        if (modern && frame % BATTERY_FRAMES == 0)
            check_battery();
    }
    return 0;
}

void top_init(void)
{
    canvas = calloc(W * H, 1);
    if (canvas == NULL)
        return;
    cv = (Canvas){ canvas, W, H, H, 0 };

    lcdMainOnTop();
    videoSetMode(MODE_5_2D);
    vramSetBankA(VRAM_A_MAIN_BG);
    setBrightness(1, 0);
    REG_BLDCNT = 0;
    int pattern = bgInit(0, BgType_Text8bpp, BgSize_T_256x256, 0, 1);
    int art = bgInit(3, BgType_Bmp8, BgSize_B8_256x256, 4, 0);
    bgSetPriority(art, 0);
    bgSetPriority(pattern, 1);
    bitmap = bgGetGfxPtr(art);

    static const uint8_t rgb[][3] = {
        [C_BACKDROP] = { 40, 104, 112 }, [C_TILE] = { 52, 122, 130 }, [C_DOT] = { 70, 142, 148 },
        [C_BAR] = { 32, 48, 58 }, [C_BAR_HI] = { 66, 90, 102 }, [C_BAR_LO] = { 16, 24, 32 },
        [C_TEXT] = { 248, 248, 248 }, [C_TEXT_SHADOW] = { 24, 32, 40 },
        [C_SHADOW] = { 30, 84, 92 }, [C_LINES] = { 201, 208, 220 },
    };
    static const uint8_t modern_rgb[][3] = {
        [C_GREEN - C_GREEN] = { 88, 208, 128 }, [C_GREEN_DARK - C_GREEN] = { 16, 36, 26 },
        [C_AMBER - C_GREEN] = { 240, 192, 48 }, [C_AMBER_DARK - C_GREEN] = { 42, 32, 8 },
        [C_RED - C_GREEN] = { 232, 72, 56 }, [C_RED_DARK - C_GREEN] = { 44, 14, 10 },
        [C_CYAN - C_GREEN] = { 72, 200, 232 }, [C_CYAN_DARK - C_GREEN] = { 12, 36, 48 },
        [C_GREY - C_GREEN] = { 44, 60, 82 }, [C_DIM - C_GREEN] = { 159, 176, 200 },
        [C_WHITE - C_GREEN] = { 248, 248, 248 },
    };
    for (int i = 0; i <= C_LINES; i++)
        BG_PALETTE[i] = RGB(rgb[i][0], rgb[i][1], rgb[i][2]);
    for (int i = 0; i < 8; i++)
        BG_PALETTE[C_DSI + i] = RGB(DSI_RGB[i][0], DSI_RGB[i][1], DSI_RGB[i][2]);
    for (int i = C_GREEN; i <= C_WHITE; i++)
        BG_PALETTE[i] = RGB(modern_rgb[i - C_GREEN][0], modern_rgb[i - C_GREEN][1], modern_rgb[i - C_GREEN][2]);

    make_pattern(bgGetGfxPtr(pattern), bgGetMapPtr(pattern));
    draw();
    // VRAM takes 16-bit writes only; the bitmap is 256 rows, 192 shown
    uint16_t *bmp = bitmap;
    for (int i = 0; i < W * 256 / 2; i++)
        bmp[i] = i < W * H / 2 ? canvas[2 * i] | (canvas[2 * i + 1] << 8) : 0;
    free(canvas);
    canvas = NULL;

    top_animate(0);
    bgUpdate();
    cothread_create(top_thread, NULL, 8192, COTHREAD_DETACHED);   // (the battery's drawn from it)
}

void top_set(TopState s)
{
    state = s;
    if (modern && canvas != NULL)
    {
        draw_status();
        present();
    }
}
