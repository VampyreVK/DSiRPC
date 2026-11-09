// dsirpc_skin.c - DSiRPC's look for nds-bootstrap's in-game menu: the teal
// diamonds of DSiRPC's banner drifting behind slate panels with rounded
// corners, a title bar and a footer, an amber highlight that glows, icons,
// a progress bar, and text with a drop shadow. The colors are the launcher's
// (launcher/source/ui.c), and the title bar's and footer's edges and the
// battery are its top screen's (launcher/source/topscreen.c).
//
// It's all tiles in VRAM H, which the menu already maps to the sub screen's
// backgrounds and backs up (with the maps and the palette) while it's open:
// the font's 256 tiles, then this file's (SKIN_TILE0 on). The art is in this
// file, as rows of palette indexes (SKIN_PAL below), one hex digit a pixel,
// left to right; the icons get their shadow when they're loaded. Not in B4DS
// builds, whose menu keeps upstream's look.

#ifndef B4DS

#include <nds/ndstypes.h>
#include <nds/system.h>
#include <nds/arm9/background.h>
#include <nds/arm9/video.h>
#include "igm_text.h"
#include "inGameMenu.h"
#include "dsirpc_skin.h"

void mySwiDelay(int delay);

// -- the art ---------------------------------------------------------------

// A row of 8 pixels written left to right (0x01F33333), the way the DS reads
// it (the leftmost pixel in the low 4 bits)
#define P(v) PX((u32)(v))
#define PX(v) ((((v) >> 28) & 0xFu) | (((v) >> 20) & 0xF0u) | (((v) >> 12) & 0xF00u) | (((v) >> 4) & 0xF000u) | \
               (((v) << 4) & 0xF0000u) | (((v) << 12) & 0xF00000u) | (((v) << 20) & 0xF000000u) | (((v) << 28) & 0xF0000000u))

#define RGB(r, g, b) ((u16)(((r) >> 3) | (((g) >> 3) << 5) | (((b) >> 3) << 10)))

// SKIN_PAL, palette row 8 (row 9: the same with 9 green, for green icons;
// row 10: 9 glowing, for the highlight)
//   0 clear   1 outline   2 bar      3 panel    4 highlight  5 panel's dark
//   6 teal    7 diamond   8 its core 9 amber    A green      B cyan
//   C red     D white     E slate    F panel's light edge
#define SKIN_PAL      8
#define SKIN_PAL_ALT  9
#define SKIN_PAL_GLOW 10
// Row 11: the bars' edges and the battery, with 1 the launcher's dark edge
// (ui.c's UI_EDGE: the bars' own dark is the same as 1 on the DS) and E and
// F its top screen's (its battery's outline, its bar's light edge). Rows 12 and 13:
// 9 red and 9 gray, for the Wi-Fi sign (SKIN_ICON_RED, SKIN_ICON_GRAY).
#define SKIN_PAL_BAR  11
#define SKIN_PAL_LAST 13
static const u16 skinPal[16] = {
	RGB(0, 0, 0),       RGB(16, 24, 32),    RGB(20, 28, 38),    RGB(38, 54, 74),
	RGB(60, 96, 132),   RGB(28, 40, 56),    RGB(40, 104, 112),  RGB(52, 122, 130),
	RGB(70, 142, 148),  RGB(240, 192, 48),  RGB(88, 208, 128),  RGB(72, 200, 232),
	RGB(232, 72, 56),   RGB(232, 238, 247), RGB(129, 148, 174), RGB(74, 106, 142),
};
#define BAR_EDGE  RGB(14, 20, 27)
#define BAR_LINES RGB(201, 208, 220)
#define BAR_HI    RGB(66, 90, 102)
#define WIFI_GRAY RGB(94, 107, 132)
// The diamonds when the menu shows an exception
static const u16 skinPalRed[3] = { RGB(90, 28, 28), RGB(112, 40, 40), RGB(138, 58, 58) };
// The text's colors (FontPalette, then FONT_AMBER), each with a dark shadow
static const u16 skinText[7] = {
	RGB(232, 238, 247), RGB(197, 209, 227), RGB(122, 136, 162), RGB(72, 200, 232),
	RGB(232, 72, 56),   RGB(88, 208, 128),  RGB(240, 192, 48),
};
#define SHADOW RGB(16, 24, 32)
// The highlight's glow: amber to pale gold and back
#define GLOW_R0 240
#define GLOW_G0 192
#define GLOW_B0 48
#define GLOW_R1 255
#define GLOW_G1 236
#define GLOW_B1 150

