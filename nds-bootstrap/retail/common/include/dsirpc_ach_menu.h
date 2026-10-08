// dsirpc_ach_menu.h - what nds-bootstrap's in-game menu shows of DSiRPC's
// offline play: the game's achievements. The ARM7's rpcprobe/probe_ach.c
// loads the set (sd:/RPCSET.BIN, from DSiRPC's core/offline.py) into
// DSIRPC_ACH_LOCATION: its 64-byte header, the program the console checks,
// then the list of every achievement of the game. It marks the console's
// unlocks in that list as they happen, and keeps its notes for the menu
// (the anchor) in its RAM copy of the header's bytes 40-63, which are 0 in
// the file. The menu (arm9_igm/source/dsirpc_ach.c) only reads all this.

#ifndef DSIRPC_ACH_MENU_H
#define DSIRPC_ACH_MENU_H

#include <nds/ndstypes.h>

#define DSIRPC_MENU_ANCHOR_OFFSET 40
#define DSIRPC_MENU_ANCHOR_MAGIC  0x414D5244 // "DRMA"
#define DSIRPC_LIST_MAGIC         0x4E4D5244 // "DRMN"
#define DSIRPC_LIST_VERSION       1

// The anchor's status
#define DSIRPC_MENU_READY     2 // the set is checked and running; the list (if any) is live
#define DSIRPC_MENU_CHECKING  1 // the set loaded; its CRC is being checked
#define DSIRPC_MENU_NO_SET    0 // no RPCSET.BIN: the game wasn't started from the launcher
// Below 0: why the set wasn't used (probe_ach.h's PROBE_ACH_E_*)

typedef struct {
	u32 magic;    // DSIRPC_MENU_ANCHOR_MAGIC, written when the game starts
	u8  game[4];  // the running game's code
	s16 status;   // DSIRPC_MENU_*
	u16 unlocks;  // the console's unlocks this game: the last one's seq
	u16 newFrom;  // entries with a seq above this one are new to the menu
	u16 open;     // 1 while the in-game menu is open (stale anchors don't count)
	u32 list;     // the list's offset from DSIRPC_ACH_LOCATION, 0 = none
	u32 reserved;
} DsirpcMenuAnchor; // 24 bytes

typedef struct {
	u32 magic;    // DSIRPC_LIST_MAGIC
	u16 version;  // DSIRPC_LIST_VERSION
	u16 count;    // entries
	u32 textSize; // the text after the entries (padded to 4)
	u32 reserved;
} DsirpcList; // 16 bytes, then the entries, then the text

#define DSIRPC_LIST_EARNED     1 // RetroAchievements has it (as far as DSiRPC knew)
#define DSIRPC_LIST_ON_CONSOLE 2 // earned on this console (set by probe_ach.c)
#define DSIRPC_LIST_CHECKED    4 // the console checks it

typedef struct {
	u32 id;          // RetroAchievements' achievement ID
	u32 when;        // seconds since 2000-01-01 by the console's clock; 0 = not earned or not known
	u16 title;       // offset of its title in the text (NUL-terminated ASCII)
	u16 description; // ... and of its description
	u8  points;
	u8  flags;       // DSIRPC_LIST_*
	u16 seq;         // the console's unlock number this game (1, 2, ...), 0 = none
} DsirpcListEntry; // 16 bytes

#endif // DSIRPC_ACH_MENU_H
