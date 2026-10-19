// probe_watch.h - per-frame capture. The PC sends a short list of main RAM
// values to watch ('W'); every VBlank one record of them goes into a ring
// buffer; the PC drains the ring ('F'). Memory reads ('R') can only sample
// as often as a request gets answered, so a value that changes for a single
// frame can be missed; the ring keeps every frame.
//
// Who reads the values: the ARM9, when the ARM9 cardengine carries DSiRPC's
// half (cardenginei/arm9/source/dsirpc_watch.c). The game's writes sit in
// the ARM9's data cache for a while, so reading main RAM from the ARM7 can
// see them a frame or more late; the ARM9 reads through its cache, at the
// very start of every VBlank, before the game's own VBlank code runs. The
// ARM7 records the ARM9's snapshots in order, one per VBlank (common/include/
// dsirpc_watch_block.h). When there's none to record (the ARM9's
// hook isn't in yet, the game had interrupts off, or the cardengine has no
// ARM9 half), the ARM7 reads main RAM itself and marks the record
// (WATCH_REC_ARM7).
//
// Nothing here writes to the game's memory: the watch list lives in
// rpcprobe's own memory, the ring in the main RAM nds-bootstrap sets aside
// for DSiRPC (locations.h's DSIRPC_WATCH_RING_LOCATION), and the hand-over
// block in the ARM9 cardengine's. The ARM9's hook is put in front of the game's VBlank
// interrupt handler (in the game's interrupt table, like nds-bootstrap's own
// hooks) and calls that handler unchanged.
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
//       VBlank), plus WATCH_REC_ARM7 (bit 15) when the ARM7 read them from
//       main RAM instead of the ARM9; values = each watch's bytes as they
//       are in memory (little endian), in list order. ARM9 values are from
//       the start of this VBlank or the one before (one snapshot after
//       another, none twice or skipped), so they can be a frame older than
//       the ARM7's would be.
//
// Status: 0 OK, 1 malformed, 2 address outside main RAM, 3 no watch list.

#ifndef PROBE_WATCH_H
#define PROBE_WATCH_H

#include <nds/ndstypes.h>

#define WATCH_MAX        8
#define WATCH_RING_BYTES 2048 // locations.h's DSIRPC_WATCH_RING_SIZE

#define WATCH_ARM7_ONLY  0x80   // in the 'W' count
#define WATCH_REC_ARM7   0x8000 // in a record's vcount
#define WATCH_REC_VCOUNT 0x01FF

// The hellos report it as a9=: 0 = no ARM9 half, 1 = found, 2 or more =
// found and its VBlank hook in (1 + the number of hooks it has put in, so
// more than 2 means the game replaced its VBlank handler along the way).
extern u8 probeWatchArm9;

// Looks for the ARM9 half's block. Call on the first VBlank (offline play
// needs it too) and when the connection is up.
void ProbeWatch_Init(void);

// For offline play's achievement checker (probe_ach.c): has the ARM9 write
// its data cache back to main RAM at the start of every VBlank from now on
// (rings it to put its VBlank hook in; call again if the write-backs don't
// come). ProbeWatch_Cleaned() counts them (0 if there's no ARM9 half).
void ProbeWatch_Clean(void);
u32 ProbeWatch_Cleaned(void);

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