// The tiles, from SKIN_TILE0
enum {
	T_DIAMOND,                  // 4: the diamonds' 16x16, drawn by skinDiamonds()
	T_PANEL_TL = T_DIAMOND + 4, // the art below, in this order
	T_PANEL_T, T_PANEL_TR, T_PANEL_L, T_PANEL_R, T_PANEL_BL, T_PANEL_B, T_PANEL_BR,
	T_SELECT_L, T_SELECT_R, T_SELECT_PIP, T_HEADER_EDGE, T_FOOTER_EDGE, T_RULE, T_SHEET_T,
	T_SOLID,                    // 4: tones 0-3 (Skin_Fill)
	T_ICON = T_SOLID + 4,       // the icons
	T_BAR = T_ICON + SKIN_ICON_COUNT, // 5: the progress bar's, drawn by Skin_Progress()
	T_BATTERY = T_BAR + 5,      // 3: the battery's two and the bolt, drawn by Skin_Battery()
	T_SPLIT = T_BATTERY + 3,    // 2 a slot: Skin_SplitRow()'s first column and the rest
	T_COUNT = T_SPLIT + SKIN_SPLIT_SLOTS * 2
};
_Static_assert(T_COUNT <= SKIN_TILE_COUNT, "dsirpc_skin.h: SKIN_TILE_COUNT is too small");

static const u8 solidTone[4] = { 2, 3, 4, 5 };

#define ART_TILES (T_SOLID - T_PANEL_TL)
static const u32 artChrome[ART_TILES][8] = {
	{ // panel, top left
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000),
		P(0x00000000), P(0x00011111), P(0x001FFFFF), P(0x01F33333) },
	{ // top
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000),
		P(0x00000000), P(0x11111111), P(0xFFFFFFFF), P(0x33333333) },
	{ // top right
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000),
		P(0x00000000), P(0x11111000), P(0xFFFFF100), P(0x33333510) },
	{ // left
		P(0x01F33333), P(0x01F33333), P(0x01F33333), P(0x01F33333),
		P(0x01F33333), P(0x01F33333), P(0x01F33333), P(0x01F33333) },
	{ // right
		P(0x33333510), P(0x33333510), P(0x33333510), P(0x33333510),
		P(0x33333510), P(0x33333510), P(0x33333510), P(0x33333510) },
	{ // bottom left
		P(0x01F33333), P(0x00155555), P(0x00011111), P(0x00000000),
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000) },
	{ // bottom
		P(0x33333333), P(0x55555555), P(0x11111111), P(0x00000000),
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000) },
	{ // bottom right
		P(0x33333510), P(0x55555100), P(0x11111000), P(0x00000000),
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000) },
	{ // highlight, left (its 9s glow)
		P(0x01F44444), P(0x01F49944), P(0x01F49994), P(0x01F49999),
		P(0x01F49999), P(0x01F49994), P(0x01F49944), P(0x01F44444) },
	{ // highlight, right
		P(0x44444510), P(0x44444510), P(0x44444510), P(0x44444510),
		P(0x44444510), P(0x44444510), P(0x44444510), P(0x44444510) },
	{ // highlight in a list, first column (its 9s glow)
		P(0x99444444), P(0x99444444), P(0x99444444), P(0x99444444),
		P(0x99444444), P(0x99444444), P(0x99444444), P(0x99444444) },
	{ // the title bar's last row (SKIN_PAL_BAR): 2 more pixels of it, then its
	  // edge, dark, then light against the diamonds
		P(0x22222222), P(0x22222222), P(0x11111111), P(0xFFFFFFFF),
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000) },
	{ // over the footer (SKIN_PAL_BAR): its edge, light against the diamonds,
	  // then dark, then 2 pixels of it
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000),
		P(0xFFFFFFFF), P(0x11111111), P(0x22222222), P(0x22222222) },
	{ // a rule
		P(0x22222222), P(0x22222222), P(0x22222222), P(0xFFFFFFFF),
		P(0x11111111), P(0x22222222), P(0x22222222), P(0x22222222) },
	{ // a sheet's top
		P(0x00000000), P(0x00000000), P(0x00000000), P(0x00000000),
		P(0x00000000), P(0x11111111), P(0xFFFFFFFF), P(0x33333333) },
};

