// SPDX-License-Identifier: MIT
//
// The modern look's drawing (see ui.h). The bottom screen's bitmap is BG3 in
// mode 5, 64 KB into VRAM C: above the text console's font (from 0) and map
// (at 62 KB), which stay where consoleDemoInit() put them for the classic
// look. VRAM takes no 8-bit writes, so the bitmap is drawn in memory and the
// rows that changed are copied over by ui_present().
//
// The spinner turns by palette: its 8 dots are 8 palette entries, lit in turn
// by a cothread every few frames, so it keeps turning whatever the launcher
// does, as long as it waits for frames (the network code does).
//
// The sounds are short samples made once at startup (soft sine notes that
// fade fast), so they stop by themselves and nothing has to stop them.

#include <malloc.h>
#include <stdlib.h>
#include <string.h>

#include <nds.h>

#include "music.h"
#include "sync.h"
#include "ui.h"

#define RGB(r, g, b)  RGB15((r) >> 3, (g) >> 3, (b) >> 3)

#define BMP_BASE      4         // the bitmap's place in VRAM C, in 16 KB
#define BIG_CHANGE    48        // rows: copied from the start of a blank
#define SPIN_FRAMES   5         // the spinner's next dot
#define SOUND_RATE    16384
#define MAX_HITS      24
#define MAX_FOOTER    6

static uint8_t screen_px[UI_W * UI_H] __attribute__((aligned(32)));
static Canvas screen = { screen_px, UI_W, UI_H, 0, UI_H };
static bool on;
static int bmp_bg = -1;

static const uint8_t *font;     // the console's: 8x8, 1 bit a pixel (bit 0 left), from ' '
static uint8_t glyph_left[96], glyph_width[96];

static const uint8_t RGBS[UI_SPIN][3] = {
    [UI_CLEAR] = { 28, 39, 51 }, [UI_BG] = { 28, 39, 51 },
    [UI_BAR] = { 20, 28, 38 }, [UI_EDGE] = { 14, 20, 27 },
    [UI_PANEL] = { 38, 54, 74 }, [UI_PANEL_HI] = { 52, 80, 106 }, [UI_PANEL_LO] = { 24, 34, 46 },
    [UI_CHIP] = { 44, 60, 82 },
    [UI_TEXT] = { 232, 238, 247 }, [UI_DIM] = { 159, 176, 200 }, [UI_SOFT] = { 197, 209, 227 },
    [UI_GREEN] = { 88, 208, 128 }, [UI_GREEN_DARK] = { 16, 36, 26 },
    [UI_CYAN] = { 72, 200, 232 }, [UI_CYAN_DARK] = { 12, 36, 48 },
    [UI_AMBER] = { 240, 192, 48 }, [UI_AMBER_DARK] = { 42, 32, 8 },
    [UI_RED] = { 232, 72, 56 }, [UI_RED_DARK] = { 44, 14, 10 },
    [UI_SCROLL] = { 74, 92, 120 }, [UI_ICON] = { 201, 208, 220 },
};

// The spinner's dots (2x2, clockwise from the top) and their colors, the lit
// one first, then its fading tail
static const uint8_t SPIN_DOTS[8][2] = {
    { 5, 0 }, { 8, 2 }, { 10, 5 }, { 8, 8 }, { 5, 10 }, { 2, 8 }, { 0, 5 }, { 2, 2 },
};
static const uint8_t SPIN_RGB[8][3] = {
    { 240, 192, 48 }, { 196, 160, 58 }, { 150, 128, 66 }, { 112, 104, 84 },
    { 74, 92, 120 }, { 74, 92, 120 }, { 74, 92, 120 }, { 74, 92, 120 },
};

