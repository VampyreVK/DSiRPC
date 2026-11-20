#ifndef DSIRPC_STATE_H
#define DSIRPC_STATE_H

// DSiRPC: save states from the in-game menu (DS-mode games under the DSi-mode
// cardengines only).
//
// A game's states live in one file next to its save, <save name>.dss (the
// .sav's base name: the launcher's save sync only looks at names with ".sav"
// in them), made at boot by conf_sd.cpp as slots x DSS_SLOT_SIZE bytes. The
// ARM7 can only write into a file that is already as big as it needs to be,
// so it's never grown in game. Its first cluster and the slot count go into
// the in-game menu's IgmText (stateCluster, stateSlots).
//
// The menu is the freeze point: the ARM9 is in its IPC-sync IRQ (the
// cardengine's inGameMenu()), the ARM7 in its in-game menu loop, the same
// calls every boot for the same game and nds-bootstrap build. A save takes
// each CPU's registers (every mode's banked ones too) in a setjmp, then its
// memory; a load puts the memory back from a private stack and longjmps into
// the frames the save took, which the memory put back too. Both halves run
// from the in-game menu's window in main RAM (the ARM7 half is ARM code for
// the ARM7, dsirpc_state7.c), and the ARM7 cardengine only calls into it
// (its SSTE command, with dsirpcStateServices[]).
//
// A slot (DSS_SLOT_SIZE bytes): the header (DSS_HEADER_SIZE, written last, so
// a slot whose save didn't finish has no header), the 3D geometry engine's
// matrices at DSS_GEOM_OFFSET (if the header's flags say so), then the
// regions at the offsets the header lists from DSS_DATA_OFFSET.

#ifndef __ASSEMBLER__
#include <nds/ndstypes.h>
#endif
#include "dsirpc_shadow3d.h"

#define DSS_MAGIC          0x54535344 // "DSST"
#define DSS_VERSION        1
#define DSS_HEADER_SIZE    0x1000
#define DSS_GEOM_OFFSET    0x1000     // DssGeometry (DSS_FLAG_GEOMETRY)
#define DSS_GEOM_SIZE      0x1000
#define DSS_DATA_OFFSET    0x4000     // (0x2000 to here: room for a thumbnail later)
#define DSS_SLOT_SIZE      0x600000   // a state is about 0x5D5000 at most (dsirpc_state.c)
#define DSS_MAX_SLOTS      8
#define DSS_DEFAULT_SLOTS  3
#define DSS_SAVE_MAX       0x100000   // the biggest save a state carries (8 Mbit)
#define DSS_REGIONS_MAX    20
#define DSS_FIFO_MAX       16

// Region kinds: who reads and writes it, and how
#define DSS_KIND_MAIN      1 // main RAM: the ARM7, straight to and from the file
#define DSS_KIND_ARM7      2 // the ARM7's own memory (its WRAM, its shared WRAM): the ARM7, straight
#define DSS_KIND_SAVE      3 // the game's save file (addr 0): the ARM7, through the staging buffer
#define DSS_KIND_ARM9      4 // the ARM9's own memory (TCMs, VRAM, palettes, OAM, its shared WRAM): the ARM9, through the staging buffer

// Header flags
#define DSS_FLAG_SHARED_WRAM_SKIPPED BIT(0) // the cardengine keeps ROM data in shared WRAM (useSharedWram)
#define DSS_FLAG_SAVE_INCLUDED       BIT(1)
#define DSS_FLAG_ARM7_NWRAM          BIT(2) // the ARM7 cardengine is in the DSi's WRAM-A at 0x037C0000, so the game's
                                            // ARM7 "shared WRAM" at 0x037F8000 is WRAM-A too: all 32 KB, whatever WRAMCNT says
#define DSS_FLAG_GEOMETRY            BIT(3) // the slot has the geometry engine's matrices (DssGeometry at DSS_GEOM_OFFSET)

// Results (DssRequest.result, State_Save(), State_Load())
#define DSS_OK             0
#define DSS_RESUMED        1   // (State_Save(): a load came back here)
#define DSS_E_NOSLOTS     -1   // no slot file
#define DSS_E_EMPTY       -2   // nothing in that slot
#define DSS_E_GAME        -3   // the slot is another game's, or another build's
#define DSS_E_BUSY        -4   // the cardengine is part way through a ROM read
#define DSS_E_HARDWARE    -5   // the slot's TCM or WRAM setup isn't the game's now
#define DSS_E_IO          -6   // the file couldn't be read or written
#define DSS_E_CORRUPT     -7   // the header's check doesn't match