static const u32 artIcons[SKIN_ICON_COUNT][8] = {
	{ // logo: DSiRPC's Wi-Fi sign, all in 9 so the link's color (SKIN_ICON_*) is all of it
		P(0x00999900), P(0x09000090), P(0x90099009), P(0x00900900),
		P(0x00000000), P(0x00099000), P(0x00099000), P(0x00000000) },
	{ // back to the game
		P(0x00A00000), P(0x00AA0000), P(0x00AAA000), P(0x00AAAA00),
		P(0x00AAA000), P(0x00AA0000), P(0x00A00000), P(0x00000000) },
	{ // achievements
		P(0x09999990), P(0x99D99999), P(0x90999909), P(0x09999990),
		P(0x00999900), P(0x00099000), P(0x00099000), P(0x00999900) },
	{ // reset (a row shorter than the rest, clear of the trophy above it)
		P(0x00000000), P(0x00BBB0B0), P(0x0B000BB0), P(0xB000BBB0),
		P(0xB00000B0), P(0x0B000B00), P(0x00BBB000), P(0x00000000) },
	{ // screenshot
		P(0x00000000), P(0x0DD00000), P(0xDDDDDDD0), P(0xDDBBBDD0),
		P(0xDDB1BDD0), P(0xDDBBBDD0), P(0xDDDDDDD0), P(0x00000000) },
	{ // manual
		P(0x0DDDD000), P(0x0DEEDD00), P(0x0DDDDDD0), P(0x0DEEEED0),
		P(0x0DDDDDD0), P(0x0DEEEED0), P(0x0DDDDDD0), P(0x00000000) },
	{ // RAM dump: an arrow down
		P(0x000BB000), P(0x000BB000), P(0x000BB000), P(0x000BB000),
		P(0x0BBBBBB0), P(0x00BBBB00), P(0x000BB000), P(0x00000000) },
	{ // options
		P(0x0E0E0E00), P(0xEEEEEEE0), P(0x0EE0EE00), P(0xEE000EE0),
		P(0x0EE0EE00), P(0xEEEEEEE0), P(0x0E0E0E00), P(0x00000000) },
	{ // RAM viewer
		P(0x00DDD000), P(0x0D000D00), P(0x0D0B0D00), P(0x0D000D00),
		P(0x00DDDD00), P(0x00000990), P(0x00000099), P(0x00000000) },
	{ // quit
		P(0x000CC000), P(0x0C0CC0C0), P(0xC00CC00C), P(0xC000000C),
		P(0xC000000C), P(0x0C0000C0), P(0x00CCCC00), P(0x00000000) },
	{ // a locked achievement
		P(0x00EEE000), P(0x0E000E00), P(0x0E000E00), P(0xEEEEEEE0),
		P(0xEEE1EEE0), P(0xEEE1EEE0), P(0xEEEEEEE0), P(0x00000000) },
	{ // a star
		P(0x00090000), P(0x00999000), P(0x999D9990), P(0x09999900),
		P(0x00999000), P(0x09909900), P(0x09000900), P(0x00000000) },
};

