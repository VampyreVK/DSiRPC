// dsirpc_ach.h - DSiRPC's achievements in nds-bootstrap's in-game menu.
// See dsirpc_ach.c. Not in B4DS builds.

#ifndef DSIRPC_ACH_H
#define DSIRPC_ACH_H

#include <nds/ndstypes.h>

// When the menu opens, before the main screen is drawn: reads what the
// ARM7's offline play checker knows (dsirpc_ach_menu.h). show = 0 (the
// exception screen): nothing to show this time. The menu's memory is kept
// between openings, so this has to run every time.
void Ach_Open(int show);

// 1 if there's a list to show: the main screen gets an "Achievements" item.
int Ach_HasScreen(void);

// That item's label.
const unsigned char *Ach_Label(void);

// The main screen's achievement lines: the unlocks new since the menu last
// opened, and how many are earned (or why there are none). Nothing when
// this nds-bootstrap isn't checking achievements for the game.
void Ach_DrawMain(void);

// The Achievements screen, until B is pressed.
void Ach_Screen(void);

#endif // DSIRPC_ACH_H
