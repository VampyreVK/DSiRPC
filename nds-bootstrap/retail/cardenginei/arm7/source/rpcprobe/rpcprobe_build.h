// rpcprobe_build.h - build-wide switches for rpcprobe. Every rpcprobe .c
// file that has a switch includes this, so it means the same thing everywhere.

#ifndef RPCPROBE_BUILD_H
#define RPCPROBE_BUILD_H

// 1 = answer memory read requests from the PC (probe_req.c).
// 0 = send hello packets only (handy for ruling the receive path out when
//     something goes wrong).
#define RPCPROBE_REQUESTS 1

// 1 = read received packets with CMD53 block transfers (one SDIO command
// per packet instead of one per byte; see twl_wifi.c). If they fail on
// this console, receiving switches itself back to CMD52 and the hellos
// say rxm=52. 0 = CMD52 only, as before.
#define RPCPROBE_RX_CMD53 1

// 1 = send replies with CMD53 block writes too (and most hellos: every
// RPCPROBE_HELLO_CMD52_EVERY-th one still goes out with CMD52, so the PC
// always hears from the DSi). Falls back to CMD52 by itself if CMD53
// writes fail, or if the PC keeps re-sending a request (its replies
// aren't arriving); the hellos say txm=52 then. 0 = CMD52 only.
#define RPCPROBE_TX_CMD53 1
#define RPCPROBE_HELLO_CMD52_EVERY 10

// Every frame the chip receives (including other devices' broadcast
// traffic) has to be drained inside the VBlank interrupt.
//
// With CMD52 (one SDIO command per byte, about 19 us each) a single big
// frame used to take several milliseconds - enough to make the game
// stutter - so at most this many bytes are read per VBlank, and a bigger
// frame is drained over several. Lower = smoother, higher = faster
// replies. The "vb=" field in the hello packets shows the longest VBlank
// tick, for tuning.
#define RPCPROBE_RX_BYTES_PER_VBLANK 128

// With CMD53 a whole frame is one command, so a VBlank drains up to this
// many frames or this many bytes, whichever comes first, and stops after
// anything that sends a reply (one send per VBlank, which also keeps the
// tick short while sending is CMD52).
#define RPCPROBE_RX53_FRAMES_PER_VBLANK 8
#define RPCPROBE_RX53_BYTES_PER_VBLANK 2048

// 1 = check the game's achievements in game, for offline play: the set the
// DSiRPC launcher puts in sd:/RPCSET.BIN (probe_ach.c). With Wi-Fi, a
// "DSiRPC ach" packet after each hello says how it's going, so it can be
// compared with what DSiRPC unlocks. 0 = off.
#ifndef RPCPROBE_ACH // (a test build can set it with DSIRPC_CFLAGS)
#define RPCPROBE_ACH 1
#endif

// Looking for the game's OS_Halt (probe_watch.c: the ARM9 patches it to write
// its data cache back whenever the game is idle) takes this many scanlines at
// most per visit to the game's idle time, from the start until it's found.
// The game's ARM9 binary is read 256 words between looks at the clock.
#define RPCPROBE_WATCH_SCAN_LINES 4

// The checker runs while the game's ARM7 idles (nds-bootstrap's swiHalt
// hook, outside interrupts): at most this many scanlines (about 64 us
// each; a frame has 263) a visit, and a frame. The rest of the idle time the
// ARM7 sleeps as usual. It checks the time every 8 conditions, so it usually
// goes over by a scanline or two.
#define RPCPROBE_ACH_IDLE_LINES_PER_VISIT 16
#define RPCPROBE_ACH_IDLE_LINES_PER_FRAME 120

// If the swiHalt hook hasn't run for this many VBlanks (a game whose
// swiHalt nds-bootstrap couldn't hook), the VBlank does the checking
// instead: this many scanlines a VBlank, skipped if the rest of the tick
// already took the second number. A big set takes a few VBlanks for one pass
// over the pass lane (16 with time checks every 32 conditions went up to 26
// on hardware).
#define RPCPROBE_ACH_IDLE_DEAD 30
#define RPCPROBE_ACH_LINES_PER_VBLANK 20
#define RPCPROBE_ACH_SKIP_AFTER_LINES 40

// While an ARM9 ROM read is under way (nds-bootstrap's readOngoing; a game
// whose swiHalt couldn't be hooked has the ARM7 serve it from its IPC
// interrupt, a step each time the ARM9 pings), and for this many VBlanks
// after one was seen, the VBlank tick stays short so it doesn't hold the
// reads up: no checker turn, no frame-lane sample, and at most one frame
// from the Wi-Fi chip. 0 = off, now: Pokemon Black and White's slow battle
// loads, which this was for, turned out to come from the ARM9's VBlank hook,
// and the checker missed every frame it didn't sample.
#ifndef RPCPROBE_ROM_BUSY_VBLANKS // (a test build can set it with DSIRPC_CFLAGS)
#define RPCPROBE_ROM_BUSY_VBLANKS 0
#endif

// Unlocks are saved to sd:/RPCUNLK.BIN from nds-bootstrap's swiHalt hook
// (outside interrupts). If that hook hasn't run for this many VBlanks (a
// game whose swiHalt nds-bootstrap couldn't hook), the VBlank saves them
// instead, when nds-bootstrap's SD card lock is free. At most 255.
#define RPCPROBE_ACH_SAVE_FALLBACK 120

#endif // RPCPROBE_BUILD_H