// Requests (DssRequest.op): one per SSTE command
#define DSS_OP_HEADERS     1  // every slot's header summary to info[]
#define DSS_OP_BEGIN       2  // back up the staging buffer; for a save (arg 1), clear the slot's header first
#define DSS_OP_SAVE7       3  // the ARM7's registers and memory, main RAM and the save to the slot
#define DSS_OP_WRITE       4  // staging buffer [0, len) to the slot at offset
#define DSS_OP_READ        5  // the slot at offset to staging buffer [0, len)
#define DSS_OP_COMMIT      6  // the header to the slot
#define DSS_OP_LOAD7       7  // main RAM, the ARM7's memory and registers from the slot (no return: a longjmp)
#define DSS_OP_END         8  // put the staging buffer back; re-send fifo9[] to the ARM9
#define DSS_OP_READHDR     9  // the slot's header to hdr

#ifndef __ASSEMBLER__

typedef struct {
	u32 addr;
	u32 size;
	u32 offset; // in the slot
	u32 kind;   // DSS_KIND_*
} DssRegion;

// The CPU context dss_setjmp() takes: r4-r11, sp, lr; cpsr; SYS sp, lr;
// FIQ r8-r12, sp, lr, spsr; IRQ, SVC, ABT, UND sp, lr, spsr
#define DSS_CTX_WORDS 33

typedef struct {
	u32 magic;                   // 0x000 DSS_MAGIC, once the save finished
	u16 version;                 // 0x004
	u16 headerSize;              // 0x006
	char gameCode[4];            // 0x008 the ROM header's
	u16 headerCrc;               // 0x00C
	u8 romVersion;               // 0x00E
	u8 unitCode;                 // 0x00F
	u32 stamp;                   // 0x010 the nds-bootstrap build (a hash of the in-game menu's code)
	u32 valueBits;               // 0x014 the ARM9 cardengine's, at the save
	u8 time[8];                  // 0x018 year (from 2000), month, day, weekday, hours, minutes, seconds
	u32 saveSize;                // 0x020 bytes of the save in the state (0: none)
	u32 dtcmReg;                 // 0x024 CP15 c9,c1,0
	u32 itcmReg;                 // 0x028 CP15 c9,c1,1
	u8 wramcnt;                  // 0x02C
	u8 regionCount;              // 0x02D
	u8 fifo9Count;               // 0x02E words the ARM9 had received and not read
	u8 fifo7Count;               // 0x02F    the ARM7
	char title[12];              // 0x030 the ROM header's
	u32 dataSize;                // 0x03C bytes in the slot
	DssRegion region[DSS_REGIONS_MAX]; // 0x040
	u32 ctx9[DSS_CTX_WORDS + 1]; // 0x180
	u32 ctx7[DSS_CTX_WORDS + 1]; // 0x208
	u32 io9[96];                 // 0x290 (dsirpc_state.c's io9Regs)
	u32 io7[64];                 // 0x410 (dsirpc_state7.c's io7Regs)
	u32 fifo9[DSS_FIFO_MAX];     // 0x510
	u32 fifo7[DSS_FIFO_MAX];     // 0x550
	u32 cp15[16];                // 0x590
	u32 flags;                   // 0x5D0 DSS_FLAG_*
	u32 g3dValid;                // 0x5D4 DSIRPC_SH3D_*: the parts of g3d[] the ARM9 cardengine kept (0: none)
	u8 g3d[DSIRPC_SH3D_SIZE];    // 0x5D8 the 3D engine's write-only setup registers, 0x04000330-0x040003BF (dsirpc_shadow3d.h)
	u32 g2dValid;                // 0x668 BIT(layer): the layers of g2d[] the ARM9 cardengine kept (its affValid)
	u32 g2d[DSIRPC_SH2D_LAYERS][4]; // 0x66C BG2 and BG3's rotate/zoom registers, both engines (its aff[])
	u32 reserved[(0xFFC - 0x6AC) / 4];
	u32 check;                   // 0xFFC dss_check() of the header before it
} DssHeader;

#ifndef __cplusplus
_Static_assert(sizeof(DssHeader) == DSS_HEADER_SIZE, "DssHeader layout");
_Static_assert(__builtin_offsetof(DssHeader, g3d) == 0x5D8, "DssHeader layout");
_Static_assert(__builtin_offsetof(DssHeader, g2d) == 0x66C, "DssHeader layout");
#endif