// -- drawing ---------------------------------------------------------------

#define UI_MAP   BG_MAP_RAM_SUB(SKIN_UI_MAP)
#define TEXT_MAP BG_MAP_RAM_SUB(15)
#define ENTRY(t, pal) ((u16)((SKIN_TILE0 + (t)) | ((pal) << 12)))

static int skinOn;
static u16 lastLine;
static u8 frame, drift;

static vu32 *tileAt(int t) {
	return (vu32 *)((u8 *)BG_GFX_SUB + (SKIN_TILE0 + t) * 32);
}

static void waitFrame(void) {
	while (REG_VCOUNT != 191) mySwiDelay(100);
	while (REG_VCOUNT == 191) mySwiDelay(100);
}

// The diamonds' 16x16 (2x2 tiles), moved right and down by `shift` pixels:
// teal, with a diamond in the middle of rows 4 to 11
static void skinDiamonds(int shift) {
	for (int t = 0; t < 4; t++) {
		vu32 *dst = tileAt(T_DIAMOND + t);
		for (int y = 0; y < 8; y++) {
			int py = ((t >> 1) * 8 + y - shift) & 15;
			int half = (py <= 7) ? py - 4 : 11 - py; // the diamond's half width (< 0: none)
			u32 row = 0;
			for (int x = 7; x >= 0; x--) {
				int px = ((t & 1) * 8 + x - shift) & 15;
				int dx = (px < 8) ? 8 - px : px - 8;
				u32 c = (half >= 0 && dx <= half) ? ((px == 8 && py == 7) ? 8 : 7) : 6;
				row = (row << 4) | c;
			}
			dst[y] = row;
		}
	}
}

// Each frame: the highlight glows, and every 7th the diamonds move a pixel
// (16 pixels in 1.9 s, as on the banner)
static void skinTick(void) {
	frame++;
	int k = frame & 31;
	int tri = (k < 16) ? k : 31 - k;
	BG_PALETTE_SUB[SKIN_PAL_GLOW * 16 + 9] = RGB(GLOW_R0 + (GLOW_R1 - GLOW_R0) * tri / 15,
	                                             GLOW_G0 + (GLOW_G1 - GLOW_G0) * tri / 15,
	                                             GLOW_B0 + (GLOW_B1 - GLOW_B0) * tri / 15);
	if (frame % 7 == 0) {
		drift = (drift + 1) & 15;
		skinDiamonds(drift);
	}
}

void Skin_Poll(void) {
	if (!skinOn) return;
	u16 line = REG_VCOUNT;
	if (line >= 192 && lastLine < 192) skinTick(); // the VBlank started
	lastLine = line;
}

// The font from 1 bit a pixel to 4: index 1 the glyph, index 2 its shadow
// (a pixel down and right)
static void skinFont(void) {
	vu32 *dst = (vu32 *)BG_GFX_SUB;
	const u8 *src = igmText.font;
	for (int g = 0; g < 256; g++) {
		u32 above = 0;
		for (int y = 0; y < 8; y++) {
			u32 cur = *src++;
			u32 shade = (above << 1) & ~cur & 0xFF;
			u32 row = 0;
			for (int x = 7; x >= 0; x--) {
				row = (row << 4) | (((cur >> x) & 1) ? 1 : ((shade >> x) & 1) ? 2 : 0);
			}
			*dst++ = row;
			above = cur;
		}
	}
}