// The steps' icons, 12x12: 1 the box, 2 the mark
static const char *const ICON_CHECK[12] = {
    ".1111111111.", "111111111111", "111111111121", "111111111221",
    "111111112211", "112111122111", "112211221111", "111222211111",
    "111122111111", "111111111111", "111111111111", ".1111111111.",
};
static const char *const ICON_CROSS[12] = {
    ".1111111111.", "111111111111", "112211112211", "111221122111",
    "111122221111", "111112211111", "111112211111", "111122221111",
    "111221122111", "112211112211", "111111111111", ".1111111111.",
};
static const char *const ICON_DASH[12] = {
    ".1111111111.", "111111111111", "111111111111", "111111111111",
    "111111111111", "112222222211", "112222222211", "111111111111",
    "111111111111", "111111111111", "111111111111", ".1111111111.",
};

typedef struct
{
    int16_t x, y, w, h;
    int id;
} Hit;

static Hit hits[MAX_HITS];
static int n_hits;
static Hit footer[MAX_FOOTER];
static int n_footer;

// ---------------------------------------------------------------------------
// The screen

static void mark(Canvas *c, int top, int bottom)
{
    if (top < c->dirty_top)
        c->dirty_top = top;
    if (bottom > c->dirty_bottom)
        c->dirty_bottom = bottom;
}

static void load_palette(void)
{
    for (int i = 0; i < UI_SPIN; i++)
        BG_PALETTE_SUB[i] = RGB(RGBS[i][0], RGBS[i][1], RGBS[i][2]);
    for (int i = 0; i < 8; i++)
        BG_PALETTE_SUB[UI_SPIN + i] = RGB(SPIN_RGB[4][0], SPIN_RGB[4][1], SPIN_RGB[4][2]);
}

static int spin_thread(void *arg)
{
    (void)arg;
    for (unsigned frame = 0;; frame++)
    {
        cothread_yield_irq(IRQ_VBLANK);
        if (!on || frame % SPIN_FRAMES != 0)
            continue;
        unsigned step = frame / SPIN_FRAMES;
        for (int i = 0; i < 8; i++)
        {
            const uint8_t *c = SPIN_RGB[(step - i) & 7];
            BG_PALETTE_SUB[UI_SPIN + i] = RGB(c[0], c[1], c[2]);
        }
    }
    return 0;
}

static void make_sounds(void);

void ui_init(void)
{
    font = consoleGetDefault()->font.gfx;
    for (int ch = 0; ch < 96; ch++)
    {
        const uint8_t *g = font + ch * 8;
        uint8_t cols = 0;
        for (int row = 0; row < 8; row++)
            cols |= g[row];
        int left = 0, right = 7;
        while (left < 8 && !(cols & (1 << left)))
            left++;
        while (right >= 0 && !(cols & (1 << right)))
            right--;
        glyph_left[ch] = left < 8 ? left : 0;
        glyph_width[ch] = left < 8 ? right - left + 1 : 3;   // a space: 3 (and the gap)
    }
    soundEnable();
    music_init();
    make_sounds();
    cothread_create(spin_thread, NULL, 2048, COTHREAD_DETACHED);
}

void ui_enter(void)
{
    videoSetModeSub(MODE_5_2D);
    vramSetBankC(VRAM_C_SUB_BG);
    bmp_bg = bgInitSub(3, BgType_Bmp8, BgSize_B8_256x256, BMP_BASE, 0);
    bgUpdate();
    load_palette();
    on = true;
    mark(&screen, 0, UI_H);     // all of it at the next ui_present()
}

void ui_leave(void)
{
    on = false;
    consoleDemoInit();
    BG_PALETTE_SUB[0] = 0;      // the console's black, not the bitmap's backdrop
    consoleClear();
}

bool ui_on(void)
{
    return on;
}

Canvas *ui_screen(void)
{
    return &screen;
}

void ui_clear(void)
{
    memset(screen_px, UI_BG, sizeof(screen_px));
    mark(&screen, 0, UI_H);
    n_hits = 0;
    n_footer = 0;
}

