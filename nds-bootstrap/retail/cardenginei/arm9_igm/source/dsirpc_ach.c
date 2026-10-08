// dsirpc_ach.c - DSiRPC's achievements in nds-bootstrap's in-game menu.
//
// The main screen shows the unlocks that are new since the menu last opened
// and how many of the game's achievements are earned (or why the console
// isn't checking any). Its "Achievements" item lists them all: the earned
// ones first, new ones on top, then newest first with when they were
// earned, then the rest in RetroAchievements' order. The bottom of that
// screen shows the highlighted one's description.
//
// It all comes from offline play's set, which the ARM7's
// rpcprobe/probe_ach.c loads into DSIRPC_ACH_LOCATION and keeps up to date
// as the console unlocks achievements (dsirpc_ach_menu.h). This file only
// reads it, with the MPU opened up to reach it (changeMpu(), as the RAM
// viewer does). Titles in lime were earned on this console; DSiRPC gets
// them at the next sync. Not in B4DS builds (no rpcprobe there).

#ifndef B4DS

#include <nds/ndstypes.h>
#include <nds/input.h>
#include "inGameMenu.h"
#include "locations.h"
#include "dsirpc_ach_menu.h"
#include "dsirpc_ach.h"

#ifndef ACH_BASE // (the PC test has its own)
#include <nds/system.h>
#define ACH_BASE ((const u8 *)DSIRPC_ACH_LOCATION)
#define ACH_KEYS (sharedAddr[5])
void DC_InvalidateRange(const void *base, u32 size);
void mySwiDelay(int delay);
static void waitFrame(void) {
	while (REG_VCOUNT != 191) mySwiDelay(100);
	while (REG_VCOUNT == 191) mySwiDelay(100);
}
#endif

#define ACH_MAX          512    // entries listed (a longer list is cut short)
#define ACH_ROWS         8      // entries a page, two lines each
#define ACH_TOP          1      // the first entry's line
#define ACH_RULE         17     // the line between the list and the details
#define ACH_DETAIL       18     // the highlighted one's text ...
#define ACH_DETAIL_LINES 5      // ... on lines 18-22
#define ACH_ABSENT       0x7FFF // status: no anchor (this nds-bootstrap isn't checking the game)
#define ACH_COLS         32

static s16 achStatus = ACH_ABSENT;
static const DsirpcListEntry *achEntries;
static const char *achText;
static u16 achCount, achEarned, achNew, achNewFrom;
static u32 achPoints, achPointsEarned;
static u16 achOrder[ACH_MAX];
static char achNewTitle[2][ACH_COLS - 1]; // the two newest new ones, for the main screen

static const unsigned char achLabel[] = "Achievements";

// -- text ----------------------------------------------------------------

static int achNum(char *p, u32 v) {
	char tmp[10];
	int n = 0;
	do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v);
	for (int i = 0; i < n; i++) p[i] = tmp[n - 1 - i];
	return n;
}

static int achStr(char *p, const char *s) {
	int n = 0;
	while (s[n]) { p[n] = s[n]; n++; }
	return n;
}

// "2026-10-08 12:15" from seconds since 2000-01-01 (17 bytes with the NUL)
static void achDate(char *out, u32 t) {
	static const u8 monthDays[12] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
	u32 days = t / 86400, mins = (t % 86400) / 60;
	int y = 2000, m = 0;
	while (1) { // every 4th year is a leap year until 2100
		u32 len = (y % 4) ? 365 : 366;
		if (days < len) break;
		days -= len;
		y++;
	}
	while (1) {
		u32 len = monthDays[m] + (m == 1 && !(y % 4));
		if (days < len) break;
		days -= len;
		m++;
	}
	const u32 parts[5] = { y, m + 1, days + 1, mins / 60, mins % 60 };
	static const char seps[5] = { '-', '-', ' ', ':', 0 };
	int n = 0;
	for (int i = 0; i < 5; i++) {
		if (i && parts[i] < 10) out[n++] = '0';
		n += achNum(&out[n], parts[i]);
		out[n++] = seps[i];
	}
}

// At most `max` characters of `s` from column x; a cut title ends in '~'
static void achPrintN(int x, int y, const char *s, int max, FontPalette pal) {
	char line[ACH_COLS + 1];
	int n = 0;
	while (s[n] && n < max) { line[n] = s[n]; n++; }
	if (s[n] && n) line[n - 1] = '~';
	line[n] = 0;
	print(x, y, (const unsigned char *)line, pal, false);
}