void Skin_Open(int exception) {
	// The palettes: the text's rows (0-6) and the skin's (8-10)
	for (int i = 0; i < 7; i++) {
		BG_PALETTE_SUB[i * 16 + 1] = skinText[i];
		BG_PALETTE_SUB[i * 16 + 2] = SHADOW;
	}
	for (int r = SKIN_PAL; r <= SKIN_PAL_LAST; r++) {
		for (int i = 0; i < 16; i++) BG_PALETTE_SUB[r * 16 + i] = skinPal[i];
		if (exception) {
			for (int i = 0; i < 3; i++) BG_PALETTE_SUB[r * 16 + 6 + i] = skinPalRed[i];
		}
	}
	BG_PALETTE_SUB[SKIN_PAL_ALT * 16 + 9] = skinPal[0xA];
	BG_PALETTE_SUB[SKIN_PAL_BAR * 16 + 1] = BAR_EDGE;
	BG_PALETTE_SUB[SKIN_PAL_BAR * 16 + 0xE] = BAR_LINES;
	BG_PALETTE_SUB[SKIN_PAL_BAR * 16 + 0xF] = BAR_HI;
	BG_PALETTE_SUB[(SKIN_PAL_BAR + 1) * 16 + 9] = skinPal[0xC];
	BG_PALETTE_SUB[(SKIN_PAL_BAR + 2) * 16 + 9] = WIFI_GRAY;
	BG_PALETTE_SUB[0] = BG_PALETTE_SUB[SKIN_PAL * 16 + 6];

	// The tiles
	skinFont();
	skinDiamonds(drift);
	for (int t = 0; t < ART_TILES; t++) {
		vu32 *dst = tileAt(T_PANEL_TL + t);
		for (int y = 0; y < 8; y++) dst[y] = artChrome[t][y];
	}
	for (int t = 0; t < 4; t++) {
		vu32 *dst = tileAt(T_SOLID + t);
		for (int y = 0; y < 8; y++) dst[y] = solidTone[t] * 0x11111111u;
	}
	for (int t = 0; t < SKIN_ICON_COUNT; t++) { // with a shadow, a pixel down and right
		vu32 *dst = tileAt(T_ICON + t);
		u32 above = 0;
		for (int y = 0; y < 8; y++) {
			u32 cur = artIcons[t][y], row = cur;
			for (int x = 1; x < 8; x++) {
				if (!((cur >> (x * 4)) & 0xF) && ((above >> ((x - 1) * 4)) & 0xF)) row |= 1u << (x * 4);
			}
			dst[y] = row;
			above = cur;
		}
	}

	// BG1: the diamonds, all over its map, so its scroll doesn't matter.
	// BG2: nothing yet, under BG3's text.
	u16 *map = BG_MAP_RAM_SUB(SKIN_BG_MAP);
	for (int i = 0; i < 32 * 32; i++) {
		map[i] = ENTRY(T_DIAMOND + ((i >> 5) & 1) * 2 + (i & 1), SKIN_PAL);
	}
	Skin_Clear();
	REG_BG1CNT_SUB = (u16)(BG_MAP_BASE(SKIN_BG_MAP) | BG_TILE_BASE(0) | BgSize_T_256x256 | BG_PRIORITY(2));
	REG_BG2CNT_SUB = (u16)(BG_MAP_BASE(SKIN_UI_MAP) | BG_TILE_BASE(0) | BgSize_T_256x256 | BG_PRIORITY(1));
	REG_BG2HOFS_SUB = 0; // write only, like BG3's: left at 0 when the menu closes
	REG_BG2VOFS_SUB = 0;
	REG_DISPCNT_SUB = MODE_0_2D | DISPLAY_BG1_ACTIVE | DISPLAY_BG2_ACTIVE | DISPLAY_BG3_ACTIVE;

	SetBrightness(1, -16); // dark until Skin_FadeIn()
	lastLine = REG_VCOUNT;
	skinOn = 1;
}

void Skin_Close(void) {
	skinOn = 0;
}

void Skin_FadeIn(void) {
	for (int b = -14; b < 0; b += 2) {
		waitFrame();
		SetBrightness(1, b);
	}
	waitFrame();
	SetBrightness(1, 0);
}