void ui_present(void)
{
    Canvas *c = &screen;
    if (!on || c->dirty_top >= c->dirty_bottom)
        return;
    int top = c->dirty_top < 0 ? 0 : c->dirty_top;
    int bottom = c->dirty_bottom > UI_H ? UI_H : c->dirty_bottom;
    if (bottom - top >= BIG_CHANGE)
        cothread_yield_irq(IRQ_VBLANK);   // so it's all there before the screen draws it
    // (volatile: a plain loop could become a memcpy() with byte writes)
    volatile uint32_t *dst = (volatile uint32_t *)bgGetGfxPtr(bmp_bg) + top * (UI_W / 4);
    const uint32_t *src = (const uint32_t *)(c->px + top * UI_W);
    for (int i = 0; i < (bottom - top) * (UI_W / 4); i++)
        dst[i] = src[i];
    c->dirty_top = c->h;
    c->dirty_bottom = 0;
}

// ---------------------------------------------------------------------------
// Drawing

void ui_fill(Canvas *c, int x, int y, int w, int h, uint8_t color)
{
    if (x < 0)
    {
        w += x;
        x = 0;
    }
    if (y < 0)
    {
        h += y;
        y = 0;
    }
    if (x + w > c->w)
        w = c->w - x;
    if (y + h > c->h)
        h = c->h - y;
    if (w <= 0 || h <= 0)
        return;
    for (int yy = y; yy < y + h; yy++)
        memset(c->px + yy * c->w + x, color, w);
    mark(c, y, y + h);
}

void ui_frame(Canvas *c, int x, int y, int w, int h, int t, uint8_t color)
{
    ui_fill(c, x, y, w, t, color);
    ui_fill(c, x, y + h - t, w, t, color);
    ui_fill(c, x, y + t, t, h - 2 * t, color);
    ui_fill(c, x + w - t, y + t, t, h - 2 * t, color);
}

void ui_round(Canvas *c, int x, int y, int w, int h, int r, uint8_t color)
{
    for (int i = 0; i < r; i++)
    {
        // Each of the first r rows (and the last r) a pixel wider than the one before
        int in = r - i;
        ui_fill(c, x + in, y + i, w - 2 * in, 1, color);
        ui_fill(c, x + in, y + h - 1 - i, w - 2 * in, 1, color);
    }
    ui_fill(c, x, y + r, w, h - 2 * r, color);
}

static void plot(Canvas *c, int x, int y, uint8_t color)
{
    if (x >= 0 && x < c->w && y >= 0 && y < c->h)
        c->px[y * c->w + x] = color;
}

char ui_ascii(uint32_t cp)
{
    // Latin-1's letters (U+00C0 to U+00FF) as their plain ones
    static const char LATIN[] = "AAAAAAACEEEEIIIIDNOOOOOxOUUUUYPsaaaaaaaceeeeiiiidnooooo/ouuuuypy";
    if (cp >= 32 && cp < 127)
        return (char)cp;
    if (cp >= 0xC0 && cp <= 0xFF)
        return LATIN[cp - 0xC0];
    switch (cp)
    {
    case 0x2018: case 0x2019: case 0xB4:
        return '\'';
    case 0x201C: case 0x201D:
        return '"';
    case 0x2013: case 0x2014:
        return '-';
    case 0x2026: case 0xB7:
        return '.';
    case 0xA0: case 0x3000:
        return ' ';
    default:
        return '?';
    }
}

