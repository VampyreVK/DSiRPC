// SPDX-License-Identifier: MIT
//
// The modern look's drawing (Look in the launcher's settings; the classic
// look is the text console, as it always was). The bottom screen becomes an
// 8-bit bitmap, drawn in memory and copied to the screen when it changes:
// panels, chips and key hints in the colors of the desktop app, text in the
// console's own 8x8 font, a few pixel icons and the games' banner icons. The
// top screen's modern panels (topscreen.c) draw with the same calls on a
// canvas of their own.
//
// It also has the modern look's soft menu sounds (Sounds in the settings),
// taps on the touch screen, and the battery level for the top screen.

#ifndef UI_H__
#define UI_H__

#include <stdbool.h>
#include <stdint.h>

#define UI_W        256
#define UI_H        192
#define UI_BAR_H    20          // the header bar, its edge included
#define UI_FOOT_Y   172         // the footer's top edge
#define UI_TOP      (UI_BAR_H + 4)     // where the content starts
#define UI_LINE     10          // a line of text

// Something to draw on: w x h palette entries
typedef struct
{
    uint8_t *px;
    int w, h;
    int dirty_top, dirty_bottom;    // rows changed since the last copy
} Canvas;

// The bottom screen's palette entries (0 is clear: the backdrop shows)
enum
{
    UI_CLEAR,
    UI_BG,                      // the screen
    UI_BAR, UI_EDGE,            // the header and footer, and borders
    UI_PANEL, UI_PANEL_HI, UI_PANEL_LO,
    UI_CHIP,                    // a chip's fill, an unselected button's
    UI_TEXT, UI_DIM, UI_SOFT,
    UI_GREEN, UI_GREEN_DARK,    // the dark ones are text on the bright ones
    UI_CYAN, UI_CYAN_DARK,
    UI_AMBER, UI_AMBER_DARK,
    UI_RED, UI_RED_DARK,
    UI_SCROLL,                  // the scroll bar's thumb
    UI_ICON,                    // icon grey
    UI_SLATE, UI_SKY,           // the Games icon's card and screen
    UI_SPIN,                    // 8: the spinner's dots, lit in turn
    UI_COLORS = UI_SPIN + 8,
    UI_BANNERS = 48,            // the banner icons' palettes, 16 entries each
};
#define UI_BANNER_SLOTS  12

// The steps on the connecting screen
typedef enum
{
    STEP_WAITING,               // not started: a grey box
    STEP_ACTIVE,                // the spinner
    STEP_DONE,                  // a green check
    STEP_FAILED,                // a red cross
    STEP_SKIPPED,               // a grey dash
} StepState;

// The menu sounds
typedef enum
{
    SND_MOVE,                   // the selection moved
    SND_SELECT,                 // A
    SND_BACK,                   // B
    SND_TOGGLE,                 // a setting changed, a favorite
    SND_ERROR,                  // can't do that
    SND_DONE,                   // finished (a sync, an update)
    SND_COUNT,
} UiSound;

// A key hint in the footer: the key's cap ("A"), what it does ("Open"), and
// the key a tap on it presses (0: none)
typedef struct
{
    const char *cap;
    const char *label;
    uint32_t key;
} UiKey;

// A game's banner icon (the .nds file's 32x32, 16 colors)
typedef struct
{
    uint8_t px[32 * 32];        // color indexes, 0 clear
    uint16_t pal[16];           // BGR555
    bool ok;
} UiBanner;

// ---------------------------------------------------------------------------
// The bottom screen

// Once, after consoleDemoInit(): sets the bitmap up and starts the sounds
// (shown only after ui_enter()).
void ui_init(void);

// Shows the bitmap (the modern look) or the text console again (the
// classic look). The console is set up afresh when it comes back.
void ui_enter(void);
void ui_leave(void);
bool ui_on(void);

Canvas *ui_screen(void);
void ui_clear(void);            // the whole screen in UI_BG
void ui_present(void);          // copies the rows that changed to the screen

// ---------------------------------------------------------------------------
// Drawing, on any canvas

void ui_fill(Canvas *c, int x, int y, int w, int h, uint8_t color);
void ui_frame(Canvas *c, int x, int y, int w, int h, int t, uint8_t color);
// A filled box with its corners cut (r pixels)
void ui_round(Canvas *c, int x, int y, int w, int h, int r, uint8_t color);

