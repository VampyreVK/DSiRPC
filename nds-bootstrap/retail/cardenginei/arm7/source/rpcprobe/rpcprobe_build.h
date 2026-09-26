// rpcprobe_build.h - build-wide switches for rpcprobe. Every rpcprobe .c
// file that has a switch includes this, so it means the same thing everywhere.

#ifndef RPCPROBE_BUILD_H
#define RPCPROBE_BUILD_H

// 1 = answer memory read requests from the PC (probe_req.c).
// 0 = send hello packets only (handy for ruling the receive path out when
//     something goes wrong).
#define RPCPROBE_REQUESTS 1

// Most mailbox bytes the receive path reads in one VBlank. Every frame the
// chip receives (including other devices' broadcast traffic) has to be
// drained one CMD52 per byte, all inside the VBlank interrupt, and a single
// big frame used to take several milliseconds - enough to make the game
// stutter. Bigger frames are now drained over several VBlanks instead.
// Lower = smoother, higher = faster replies. The "vb=" field in the hello
// packets shows the longest VBlank tick, for tuning.
#define RPCPROBE_RX_BYTES_PER_VBLANK 128

#endif // RPCPROBE_BUILD_H