// `s` word-wrapped from line y, at most `lines` lines (the last one ends in
// "..." if it doesn't all fit). Returns the line after the last one used.
static int achWrap(int y, const char *s, int lines, FontPalette pal) {
	while (lines > 0) {
		while (*s == ' ') s++;
		if (!*s) break;
		int n = 0, cut = 0;
		while (s[n] && n < ACH_COLS) {
			if (s[n] == ' ') cut = n;
			n++;
		}
		if (s[n] && s[n] != ' ' && cut) n = cut; // don't split a word
		char line[ACH_COLS + 1];
		for (int i = 0; i < n; i++) line[i] = s[i];
		s += n;
		while (*s == ' ') s++;
		if (lines == 1 && *s) { // more than fits
			if (n > ACH_COLS - 3) n = ACH_COLS - 3;
			line[n++] = '.';
			line[n++] = '.';
			line[n++] = '.';
		}
		line[n] = 0;
		print(0, y, (const unsigned char *)line, pal, false);
		y++;
		lines--;
	}
	return y;
}

// -- the list --------------------------------------------------------------

static int achIsEarned(const DsirpcListEntry *e) {
	return e->flags & (DSIRPC_LIST_EARNED | DSIRPC_LIST_ON_CONSOLE);
}

static int achIsNew(const DsirpcListEntry *e) {
	return e->seq > achNewFrom;
}

// Whether entry a is listed before entry b: earned first; of those, new
// ones, then dated ones newest first, then the console's latest unlocks
// first; otherwise the list's (RetroAchievements') order.
static int achBefore(u16 a, u16 b) {
	const DsirpcListEntry *x = &achEntries[a], *y = &achEntries[b];
	int ex = achIsEarned(x) != 0, ey = achIsEarned(y) != 0;
	if (ex != ey) return ex;
	if (ex) {
		int nx = achIsNew(x), ny = achIsNew(y);
		if (nx != ny) return nx;
		if ((x->when != 0) != (y->when != 0)) return x->when != 0;
		if (x->when != y->when) return x->when > y->when;
		if (x->seq != y->seq) return x->seq > y->seq;
	}
	return a < b;
}

static void achLoadList(u32 offset) {
	if (offset < 64 || offset > DSIRPC_ACH_SIZE - sizeof(DsirpcList)) return;
	const DsirpcList *l = (const DsirpcList *)(ACH_BASE + offset);
	DC_InvalidateRange(l, sizeof(DsirpcList));
	u32 entriesSize = l->count * sizeof(DsirpcListEntry);
	if (l->magic != DSIRPC_LIST_MAGIC || l->version != DSIRPC_LIST_VERSION || !l->count ||
	    !l->textSize || l->textSize > DSIRPC_ACH_SIZE ||
	    offset + sizeof(DsirpcList) + entriesSize + l->textSize > DSIRPC_ACH_SIZE) {
		return;
	}
	const DsirpcListEntry *e = (const DsirpcListEntry *)(l + 1);
	const char *text = (const char *)(e + l->count);
	DC_InvalidateRange(e, entriesSize + l->textSize);
	if (text[l->textSize - 1] != 0) return; // so every string ends inside the text
	u16 n = (l->count > ACH_MAX) ? ACH_MAX : l->count;
	for (u16 i = 0; i < n; i++) {
		if (e[i].title >= l->textSize || e[i].description >= l->textSize) return;
	}

	achEntries = e;
	achText = text;
	achCount = n;
	for (u16 i = 0; i < n; i++) {
		achPoints += e[i].points;
		if (achIsEarned(&e[i])) {
			achEarned++;
			achPointsEarned += e[i].points;
		}
		if (achIsNew(&e[i])) achNew++;
		// insertion sort: a few hundred entries at most
		u16 j = i;
		while (j > 0 && achBefore(i, achOrder[j - 1])) {
			achOrder[j] = achOrder[j - 1];
			j--;
		}
		achOrder[j] = i;
	}
	for (int k = 0; k < 2 && k < achNew; k++) { // new ones are listed first
		const char *t = achText + achEntries[achOrder[k]].title;
		int c = 0;
		while (t[c] && c < ACH_COLS - 2) { achNewTitle[k][c] = t[c]; c++; }
		if (t[c] && c) achNewTitle[k][c - 1] = '~';
		achNewTitle[k][c] = 0;
	}
}