// The next letter of UTF-8 text, as one of the font's; 0 at the end
static int next_char(const char **s)
{
    const uint8_t *p = (const uint8_t *)*s;
    while (p[0] == 0x1B && p[1] == '[')
    {
        // A console color code ("\x1b[32;1m"): not for this screen
        p += 2;
        while (*p != '\0' && !((*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z')))
            p++;
        if (*p != '\0')
            p++;
    }
    uint32_t c = *p;
    if (c == 0)
    {
        *s = (const char *)p;
        return 0;
    }
    p++;
    int more = 0;
    if (c >= 0x80)
    {
        if ((c & 0xE0) == 0xC0)
        {
            c &= 0x1F;
            more = 1;
        }
        else if ((c & 0xF0) == 0xE0)
        {
            c &= 0x0F;
            more = 2;
        }
        else if ((c & 0xF8) == 0xF0)
        {
            c &= 0x07;
            more = 3;
        }
        else
        {
            c = '?';
        }
        while (more-- > 0 && (*p & 0xC0) == 0x80)
            c = (c << 6) | (*p++ & 0x3F);
    }
    *s = (const char *)p;
    if (c == '\n')
        return ' ';
    return (unsigned char)ui_ascii(c);
}

static int advance(int ch)
{
    return glyph_width[ch - 32] + 1;
}

static void glyph(Canvas *c, int x, int y, int ch, uint8_t color)
{
    const uint8_t *g = font + (ch - 32) * 8;
    int left = glyph_left[ch - 32], w = glyph_width[ch - 32];
    for (int row = 0; row < 8; row++)
    {
        uint8_t bits = g[row] >> left;
        for (int col = 0; col < w; col++)
        {
            if (bits & (1 << col))
                plot(c, x + col, y + row, color);
        }
    }
}

int ui_text(Canvas *c, int x, int y, const char *s, uint8_t color)
{
    int ch;
    while ((ch = next_char(&s)) != 0)
    {
        glyph(c, x, y, ch, color);
        x += advance(ch);
    }
    mark(c, y, y + 8);
    return x;
}

int ui_text_width(const char *s)
{
    int w = 0, ch;
    while ((ch = next_char(&s)) != 0)
        w += advance(ch);
    return w > 0 ? w - 1 : 0;
}

int ui_text_fit(Canvas *c, int x, int y, const char *s, int max_w, uint8_t color)
{
    if (ui_text_width(s) <= max_w)
        return ui_text(c, x, y, s, color);
    int room = max_w - ui_text_width("..."), w = 0, ch;
    const char *p = s;
    while ((ch = next_char(&p)) != 0 && w + advance(ch) - 1 <= room)
    {
        glyph(c, x + w, y, ch, color);
        w += advance(ch);
    }
    mark(c, y, y + 8);
    return ui_text(c, x + w, y, "...", color);
}

void ui_text_right(Canvas *c, int right, int y, const char *s, uint8_t color)
{
    ui_text(c, right - ui_text_width(s), y, s, color);
}

void ui_text_center(Canvas *c, int cx, int y, const char *s, uint8_t color)
{
    ui_text(c, cx - ui_text_width(s) / 2, y, s, color);
}

void ui_text_shadow(Canvas *c, int x, int y, const char *s, uint8_t color, uint8_t shadow)
{
    ui_text(c, x + 1, y + 1, s, shadow);
    ui_text(c, x, y, s, color);
}

int ui_text_wrap(Canvas *c, int x, int y, const char *s, int max_w, int max_lines, uint8_t color)
{
    char line[160];
    int lines = 0;
    while (*s != '\0' && lines < max_lines)
    {
        // As many words as fit, up to the end of the line
        const char *end = NULL, *p = s;
        while (1)
        {
            const char *w = p;
            while (*w == ' ')
                w++;
            while (*w != '\0' && *w != ' ' && *w != '\n')
                w++;
            size_t n = (size_t)(w - s);
            if (n >= sizeof(line))
                break;
            memcpy(line, s, n);
            line[n] = '\0';
            if (ui_text_width(line) > max_w && end != NULL)
                break;
            end = w;
            if (ui_text_width(line) > max_w || *w == '\0' || *w == '\n')
                break;
            p = w;
        }
        if (end == NULL)
            end = s + 1;
        size_t n = (size_t)(end - s);
        if (n >= sizeof(line))
            n = sizeof(line) - 1;
        memcpy(line, s, n);
        line[n] = '\0';
        if (c != NULL)
            ui_text_fit(c, x, y, line, max_w, color);
        y += UI_LINE;
        lines++;
        s = end;
        while (*s == ' ')
            s++;
        if (*s == '\n')
            s++;
    }
    return lines;
}

void ui_art(Canvas *c, int x, int y, const char *const *rows, int h, const uint8_t colors[4])
{
    for (int row = 0; row < h; row++)
    {
        for (int col = 0; rows[row][col] != '\0'; col++)
        {
            char k = rows[row][col];
            if (k >= '1' && k <= '4')
                plot(c, x + col, y + row, colors[k - '1']);
        }
    }
    mark(c, y, y + h);
}

int ui_chip_width(const char *text)
{
    return ui_text_width(text) + 8;
}

int ui_chip(Canvas *c, int x, int y, const char *text, uint8_t fill, uint8_t ink)
{
    int w = ui_chip_width(text);
    ui_fill(c, x, y, w, 12, fill);
    ui_text(c, x + 4, y + 2, text, ink);
    return w;
}

void ui_bar(Canvas *c, int x, int y, int w, int h, int pct, uint8_t fill)
{
    if (pct < 0)
        pct = 0;
    if (pct > 100)
        pct = 100;
    ui_frame(c, x, y, w, h, 1, UI_EDGE);
    ui_fill(c, x + 1, y + 1, w - 2, h - 2, UI_BAR);
    ui_fill(c, x + 1, y + 1, (w - 2) * pct / 100, h - 2, fill);
}

void ui_banner(Canvas *c, int x, int y, const UiBanner *b, int scale, uint8_t first)
{
    if (!b->ok)
        return;
    for (int py = 0; py < 32; py++)
    {
        for (int px = 0; px < 32; px++)
        {
            uint8_t v = b->px[py * 32 + px];
            if (v == 0)
                continue;
            for (int dy = 0; dy < scale; dy++)
            {
                for (int dx = 0; dx < scale; dx++)
                    plot(c, x + px * scale + dx, y + py * scale + dy, first + v - 1);
            }
        }
    }
    mark(c, y, y + 32 * scale);
}

void ui_banner_half(Canvas *c, int x, int y, const UiBanner *b, uint8_t first)
{
    if (!b->ok)
        return;
    for (int py = 0; py < 16; py++)
    {
        for (int px = 0; px < 16; px++)
        {
            // The color most of the 2x2 block has (clear if most of it is)
            const uint8_t *p = b->px + py * 2 * 32 + px * 2;
            uint8_t v[4] = { p[0], p[1], p[32], p[33] };
            int best = 0, best_n = 0;
            for (int i = 0; i < 4; i++)
            {
                int n = 0;
                for (int j = 0; j < 4; j++)
                    n += v[j] == v[i];
                if (n > best_n || (n == best_n && v[best] == 0))
                {
                    best = i;
                    best_n = n;
                }
            }
            if (v[best] != 0)
                plot(c, x + px, y + py, first + v[best] - 1);
        }
    }
    mark(c, y, y + 16);
}

uint8_t ui_banner_slot(int slot, const UiBanner *b)
{
    uint8_t first = UI_BANNERS + (slot % UI_BANNER_SLOTS) * 16;
    for (int i = 1; i < 16; i++)
        BG_PALETTE_SUB[first + i - 1] = b->pal[i];
    return first;
}

// ---------------------------------------------------------------------------
// The screen's parts

void ui_header(const char *title)
{
    ui_fill(&screen, 0, 0, UI_W, UI_BAR_H - 2, UI_BAR);
    ui_fill(&screen, 0, UI_BAR_H - 2, UI_W, 2, UI_EDGE);
    if (title != NULL)
        ui_text_fit(&screen, 8, 5, title, UI_W - 16, UI_SOFT);
}

int ui_header_right(const char *text, uint8_t color)
{
    int x = UI_W - 8 - ui_text_width(text);
    ui_fill(&screen, x - 4, 0, UI_W - x + 4, UI_BAR_H - 2, UI_BAR);
    ui_text(&screen, x, 5, text, color);
    return x;
}

void ui_footer(const UiKey *keys, int n)
{
    ui_fill(&screen, 0, UI_FOOT_Y, UI_W, 2, UI_EDGE);
    ui_fill(&screen, 0, UI_FOOT_Y + 2, UI_W, UI_H - UI_FOOT_Y - 2, UI_BAR);
    n_footer = 0;
    int x = 4;
    for (int i = 0; i < n && i < MAX_FOOTER; i++)
    {
        int start = x;
        x = ui_key_cap(&screen, x, UI_FOOT_Y + 5, keys[i].cap);
        x = ui_text(&screen, x + 3, UI_FOOT_Y + 7, keys[i].label, UI_SOFT);
        footer[n_footer++] = (Hit){ start - 2, UI_FOOT_Y + 2, x - start + 4, UI_H - UI_FOOT_Y - 2, (int)keys[i].key };
        x += 7;
    }
}

int ui_key_cap(Canvas *c, int x, int y, const char *cap)
{
    int w = ui_text_width(cap) + 6;
    ui_round(c, x, y, w, 12, 2, UI_TEXT);
    ui_text(c, x + 3, y + 2, cap, UI_BAR);
    return x + w;
}

void ui_panel(int x, int y, int w, int h, uint8_t border)
{
    ui_fill(&screen, x, y, w, h, border);
    ui_fill(&screen, x + 2, y + 2, w - 4, h - 4, UI_PANEL);
    ui_fill(&screen, x + 2, y + 2, w - 4, 1, UI_PANEL_HI);
    ui_fill(&screen, x + 2, y + h - 3, w - 4, 1, UI_PANEL_LO);
}

void ui_spinner(Canvas *c, int x, int y)
{
    for (int i = 0; i < 8; i++)
        ui_fill(c, x + SPIN_DOTS[i][0], y + SPIN_DOTS[i][1], 2, 2, UI_SPIN + i);
}

void ui_icon(Canvas *c, int x, int y, StepState state, uint8_t box, uint8_t mark)
{
    const uint8_t colors[4] = { box, mark, 0, 0 };
    switch (state)
    {
    case STEP_WAITING:
        ui_frame(c, x, y, 12, 12, 1, box);
        break;
    case STEP_ACTIVE:
        ui_spinner(c, x, y);
        break;
    case STEP_DONE:
        ui_art(c, x, y, ICON_CHECK, 12, colors);
        break;
    case STEP_FAILED:
        ui_art(c, x, y, ICON_CROSS, 12, colors);
        break;
    case STEP_SKIPPED:
        ui_art(c, x, y, ICON_DASH, 12, colors);
        break;
    }
}

void ui_step(int row, StepState state, const char *label, const char *value)
{
    int y = UI_TOP + row * 18;
    ui_fill(&screen, 8, y, UI_W - 16, 16, UI_BG);
    static const uint8_t BOX[] = {
        [STEP_WAITING] = UI_SCROLL, [STEP_ACTIVE] = 0, [STEP_DONE] = UI_GREEN,
        [STEP_FAILED] = UI_RED, [STEP_SKIPPED] = UI_CHIP,
    };
    static const uint8_t MARK[] = {
        [STEP_WAITING] = 0, [STEP_ACTIVE] = 0, [STEP_DONE] = UI_GREEN_DARK,
        [STEP_FAILED] = UI_RED_DARK, [STEP_SKIPPED] = UI_DIM,
    };
    ui_icon(&screen, 12, y + 2, state, BOX[state], MARK[state]);
    int x = ui_text(&screen, 32, y + 4, label, state == STEP_WAITING ? UI_DIM : UI_TEXT);
    if (value != NULL && value[0] != '\0')
    {
        int room = UI_W - 12 - (x + 10);
        int w = ui_text_width(value);
        if (w > room)
            ui_text_fit(&screen, x + 10, y + 4, value, room, UI_DIM);
        else
            ui_text(&screen, UI_W - 12 - w, y + 4, value, UI_DIM);
    }
}

void ui_scrollbar(int x, int y, int h, int first, int shown, int total)
{
    ui_fill(&screen, x, y, 4, h, UI_BAR);
    if (total <= shown || total <= 0)
        return;
    int th = h * shown / total;
    if (th < 8)
        th = 8;
    int ty = y + (h - th) * first / (total - shown);
    ui_fill(&screen, x, ty, 4, th, UI_SCROLL);
}

void ui_card(const char *title, const char *text, uint8_t accent, const UiKey *keys, int n)
{
    // On its own: a list's rows peeking out around it look misplaced
    ui_fill(&screen, 0, UI_BAR_H, UI_W, UI_FOOT_Y - UI_BAR_H, UI_BG);
    ui_card_at(-1, title, text, accent, keys, n);
}

void ui_card_at(int top, const char *title, const char *text, uint8_t accent, const UiKey *keys, int n)
{
    // Measured first (no canvas), then drawn; what was under it can't be
    // tapped anymore
    ui_touch_clear();
    int x = 10, w = UI_W - 20;
    int lines = text != NULL && text[0] != '\0' ? ui_text_wrap(NULL, 0, 0, text, w - 20, 12, UI_TEXT) : 0;
    int h = 28 + lines * UI_LINE;
    int y = top >= 0 ? top : (UI_BAR_H + UI_FOOT_Y - h) / 2;
    if (y < UI_TOP)
        y = UI_TOP;
    ui_panel(x, y, w, h, accent);
    ui_text_fit(&screen, x + 10, y + 9, title, w - 20, accent);
    if (lines > 0)
        ui_text_wrap(&screen, x + 10, y + 23, text, w - 20, lines, UI_SOFT);
    if (keys != NULL)
        ui_footer(keys, n);
    ui_present();
}

// ---------------------------------------------------------------------------
// Taps

void ui_touch_clear(void)
{
    n_hits = 0;
}

void ui_touch_add(int x, int y, int w, int h, int id)
{
    if (n_hits < MAX_HITS)
        hits[n_hits++] = (Hit){ x, y, w, h, id };
}

static int hit_test(const Hit *list, int n)
{
    if (!on || !(keysDown() & KEY_TOUCH))
        return -1;
    touchPosition t;
    touchRead(&t);
    for (int i = 0; i < n; i++)
    {
        const Hit *h = &list[i];
        if (t.px >= h->x && t.px < h->x + h->w && t.py >= h->y && t.py < h->y + h->h)
            return i;
    }
    return -1;
}

int ui_tapped(void)
{
    int i = hit_test(hits, n_hits);
    return i >= 0 ? hits[i].id : -1;
}

uint32_t ui_footer_key(void)
{
    int i = hit_test(footer, n_footer);
    return i >= 0 ? (uint32_t)footer[i].id : 0;
}

void ui_release(void)
{
    do
    {
        sync_frame();
        scanKeys();
    } while (keysHeld() & (KEY_A | KEY_B | KEY_X | KEY_Y | KEY_START | KEY_SELECT | KEY_L | KEY_R | KEY_TOUCH));
}

uint32_t ui_wait(uint32_t keys)
{
    while (1)
    {
        sync_frame();
        scanKeys();
        uint32_t down = keysDownRepeat() & keys;
        if (down)
            return down;
        uint32_t tap = ui_footer_key() & keys;
        if (tap)
            return tap;
    }
}

// ---------------------------------------------------------------------------
// Sounds

typedef struct
{
    uint16_t freq, start, len;   // Hz, ms, ms
} Note;

typedef struct
{
    const Note *notes;
    int n;
    uint8_t volume;
} SoundDef;

static const Note MOVE_NOTES[] = { { 1760, 0, 40 } };
static const Note SELECT_NOTES[] = { { 1319, 0, 60 }, { 1976, 40, 90 } };
static const Note BACK_NOTES[] = { { 1568, 0, 60 }, { 1047, 40, 90 } };
static const Note TOGGLE_NOTES[] = { { 2093, 0, 50 }, { 2637, 30, 70 } };
static const Note ERROR_NOTES[] = { { 311, 0, 110 }, { 262, 90, 160 } };
static const Note DONE_NOTES[] = { { 1047, 0, 140 }, { 1319, 80, 140 }, { 1568, 160, 160 }, { 2093, 240, 220 } };

static const SoundDef SOUNDS[SND_COUNT] = {
    [SND_MOVE] = { MOVE_NOTES, 1, 36 },
    [SND_SELECT] = { SELECT_NOTES, 2, 44 },
    [SND_BACK] = { BACK_NOTES, 2, 44 },
    [SND_TOGGLE] = { TOGGLE_NOTES, 2, 40 },
    [SND_ERROR] = { ERROR_NOTES, 2, 64 },
    [SND_DONE] = { DONE_NOTES, 4, 44 },
};

static int8_t *samples[SND_COUNT];
static uint32_t sample_len[SND_COUNT];
static bool sounds_on = true;

// A quarter of a sine wave, 100 at the top
static const int8_t QUARTER[65] = {
    0, 2, 5, 7, 10, 12, 15, 17, 20, 22, 24, 27, 29, 31, 34, 36, 38, 41, 43, 45, 47, 49,
    51, 53, 56, 58, 60, 62, 63, 65, 67, 69, 71, 72, 74, 76, 77, 79, 80, 82, 83, 84, 86,
    87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 96, 97, 98, 98, 99, 99, 99, 100, 100, 100,
    100, 100,
};

static void make_sounds(void)
{
    int8_t sine[256];
    for (int i = 0; i < 256; i++)
    {
        int q = i & 127;
        int v = QUARTER[q <= 64 ? q : 128 - q];
        sine[i] = (int8_t)(i < 128 ? v : -v);
    }

    for (int s = 0; s < SND_COUNT; s++)
    {
        const SoundDef *d = &SOUNDS[s];
        int ms = 0;
        for (int i = 0; i < d->n; i++)
        {
            if (d->notes[i].start + d->notes[i].len > ms)
                ms = d->notes[i].start + d->notes[i].len;
        }
        uint32_t len = ((uint32_t)SOUND_RATE * ms / 1000 + 3) & ~3u;
        int16_t *mix = calloc(len, sizeof(int16_t));
        int8_t *out = memalign(32, len);
        if (mix == NULL || out == NULL)
        {
            free(mix);
            free(out);
            continue;
        }
        for (int i = 0; i < d->n; i++)
        {
            const Note *n = &d->notes[i];
            uint32_t from = (uint32_t)SOUND_RATE * n->start / 1000;
            uint32_t count = (uint32_t)SOUND_RATE * n->len / 1000;
            uint32_t step = (uint32_t)(((uint64_t)n->freq << 32) / SOUND_RATE), phase = 0;
            // A quick rise (2 ms), then a fade that's almost silent by the end
            int32_t env = 0, attack = SOUND_RATE / 500;
            int32_t decay = 32768 - (int32_t)(5 * 32768 / (count ? count : 1));
            for (uint32_t t = 0; t < count && from + t < len; t++)
            {
                if (t < (uint32_t)attack)
                    env = (int32_t)(32767 * (t + 1) / attack);
                else
                    env = (env * decay) >> 15;
                mix[from + t] += (int16_t)((sine[phase >> 24] * env) >> 15);
                phase += step;
            }
        }
        for (uint32_t t = 0; t < len; t++)
            out[t] = (int8_t)(mix[t] > 127 ? 127 : mix[t] < -127 ? -127 : mix[t]);
        free(mix);
        DC_FlushRange(out, len);    // the ARM7 reads it from memory
        samples[s] = out;
        sample_len[s] = len;
    }
}

void ui_sounds(bool yes)
{
    sounds_on = yes;
}

void ui_sound(UiSound s)
{
    // On the channels the music leaves to the sounds, in turn
    static int next;
    if (!sounds_on || !on || s >= SND_COUNT || samples[s] == NULL)
        return;
    soundPlaySampleChannel(MUSIC_UI_FIRST_CHANNEL + next, samples[s], SoundFormat_8Bit, sample_len[s], SOUND_RATE,
                           SOUNDS[s].volume, 64, false, 0);
    next = (next + 1) & 3;
}

// ---------------------------------------------------------------------------
// The battery

int ui_battery(bool *charging)
{
    u32 v = getBatteryLevel();
    *charging = (v & BATTERY_CHARGER_CONNECTED) != 0;
    switch (v & BATTERY_LEVEL_MASK)
    {
    case 15: return 100;
    case 11: return 75;
    case 7:  return 50;
    case 3:  return 25;
    case 1:  return 10;
    case 0:  return 0;
    default: return (int)(v & BATTERY_LEVEL_MASK) * 100 / 15;
    }
}