// Text (UTF-8) in the console's font, each letter as wide as it is. Returns
// the x after it. Letters outside ASCII are drawn as their nearest ASCII
// ones (ui_ascii()), and the console's color codes are skipped.
int ui_text(Canvas *c, int x, int y, const char *s, uint8_t color);
char ui_ascii(uint32_t codepoint);
int ui_text_width(const char *s);
// Cut with "..." to max_w pixels if it's wider
int ui_text_fit(Canvas *c, int x, int y, const char *s, int max_w, uint8_t color);
void ui_text_right(Canvas *c, int right, int y, const char *s, uint8_t color);
void ui_text_center(Canvas *c, int cx, int y, const char *s, uint8_t color);
// With a shadow a pixel down and right
void ui_text_shadow(Canvas *c, int x, int y, const char *s, uint8_t color, uint8_t shadow);
// Wrapped to max_w, on up to max_lines lines; returns the lines used (with
// no canvas, only counts them)
int ui_text_wrap(Canvas *c, int x, int y, const char *s, int max_w, int max_lines, uint8_t color);

// Pixel art: rows of characters, '.' clear, '1'-'4' colors[0]-colors[3]
void ui_art(Canvas *c, int x, int y, const char *const *rows, int h, const uint8_t colors[4]);

// A chip: text on a filled box. Returns its width.
int ui_chip(Canvas *c, int x, int y, const char *text, uint8_t fill, uint8_t ink);
int ui_chip_width(const char *text);

// A progress bar, pct of it filled
void ui_bar(Canvas *c, int x, int y, int w, int h, int pct, uint8_t fill);

// A banner icon at full size (scale 1) or twice it (2), its colors from
// palette entry first on (15 of them); half: every other pixel, 16x16
void ui_banner(Canvas *c, int x, int y, const UiBanner *b, int scale, uint8_t first);
void ui_banner_half(Canvas *c, int x, int y, const UiBanner *b, uint8_t first);
// Loads a banner icon's colors into the bottom screen's slot (0 to
// UI_BANNER_SLOTS - 1); returns the palette entry to draw it with
uint8_t ui_banner_slot(int slot, const UiBanner *b);

// ---------------------------------------------------------------------------
// The bottom screen's parts

// The header: a title on the left (in UI_SOFT)
void ui_header(const char *title);
// Text at the header's right end (returns its left x)
int ui_header_right(const char *text, uint8_t color);
// Key hints along the bottom (taps on them count as their keys)
void ui_footer(const UiKey *keys, int n);
// A key's cap ("A", "START") at x, y (12 high); returns the x after it
int ui_key_cap(Canvas *c, int x, int y, const char *cap);
// A raised panel with a border
void ui_panel(int x, int y, int w, int h, uint8_t border);
// The connecting screen's steps (row 0 at the top)
void ui_step(int row, StepState state, const char *label, const char *value);
// A scroll bar at the right edge: first..first+shown of total
void ui_scrollbar(int x, int y, int h, int first, int shown, int total);
// The spinner (12x12)
void ui_spinner(Canvas *c, int x, int y);
// The spinner's dots lit for one step of its turn (its cothread moves it on
// every few frames)
void ui_spin_frame(unsigned step);
// A step's icon (12x12) on any canvas, in these colors: an empty box, the
// spinner, a check, a cross or a dash
void ui_icon(Canvas *c, int x, int y, StepState state, uint8_t box, uint8_t mark);

// A card in the middle of the screen with a title and text (lines split at
// '\n'), and the footer's keys; drawn and presented, nothing waited for.
// What was between the header and the footer is cleared first.
// ui_card_at(): its top at y instead, over what's there.
void ui_card(const char *title, const char *text, uint8_t accent, const UiKey *keys, int n);
void ui_card_at(int y, const char *title, const char *text, uint8_t accent, const UiKey *keys, int n);

// ---------------------------------------------------------------------------
// Taps, sounds, the battery

// The screens say where they can be tapped; ui_tapped() is the id of the
// one tapped since the last scanKeys() (the pen going down), or -1.
void ui_touch_clear(void);
void ui_touch_add(int x, int y, int w, int h, int id);
int ui_tapped(void);
// The key the footer's hint under the pen stands for, or 0
uint32_t ui_footer_key(void);
// Waits a frame at a time (telling DSiRPC the launcher's still there) for
// one of keys, pressed or repeating, or a tap on a footer hint for one
void ui_release(void);          // first, until no button is held
uint32_t ui_wait(uint32_t keys);

void ui_sounds(bool on);
void ui_sound(UiSound s);

// The battery in percent (the DSi reports it in steps, a DS only high or
// low), and whether the charger is in
int ui_battery(bool *charging);

#endif // UI_H__