void Skin_Clear(void) {
	u16 *map = UI_MAP;
	for (int i = 0; i < 32 * 24; i++) map[i] = 0;
}

static void skinRow(int y, int x, int w, int left, int mid, int right, int pal) {
	u16 *row = UI_MAP + y * 32;
	row[x] = ENTRY(left, pal);
	for (int i = x + 1; i < x + w - 1; i++) row[i] = ENTRY(mid, SKIN_PAL);
	row[x + w - 1] = ENTRY(right, SKIN_PAL);
}

static void skinLine(int y, int t) {
	skinRow(y, 0, 32, t, t, t, SKIN_PAL);
}

// A bar's edge: in SKIN_PAL_BAR, for its light line
static void skinEdge(int y, int t) {
	u16 *row = UI_MAP + y * 32;
	for (int i = 0; i < 32; i++) row[i] = ENTRY(t, SKIN_PAL_BAR);
}

void Skin_Panel(int x, int y, int w, int h) {
	skinRow(y, x, w, T_PANEL_TL, T_PANEL_T, T_PANEL_TR, SKIN_PAL);
	for (int r = y + 1; r < y + h - 1; r++) skinRow(r, x, w, T_PANEL_L, T_SOLID + 1, T_PANEL_R, SKIN_PAL);
	skinRow(y + h - 1, x, w, T_PANEL_BL, T_PANEL_B, T_PANEL_BR, SKIN_PAL);
}

void Skin_Sheet(int y, int h) {
	skinLine(y, T_SHEET_T);
	int last = y + h - 1;
	for (int r = y + 1; r < last; r++) skinLine(r, T_SOLID + 1);
	skinLine(last, (last == 23) ? T_SOLID + 1 : T_PANEL_B); // no edge at the screen's bottom
}

void Skin_Select(int x, int y, int w) {
	skinRow(y, x, w, T_SELECT_L, T_SOLID + 2, T_SELECT_R, SKIN_PAL_GLOW);
}

void Skin_SelectRows(int y, int h) {
	for (int r = y; r < y + h; r++) {
		u16 *row = UI_MAP + r * 32;
		row[0] = ENTRY(T_SELECT_PIP, SKIN_PAL_GLOW);
		for (int i = 1; i < 32; i++) row[i] = ENTRY(T_SOLID + 2, SKIN_PAL);
	}
}

void Skin_Header(int edge) {
	skinLine(0, T_SOLID);
	if (edge) {
		skinLine(1, T_SOLID);
		skinEdge(2, T_HEADER_EDGE);
	}
}

void Skin_Footer(int y) {
	skinEdge(y, T_FOOTER_EDGE);
	for (int r = y + 1; r < 24; r++) skinLine(r, T_SOLID);
}

void Skin_Fill(int y, int h, int tone) {
	for (int r = y; r < y + h; r++) skinLine(r, T_SOLID + tone);
}

void Skin_Rule(int y) {
	skinLine(y, T_RULE);
}

void Skin_Icon(int x, int y, int icon) {
	TEXT_MAP[y * 32 + x] = ENTRY(T_ICON + (icon & 0xFF), SKIN_PAL + (icon >> 8));
}

// Pixel x of row y of a tile, palette index c
static void skinPixel(int t, int x, int y, u32 c) {
	vu32 *dst = tileAt(t) + y;
	*dst = (*dst & ~(0xFu << (x * 4))) | (c << (x * 4));
}

void Skin_SplitRow(int y, int slot, int up, int down, int pip) {
	int t = T_SPLIT + slot * 2;
	for (int r = 0; r < 8; r++) {
		u32 c = solidTone[(r < 4) ? up : down];
		u32 row = c * 0x11111111u;
		tileAt(t + 1)[r] = row;
		if (pip == ((r < 4) ? 1 : 2)) row = (row & ~0xFFu) | 0x99u; // its first 2 pixels glow
		tileAt(t)[r] = row;
	}
	u16 *map = UI_MAP + y * 32;
	map[0] = ENTRY(t, SKIN_PAL_GLOW);
	for (int i = 1; i < 32; i++) map[i] = ENTRY(t + 1, SKIN_PAL);
}