// The 3D geometry engine's matrices, which it only takes commands for (none
// can be read back as they are): what a save could read of them through the
// ones that can, the clip matrix (the position matrix times the projection)
// and the vector matrix's 3x3 (dsirpc_state.c's gxCapture() says how)
typedef struct {
	u32 level;           // the position and vector stack's (GXSTAT bits 8-12)
	u32 mode;            // MTX_MODE
	s32 proj[16];        // the projection matrix, 4x4
	s32 pos[16];         // the position matrix, 4x4
	s32 vec[9];          // the vector matrix, its 3x3 (the rest of it changes nothing a game draws)
	s32 slotPos[31][16]; // the stack's 31 slots (MTX_STORE and MTX_RESTORE's, and MTX_PUSH's)
	s32 slotVec[31][9];
} DssGeometry;

#ifndef __cplusplus
_Static_assert(sizeof(DssGeometry) <= DSS_GEOM_SIZE, "DssGeometry size");
#endif

// A slot's summary for the menu's list
typedef struct {
	u32 magic;      // DSS_MAGIC if the slot has a state
	char gameCode[4];
	u32 stamp;
	u8 time[8];
	u16 headerCrc;
	u16 pad;
} DssSlotInfo;

// The ARM9 half's request to the ARM7 half (in the in-game menu's window,
// cached on the ARM9: it flushes it before a request and invalidates it after)
typedef struct {
	u32 op;          // DSS_OP_*
	u32 slot;
	u32 arg;
	u32 offset;      // WRITE, READ: in the slot
	u32 len;         //   bytes, at INGAME_MENU_EXT_LOCATION
	s32 result;      // DSS_OK or DSS_E_*
	u32 cluster;     // the slot file's first cluster
	u32 slots;
	u32 fileReady;   // file is set up
	u32 extSaved;    // the staging buffer is in the page file
	u32 fileWords[6]; // the slot file's aFile (my_fat.h), as words
	u32 exclCount;   // LOAD7: main RAM ranges a load leaves as they are (the
	u32 excl[6][2];  //   cardengine's own, its shared area): start, end
	u32 arm7Nwram;   // (the ARM7 half, every step) its cardengine is in WRAM-A at 0x037C0000
	u32 saveSize;    // the game's save file's size (the ARM9 cardengine's saveSize)
	u32 pageWords[6]; // pagefile.sys's aFile (the ARM7 half makes it once, with fileReady)
	u32 pad[3];      // (the header at 160 bytes; the whole request is cache lines)
	DssHeader hdr;
	DssSlotInfo info[DSS_MAX_SLOTS];
} DssRequest;

// What only a save or a load uses, which both run once the menu has put the
// game's screens back (each CPU's stacks, and the ARM9's registers until
// they're in the header): in the menu's backup of the sub screen's tiles
// (inGameMenu.c's bgBak), free then
typedef struct {
	u32 ctx9[DSS_CTX_WORDS + 1];
	u32 stack9[0x200];    // 2 KB: the ARM9 half's save and load
	u32 svcStack9[0x40];  //   and the BIOS calls' during a load
	u32 stack7[0x400];    // 4 KB: the ARM7 half's save and load
	u32 svcStack7[0x80];
} DssScratch;

// The ARM7 cardengine's services to the ARM7 half: dsirpcStateServices[] in
// cardenginei/arm7/source/rpcprobe/probe_ach.c (cardengine.c in the
// ALTERNATIVE build, with no checker: its VMs 0), in this order. Each entry
// costs the nearly full ARM7 cardengine 4 bytes, so what the menu can find
// itself isn't here: the save's aFile is at SAV_FILE_LOCATION or
// SAV_FILE_LOCATION_ALT, its size is the ARM9 cardengine's saveSize, it makes
// its own aFiles for the slot file and pagefile.sys (that one from the ARM7
// cardengine's header), as getFileFromCluster() does, and it reads the RTC
// itself.
#define DSS_SVC_FILE_READ       0
#define DSS_SVC_FILE_WRITE      1
#define DSS_SVC_ACH_VM          2  // 2-4: the achievement checker's VMs (AchVm *: the pass lane, the frame lane's two), or 0
#define DSS_SVC_ACH_SHADOW      5  // AchVm **: where its shadow VM's pointer is, or 0
#define DSS_SVC_COUNT           6

#endif // __ASSEMBLER__

#endif // DSIRPC_STATE_H
