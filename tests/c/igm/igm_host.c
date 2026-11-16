// igm_host.c - nds-bootstrap's in-game menu (DSiRPC's look) on a PC.
//
// The menu's own code (arm9_igm/source/inGameMenu.c, dsirpc_skin.c,
// dsirpc_ach.c) runs unchanged: the host maps the DS memory it touches at
// the same addresses (main RAM, the I/O registers, the palettes, VRAM and
// DSIRPC_ACH_LOCATION's RAM), so its registers, VRAM and the ARM7's
// achievement set are plain memory here. The clock moves on in swiDelay(),
// which every one of the menu's waits calls: a scanline a call, REG_VCOUNT
// going round 0-262. At the start of each VBlank the host draws the sub
// screen from VRAM the way the DS's 2D engine does (text backgrounds,
// 4 bits a pixel, by priority; the master brightness), keeps the frame if
// asked to, and presses the next keys of the script (sharedAddr[5], where
// the ARM7 puts them). It plays the ARM7's part of the menu's handshakes
// too: EXIT ends the menu.
//
// Commands on stdin, one a line (tests/helpers/igm_ui.py writes them):
//   font PATH            the 1-bit font (2048 bytes, nitrofiles/fonts/ascii.lz77 unpacked)
//   version TEXT         the version the menu's footer shows (GIT_VER on the console)
//   ach PATH             what's at DSIRPC_ACH_LOCATION: the set's header with the anchor, the list
//   keys FRAMES MASK     hold these keys (input.h's bits) this many frames; one line a step
//   record PATH EVERY    write every EVERY-th frame to PATH: 256x192 RGB, 3 bytes a pixel
//   text FRAME           print the text background (BG3) on that frame: "text FRAME ROW |...|"
//   run                  open the menu; at the end prints "frames N" and "exit"

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#include <nds/ndstypes.h>
#include <nds/bios.h>
#include <nds/input.h>
#include <nds/system.h>
#include <nds/arm9/background.h>
#include <nds/arm9/video.h>
#include "igm_text.h"
#include "inGameMenu.h"
#include "locations.h"
#include "dsirpc_ach_menu.h"

// -- what the menu expects from the rest of nds-bootstrap ------------------------

struct IgmText igmText;
static u32 shared[16];
vu32 *volatile sharedAddr = (vu32 *)shared;
u16 igmPal[8] = { 0xFFFF, 0xDEF7, 0xCE73, 0xF355, 0x801B, 0x8360, 0x0000, 0x0010 }; // card_engine_header.s
u32 *waitSysCyclesLoc;
u32 scfgExtBak;
u16 scfgClkBak;

bool exceptionPrinted;
static void noop(void) {}
VoidFn codeJump = noop;
void (*codeJump1)(int);
u32 codeJumpWord;
VoidFn changeMpu = noop;
VoidFn revertMpu = noop;

void showException(s32 *expReg) { (void)expReg; }
void DC_InvalidateRange(const void *base, u32 size) { (void)base; (void)size; }
void DC_FlushRange(const void *base, u32 size) { (void)base; (void)size; }
void swiWaitForVBlank(void) {
	while (REG_VCOUNT != 192) swiDelay(1);
}

u32 inGameMenu(s32 *mainScreen, u32 consoleModel, s32 *exceptionRegisters);

// -- the DS's memory, where the menu looks for it ------------------------------