void Skin_Battery(int x, int y, int level, int charging) {
	// The launcher's: 14x8 with its tip on the right, outlined in E, its
	// level (8 pixels at most) in A, 9 at 25% or less, C at 10% or less, or
	// B while charging, and a bolt (9) left of it while charging
	static const u8 bolt[8] = { 0x1, 0x3, 0x6, 0xF, 0xF, 0x6, 0xC, 0x8 }; // bit 3 the left pixel
	u32 fill = charging ? 0xB : (level <= 10) ? 0xC : (level <= 25) ? 9 : 0xA;
	int w = (level * 8 + 99) / 100;
	for (int r = 0; r < 8; r++) {
		tileAt(T_BATTERY)[r] = tileAt(T_BATTERY + 1)[r] = tileAt(T_BATTERY + 2)[r] = 0;
		for (int px = 0; px < 14; px++) {
			u32 c = 0;
			if (px < 12 && (r == 0 || r == 7 || px == 0 || px == 11)) c = 0xE;
			else if (px >= 12 && r >= 2 && r <= 5) c = 0xE;
			else if (px >= 2 && px < 2 + w && r >= 2 && r <= 5) c = fill;
			skinPixel(T_BATTERY + (px + 1) / 8, (px + 1) & 7, r, c);
		}
		if (charging) {
			for (int px = 0; px < 4; px++) {
				if ((bolt[r] >> (3 - px)) & 1) skinPixel(T_BATTERY + 2, 3 + px, r, 9);
			}
		}
	}
	u16 *row = TEXT_MAP + y * 32 + x;
	row[0] = charging ? ENTRY(T_BATTERY + 2, SKIN_PAL_BAR) : 0;
	row[1] = ENTRY(T_BATTERY, SKIN_PAL_BAR);
	row[2] = ENTRY(T_BATTERY + 1, SKIN_PAL_BAR);
}

// A tile of the progress bar, `fill` pixels of it green; its first column
// is the bar's left end if left, its last the right end if right
static void skinBarTile(int t, int fill, int left, int right) {
	vu32 *dst = tileAt(T_BAR + t);
	for (int y = 0; y < 8; y++) {
		u32 row = 0;
		for (int x = 7; x >= 0; x--) {
			int end = (left && x == 0) || (right && x == 7);
			u32 c = 0;
			if (y == 1 || y == 6) c = end ? 0 : 1;
			else if (y >= 2 && y <= 5) c = end ? 1 : (x < fill) ? 0xA : 5;
			row = (row << 4) | c;
		}
		dst[y] = row;
	}
}

void Skin_Progress(int x, int y, int w, u32 num, u32 den) {
	if (w < 2) return;
	int full = den ? (int)((num * (u32)(w * 8)) / den) : 0;
	if (num && !full) full = 2; // something earned shows
	int part = 0;
	for (int i = 1; i < w - 1; i++) {
		int f = full - i * 8;
		if (f > 0 && f < 8) part = f;
	}
	int first = full > 8 ? 8 : full, last = full - (w - 1) * 8;
	if (last < 0) last = 0;
	skinBarTile(0, first, 1, 0);
	skinBarTile(1, 8, 0, 0);
	skinBarTile(2, 0, 0, 0);
	skinBarTile(3, part, 0, 0);
	skinBarTile(4, last, 0, 1);
	u16 *row = TEXT_MAP + y * 32 + x;
	for (int i = 0; i < w; i++) {
		int f = full - i * 8, t;
		if (i == 0) t = 0;
		else if (i == w - 1) t = 4;
		else t = (f >= 8) ? 1 : (f <= 0) ? 2 : 3;
		row[i] = ENTRY(T_BAR + t, SKIN_PAL);
	}
}

#endif // B4DS