void Ach_Open(int show) {
	achStatus = ACH_ABSENT;
	achEntries = 0;
	achCount = achEarned = achNew = 0;
	achPoints = achPointsEarned = 0;
	if (!show) return;

	(*changeMpu)();
	DC_InvalidateRange(ACH_BASE, 64);
	const DsirpcMenuAnchor *a = (const DsirpcMenuAnchor *)(ACH_BASE + DSIRPC_MENU_ANCHOR_OFFSET);
	// open: the ARM7 says this menu is open now, so the anchor isn't left
	// over from an earlier game
	if (a->magic == DSIRPC_MENU_ANCHOR_MAGIC && a->open == 1) {
		achStatus = a->status;
		achNewFrom = a->newFrom;
		if (achStatus == DSIRPC_MENU_READY && a->list) achLoadList(a->list);
	}
	(*revertMpu)();
}

int Ach_HasScreen(void) {
	return achCount != 0;
}

const unsigned char *Ach_Label(void) {
	return achLabel;
}

// -- the main screen ---------------------------------------------------------

#define ACH_BANNER  10 // lines 10-13: the new unlocks
#define ACH_SUMMARY 18 // line 18: how many are earned

void Ach_DrawMain(void) {
	if (achStatus == ACH_ABSENT) return;
	char line[ACH_COLS + 1];
	int n;

	if (achNew) {
		n = achStr(line, "* ");
		n += achNum(&line[n], achNew);
		n += achStr(&line[n], achNew == 1 ? " new achievement! *" : " new achievements! *");
		line[n] = 0;
		printCenter(16, ACH_BANNER, (const unsigned char *)line, FONT_LIME, false);
		for (int k = 0; k < 2 && k < achNew; k++) {
			printCenter(16, ACH_BANNER + 1 + k, (const unsigned char *)achNewTitle[k], FONT_WHITE, false);
		}
		if (achNew > 2) {
			n = achStr(line, "and ");
			n += achNum(&line[n], achNew - 2);
			n += achStr(&line[n], " more");
			line[n] = 0;
			printCenter(16, ACH_BANNER + 3, (const unsigned char *)line, FONT_LIGHT_GRAY, false);
		}
	}

	n = achStr(line, "Achievements: ");
	if (achCount) {
		n += achNum(&line[n], achEarned);
		n += achStr(&line[n], " of ");
		n += achNum(&line[n], achCount);
		n += achStr(&line[n], " earned");
	} else {
		const char *why;
		switch (achStatus) {
			case DSIRPC_MENU_READY:    why = "sync to list"; break; // a version 2 set
			case DSIRPC_MENU_CHECKING: why = "checking set"; break;
			case DSIRPC_MENU_NO_SET:   why = "no set loaded"; break;
			case -1:                   why = "set version?"; break; // nds-bootstrap older than DSiRPC
			case -2:                   why = "another game's"; break;
			case -3:                   why = "set too big"; break;
			case -5:                   why = "set damaged"; break;
			default:                   why = "set not loaded"; break;
		}
		n += achStr(&line[n], why);
	}
	line[n] = 0;
	print(1, ACH_SUMMARY, (const unsigned char *)line, FONT_LIGHT_BLUE, false);
}

// -- the Achievements screen ------------------------------------------------------

static u32 achWaitKeys(u32 keys) {
	// A held key repeats after 10 frames
	for (int i = 0; i < 10 && (ACH_KEYS & keys); i++) waitFrame();
	do {
		waitFrame();
	} while (!(ACH_KEYS & keys));
	return ACH_KEYS & keys;
}

static int achPointsText(char *p, u32 points) {
	int n = achNum(p, points);
	return n + achStr(&p[n], points == 1 ? " pt" : " pts");
}

