// dsirpc_skin.h - DSiRPC's look for nds-bootstrap's in-game menu. See
// dsirpc_skin.c. Not in B4DS builds.

#ifndef DSIRPC_SKIN_H
#define DSIRPC_SKIN_H

#include <nds/ndstypes.h>

// The sub screen's three backgrounds while the menu is open, all in VRAM H
// (32 KB) with their tiles from 0 (the font's 256, then the skin's):
//   BG1, map 13: the drifting diamonds, as on DSiRPC's banner
//   BG2, map 14: panels and bars
//   BG3, map 15: the text, and the icons
#define SKIN_BG_MAP      13
#define SKIN_UI_MAP      14
#define SKIN_TILE0       256 // the skin's first tile, after the font's
#define SKIN_TILE_COUNT  40
// What the menu backs up of VRAM H when it opens, and puts back when it
// closes: the tiles it overwrites, and maps 13 to 15 (the rows it uses)
#define SKIN_VRAM_TILE_BYTES ((SKIN_TILE0 + SKIN_TILE_COUNT) * 32)
#define SKIN_VRAM_MAP_BYTES  (0x800 * 2 + 0x600)

// Text in amber, as well as inGameMenu.h's FontPalette colors
#define FONT_AMBER 6

// The icons (Skin_Icon)
enum {
	SKIN_ICON_LOGO,
	SKIN_ICON_PLAY,
	SKIN_ICON_TROPHY,
	SKIN_ICON_RESET,
	SKIN_ICON_CAMERA,
	SKIN_ICON_PAGE,
	SKIN_ICON_DUMP,
	SKIN_ICON_GEAR,
	SKIN_ICON_LENS,
	SKIN_ICON_POWER,
	SKIN_ICON_LOCK,
	SKIN_ICON_STAR,
	SKIN_ICON_COUNT
};
#define SKIN_ICON_GREEN 0x100 // or'd into an icon: amber drawn in green

// When the menu opens, after it has backed up VRAM H and the palette and set
// up BG3: the skin's tiles, palettes and the font (with a shadow), BG1 and
// BG2, and the screen dark for Skin_FadeIn(). exception: red diamonds.
void Skin_Open(int exception);
// Before the menu closes: no more animating
void Skin_Close(void);
// Once the first screen is drawn: brightens the screen from dark
void Skin_FadeIn(void);
// From every wait for the screen: animates the diamonds and the highlight
void Skin_Poll(void);

// BG2: nothing over the diamonds (with the text's clearScreen())
void Skin_Clear(void);
// BG2: a rounded panel over columns x to x + w - 1 and rows y to y + h - 1;
// its first and last rows are its edges, the rows between hold the text
void Skin_Panel(int x, int y, int w, int h);
// BG2: a panel as wide as the screen, rows y to y + h - 1 (edges included)
void Skin_Sheet(int y, int h);
// BG2: the highlight on row y of the panel over columns x to x + w - 1
void Skin_Select(int x, int y, int w);
// BG2: the title bar: row 0 only, or (edge) rows 0 to 2 with its edge at
// the bottom, for a title on row 1
void Skin_Header(int edge);
// BG2: the bar on rows y + 1 to 23, its edge on row y
void Skin_Footer(int y);
// BG2: rows y to y + h - 1 filled; tone 0 the bars' color, 1 a panel's,
// 2 a highlight's, 3 a panel's dark
void Skin_Fill(int y, int h, int tone);
// BG2: the line between two parts of a screen
void Skin_Rule(int y);
// BG2: a highlighted entry in a list, rows y to y + h - 1
void Skin_SelectRows(int y, int h);

// BG3: an icon at column x, row y
void Skin_Icon(int x, int y, int icon);
// BG3: a progress bar over columns x to x + w - 1 of row y, num / den full
void Skin_Progress(int x, int y, int w, u32 num, u32 den);

#endif // DSIRPC_SKIN_H