static void mapAt(unsigned long addr, unsigned long size) {
	void *p = mmap((void *)addr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
	if (p != (void *)addr) {
		fprintf(stderr, "can't map 0x%08lX\n", addr);
		exit(2);
	}
}

static void mapMemory(void) {
	mapAt(0x02000000, 0x01000000); // main RAM (16 MB on a DSi)
	mapAt(0x04000000, 0x00010000); // I/O
	mapAt(0x05000000, 0x00001000); // palettes
	mapAt(0x06000000, 0x00900000); // VRAM (the sub engine's backgrounds at 0x06200000)
	mapAt(DSIRPC_ACH_LOCATION & ~0xFFFFFul, 0x00100000); // the achievement set's RAM
}

// -- the script and the frames ------------------------------------------------

#define MAX_STEPS 256
static struct { int frames; u32 keys; } steps[MAX_STEPS];
static int nSteps, scriptFrames;
static FILE *record;
static int recordEvery = 1;
#define MAX_TEXT 64
static int textAt[MAX_TEXT], nText;
static int frame;
static unsigned char rgb[256 * 192 * 3];

static u32 keysAt(int f) {
	for (int i = 0; i < nSteps; i++) {
		if (f < steps[i].frames) return steps[i].keys;
		f -= steps[i].frames;
	}
	return (f / 6) & 1 ? 0 : KEY_B; // the script's over: B, again and again, to leave
}

static u32 rgb15(u16 c, u16 bright) {
	int r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
	int mode = (bright >> 14) & 3, f = bright & 31;
	if (f > 16) f = 16;
	if (mode == 1) { r += (31 - r) * f / 16; g += (31 - g) * f / 16; b += (31 - b) * f / 16; }
	if (mode == 2) { r -= r * f / 16; g -= g * f / 16; b -= b * f / 16; }
	return (u32)((r << 3 | r >> 2) << 16 | (g << 3 | g >> 2) << 8 | (b << 3 | b >> 2));
}

// The sub screen as the 2D engine shows it: mode 0's text backgrounds (16
// colours, or 256 with BG_COLOR_256), 256x256 maps, scrolled; the lowest
// priority number on top, then the lowest background number; colour 0
// see-through, the backdrop under them all
static void drawSubScreen(void) {
	const u8 *vram = (const u8 *)BG_GFX_SUB;
	const u16 *pal = BG_PALETTE_SUB;
	u32 disp = REG_DISPCNT_SUB;
	u16 bright = *(vu16 *)0x0400106C;
	for (int y = 0; y < 192; y++) {
		for (int x = 0; x < 256; x++) {
			u16 color = pal[0];
			int best = 4;
			for (int bg = 0; bg < 4; bg++) {
				if (!(disp & BIT(8 + bg))) continue;
				u16 cnt = *(vu16 *)(0x04001008 + 2 * bg);
				int prio = cnt & 3;
				if (prio >= best) continue;
				int sx = (x + (*(vu16 *)(0x04001010 + 4 * bg) & 0x1FF)) & 255;
				int sy = (y + (*(vu16 *)(0x04001012 + 4 * bg) & 0x1FF)) & 255;
				const u8 *map = vram + ((cnt >> 8) & 31) * 0x800;
				const u8 *tiles = vram + ((cnt >> 2) & 15) * 0x4000;
				u16 e = (u16)(map[((sy >> 3) * 32 + (sx >> 3)) * 2] | map[((sy >> 3) * 32 + (sx >> 3)) * 2 + 1] << 8);
				int px = sx & 7, py = sy & 7;
				if (e & 0x400) px = 7 - px;
				if (e & 0x800) py = 7 - py;
				int idx;
				u16 c;
				if (cnt & BG_COLOR_256) {
					idx = tiles[(e & 1023) * 64 + py * 8 + px];
					c = pal[idx];
				} else {
					u8 two = tiles[(e & 1023) * 32 + py * 4 + px / 2];
					idx = (px & 1) ? two >> 4 : two & 15;
					c = pal[(e >> 12) * 16 + idx];
				}
				if (!idx) continue;
				color = c;
				best = prio;
			}
			u32 v = rgb15(color, bright);
			unsigned char *o = &rgb[(y * 256 + x) * 3];
			o[0] = (unsigned char)(v >> 16);
			o[1] = (unsigned char)(v >> 8);
			o[2] = (unsigned char)v;
		}
	}
}

static void printText(void) {
	const u16 *map = BG_MAP_RAM_SUB(15);
	for (int row = 0; row < 24; row++) {
		char line[33];
		for (int col = 0; col < 32; col++) {
			u16 t = map[row * 32 + col] & 1023;
			line[col] = (t >= 32 && t < 127) ? (char)t : (t >= 256 ? '#' : ' ');
		}
		line[32] = 0;
		printf("text %d %02d |%s|\n", frame, row, line);
	}
}

// The start of a VBlank: the frame as it's shown, then the next frame's keys
static void vblank(void) {
	if (record && frame % recordEvery == 0) {
		drawSubScreen();
		fwrite(rgb, 1, sizeof(rgb), record);
	}
	for (int i = 0; i < nText; i++) {
		if (textAt[i] == frame) printText();
	}
	frame++;
	sharedAddr[5] = keysAt(frame);
	if (frame > scriptFrames + 600) {
		fprintf(stderr, "the menu didn't close (frame %d)\n", frame);
		exit(3);
	}
}

// The clock: a scanline a call. The menu's commands to the ARM7 that it
// waits on are answered here, a frame later, as the ARM7 would.
void swiDelay(u32 duration) {
	(void)duration;
	u16 line = (u16)((REG_VCOUNT + 1) % 263);
	REG_VCOUNT = line;
	if (line == 192) {
		vblank();
		if (sharedAddr[4] == 0x54495845) sharedAddr[4] = 0; // EXIT: the menu closes
	}
}

// -- the commands ------------------------------------------------------------------

static void load(const char *path, void *to, size_t max) {
	FILE *f = fopen(path, "rb");
	if (!f) {
		fprintf(stderr, "can't open %s\n", path);
		exit(2);
	}
	size_t n = fread(to, 1, max, f);
	fclose(f);
	if (!n) exit(2);
}

int main(void) {
	mapMemory();
	char line[1024];
	while (fgets(line, sizeof(line), stdin)) {
		line[strcspn(line, "\r\n")] = 0;
		char path[1000];
		int a;
		unsigned b;
		if (strncmp(line, "version ", 8) == 0) {
			strncpy((char *)igmText.version, line + 8, sizeof(igmText.version) - 1);
		} else if (sscanf(line, "font %999s", path) == 1) {
			load(path, igmText.font, sizeof(igmText.font));
		} else if (sscanf(line, "ach %999s", path) == 1) {
			load(path, (void *)DSIRPC_ACH_LOCATION, DSIRPC_ACH_SIZE);
		} else if (sscanf(line, "keys %d %u", &a, &b) == 2 && nSteps < MAX_STEPS) {
			steps[nSteps].frames = a;
			steps[nSteps++].keys = b;
			scriptFrames += a;
		} else if (sscanf(line, "record %999s %d", path, &a) == 2) {
			record = fopen(path, "wb");
			recordEvery = a > 0 ? a : 1;
		} else if (sscanf(line, "text %d", &a) == 1 && nText < MAX_TEXT) {
			textAt[nText++] = a;
		} else if (strcmp(line, "run") == 0) {
			// nds-bootstrap's English text (retail/arm9/source/conf_sd.cpp's defaults)
			memcpy(igmText.ndsBootstrap, "nds-bootstrap", 14);
			strcpy((char *)igmText.aYes, "A: Yes");
			strcpy((char *)igmText.bNo, "B: No");
			const char *menu[8] = { "Return to Game", "Reset Game", "Screenshot...", "Manual...", "Dump RAM",
			                        "Options...", "RAM Viewer...", "Quit Game" };
			for (int i = 0; i < 8; i++) strcpy((char *)igmText.menu[i], menu[i]);
			const char *labels[6] = { "Main Screen", "Brightness", "Volume", "Refresh Rate", "Clock Speed", "VRAM Mode" };
			for (int i = 0; i < 6; i++) strcpy((char *)igmText.optionsLabels[i], labels[i]);
			const char *values[7] = { "Auto", "Bottom", "Top", "67 MHz", "133 MHz", "DS mode", "DSi mode" };
			for (int i = 0; i < 7; i++) strcpy((char *)igmText.optionsValues[i], values[i]);
			const char *desc[6] = { "Set whether to show the main screen on the top or bottom. Does not change which screen gets a screenshot.",
			                        "Change the screen brightness level.", "Change the sound volume.",
			                        "Change the screen refresh rate.", "Change the ARM9 CPU speed.",
			                        "Change the VRAM mode." };
			for (int i = 0; i < 6; i++) strcpy((char *)igmText.optionsDescriptions[i], desc[i]);
			strcpy((char *)igmText.resetGameMessage, "Are you sure you want to reset the game?");
			strcpy((char *)igmText.quitGameMessage, "Are you sure you want to quit the game?");
			igmText.hotkey = KEY_L | KEY_DOWN | KEY_B;
			// What the ARM7 tells the menu: the menu's open, the time; a battery 3/4
			// full, the backlight's level 3 and the volume 24 of 31. A DSi-mode game
			// at 133 MHz.
			sharedAddr[4] = 0x554E454D; // MENU
			sharedAddr[6] = 0x0B | 3 << 8 | 24 << 16;
			REG_SCFG_CLK = 0x0181;
			REG_SCFG_EXT = 0x8307F100;
			sharedAddr[7] = 0x10000000 | 17;
			sharedAddr[8] = 10;
			sharedAddr[5] = keysAt(0);
			REG_VCOUNT = 0;
			s32 mainScreen = 0;
			inGameMenu(&mainScreen, 0, NULL);
			if (record) fclose(record);
			printf("frames %d\nexit\n", frame);
			fflush(stdout);
			return 0;
		} else if (line[0]) {
			printf("? %s\n", line);
		}
	}
	return 1;
}