static void achDraw(int top, int sel) {
	char line[ACH_COLS + 1];
	int n;
	clearScreen(false);

	n = achNum(line, achEarned); // "12/102 earned", "145/777 pts"
	line[n++] = '/';
	n += achNum(&line[n], achCount);
	n += achStr(&line[n], " earned");
	line[n] = 0;
	print(0, 0, (const unsigned char *)line, FONT_LIGHT_BLUE, false);
	n = achNum(line, achPointsEarned);
	line[n++] = '/';
	n += achPointsText(&line[n], achPoints);
	line[n] = 0;
	printRight(ACH_COLS - 1, 0, (const unsigned char *)line, FONT_LIGHT_BLUE, false);

	for (int r = 0; r < ACH_ROWS && top + r < achCount; r++) {
		const DsirpcListEntry *e = &achEntries[achOrder[top + r]];
		int y = ACH_TOP + r * 2;
		FontPalette pal = !achIsEarned(e) ? FONT_DARKER_GRAY
		                : (e->flags & DSIRPC_LIST_ON_CONSOLE) ? FONT_LIME : FONT_WHITE;
		if (top + r == sel) printChar(0, y, '>', FONT_WHITE, false);
		achPrintN(1, y, achText + e->title, ACH_COLS - 1, pal);

		if (achIsEarned(e)) {
			if (e->when) {
				achDate(line, e->when);
				n = 16;
			} else {
				n = achStr(line, "earned");
			}
		} else {
			n = achStr(line, "locked");
		}
		line[n++] = ' ';
		line[n++] = ' ';
		n += achPointsText(&line[n], e->points);
		if (!achIsEarned(e) && !(e->flags & DSIRPC_LIST_CHECKED)) {
			n += achStr(&line[n], ", not on DS"); // the console can't check it
		}
		line[n] = 0;
		print(3, y + 1, (const unsigned char *)line, achIsEarned(e) ? FONT_LIGHT_GRAY : FONT_DARKER_GRAY, false);
		if (achIsNew(e)) print(ACH_COLS - 3, y + 1, (const unsigned char *)"NEW", FONT_LIME, false);
	}

	for (int x = 0; x < ACH_COLS; x++) printChar(x, ACH_RULE, '-', FONT_DARKER_GRAY, false);
	const DsirpcListEntry *e = &achEntries[achOrder[sel]];
	const char *title = achText + e->title;
	int y = ACH_DETAIL, lines = ACH_DETAIL_LINES;
	int titleLen = 0;
	while (title[titleLen]) titleLen++;
	if (titleLen > ACH_COLS - 1) { // cut short in the list: the whole title first
		int next = achWrap(y, title, 2, FONT_WHITE);
		lines -= next - y;
		y = next;
	}
	achWrap(y, achText + e->description, lines, FONT_LIGHT_GRAY);

	print(0, 23, (const unsigned char *)"B: back  L/R: page", FONT_LIGHT_BLUE, false);
	n = achNum(line, sel + 1);
	line[n++] = '/';
	n += achNum(&line[n], achCount);
	line[n] = 0;
	printRight(ACH_COLS - 1, 23, (const unsigned char *)line, FONT_LIGHT_BLUE, false);
}

void Ach_Screen(void) {
	if (!achCount) return;
	(*changeMpu)();
	int top = 0, sel = 0;
	const int lastTop = (achCount > ACH_ROWS) ? achCount - ACH_ROWS : 0;
	while (1) {
		if (sel < top) top = sel;
		if (sel >= top + ACH_ROWS) top = sel - ACH_ROWS + 1;
		achDraw(top, sel);

		u32 keys = achWaitKeys(KEY_UP | KEY_DOWN | KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R | KEY_B);
		if (keys & KEY_B) break;
		if (keys & KEY_UP) {
			sel = sel ? sel - 1 : achCount - 1;
		} else if (keys & KEY_DOWN) {
			sel = (sel + 1 < achCount) ? sel + 1 : 0;
		} else { // a page up or down, the highlight staying where it is on the screen
			int step = (keys & (KEY_LEFT | KEY_L)) ? -ACH_ROWS : ACH_ROWS;
			int newTop = top + step;
			if (newTop < 0) newTop = 0;
			if (newTop > lastTop) newTop = lastTop;
			sel += newTop - top;
			if (newTop == top) sel = (step < 0) ? 0 : achCount - 1; // already at the end
			if (sel < 0) sel = 0;
			if (sel >= achCount) sel = achCount - 1;
			top = newTop;
		}
	}
	// B must be up before going back, or the main screen would take it too
	do {
		waitFrame();
	} while (ACH_KEYS & KEY_B);
	(*revertMpu)();
}

#endif // B4DS
