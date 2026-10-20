// probe_watch.h - per-frame capture. The PC sends a short list of main RAM
// values to watch ('W'); every VBlank one record of them goes into a ring
// buffer; the PC drains the ring ('F'). Memory reads ('R') can only sample
// as often as a request gets answered, so a value that changes for a single
// frame can be missed; the ring keeps every frame.
//
// The ARM7 reads the values from main RAM at the start of every VBlank. The
// game's writes sit in the ARM9's data cache for a while, so on their own
// those reads can be a frame or more late; when the ARM9 cardengine carries
// DSiRPC's half (cardenginei/arm9/source/dsirpc_watch.c), the ARM9 writes its
// data cache back to main RAM whenever the game is idle, and a game that
// idles once its frame is done has every value there by the next VBlank
// (common/include/dsirpc_watch_block.h). A record taken with no write-back
// since the last one is marked (WATCH_REC_ARM7). This file also finds the
// game's OS_Halt for that, and asks the ARM9 to patch it.
//
// Nothing here writes to the game's memory: the watch list lives in
// rpcprobe's own memory, the ring in the main RAM nds-bootstrap sets aside
// for DSiRPC (locations.h's DSIRPC_WATCH_RING_LOCATION), and the hand-over
// block in the ARM9 cardengine's. (The ARM9 patches the game's OS_Halt
// itself.)
//
// Wire format (big endian, like 'R'; see probe_req.c for the transport):
//
//   'W' | seq u16 | count u8 | count x (addr u32, size u8)
//       size is 1, 2 or 4; count is at most WATCH_MAX, plus WATCH_ARM7_ONLY
//       (0x80) to have the ARM7 read every value itself (for comparing).
//       count 0 stops the capture. Any 'W' empties the ring and restarts its
//       numbering at 0.
//   reply: 'D' | seq u16 | count u8 | status u8
//
//   'F' | seq u16 | 0 u8 | from u16
//       from = number of the first record wanted (the next one after the
//       last record the PC has; 0 after a 'W').
//   reply: 'D' | seq u16 | records u8 | status u8 |
//          first u16 | lost u16 | recSize u8 | records x record
//       first = number of the first record in this reply; lost = records
//       between `from` and `first` that the ring had already overwritten.
//
//   record: tick u16 | vcount u16 | values...
//       tick = rpcprobe's VBlank count (one record per frame); vcount = the
//       scanline the values were read on (bits 0-8; 192 is the start of
//       VBlank), plus WATCH_REC_ARM7 (bit 15) when the ARM9 hadn't written
//       its data cache back since the record before (no ARM9 half, its patch
//       not in yet, or the game busy the whole frame), so a value may be a
//       frame late; values = each watch's bytes as they are in memory
//       (little endian), in list order.
//
// Status: 0 OK, 1 malformed, 2 address outside main RAM, 3 no watch list.

#ifndef PROBE_WATCH_H
#define PROBE_WATCH_H

#include <nds/ndstypes.h>

#define WATCH_MAX        8
#define WATCH_RING_BYTES 2048 // locations.h's DSIRPC_WATCH_RING_SIZE

#define WATCH_ARM7_ONLY  0x80   // in the 'W' count (older PCs: ignored now, the ARM7 reads everything)
#define WATCH_REC_ARM7   0x8000 // in a record's vcount
#define WATCH_REC_VCOUNT 0x01FF

// The hellos report it as a9=: 0 = no ARM9 half, 1 = found, 2 or more =
// found and the game's OS_Halt patched (1 + the copies patched), so the
// write-backs in the game's idle time are on.
extern u8 probeWatchArm9;

// Looks for the ARM9 half's block. Call on the first VBlank (offline play
// needs it too) and when the connection is up.
void ProbeWatch_Init(void);

// The game's ARM9 binary, from its NDS header: where to look for OS_Halt.
// Call on the first VBlank.
void ProbeWatch_Game(const void *ndsHeader);

// Looks for OS_Halt, a part at a time: at most about `maxLines` scanlines,
// and none while romWaiting() says the ARM9 waits for a ROM read (NULL: no
// such check). Call from the ARM7's idle time (nds-bootstrap's swiHalt hook).
// Returns 1 if it stopped for that ROM read.
int ProbeWatch_Idle(u16 maxLines, int (*romWaiting)(void));

// Call first thing every VBlank: notes whether a write-back came since the
// last VBlank (ProbeWatch_Fresh(): 1 if one did, 0 if not or there's no
// ARM9 half), and asks the ARM9 for the patch while it isn't in.
void ProbeWatch_Tick(void);
int ProbeWatch_Fresh(void);

// Called once per VBlank (while connected) with the scanline the tick
// started on.
void ProbeWatch_Sample(u16 vcount);

// Request handlers. `req` points at the request's first byte ('W' or 'F'),
// `len` is its length. Each writes the reply body (after the 5-byte reply
// header) to `out`, at most `maxOut` bytes, sets *count and *status, and
// returns the body length.
u16 ProbeWatch_Set(const u8 *req, int len, u8 *count, u8 *status);
u16 ProbeWatch_Fetch(const u8 *req, int len, u8 *out, u16 maxOut, u8 *count, u8 *status);

#endif // PROBE_WATCH_H
