// probe_req.h - stage 5: answer memory read requests from the PC, over the
// DSi-mode chip the launcher left connected. See probe_req.c for the wire
// format.

#ifndef PROBE_REQ_H
#define PROBE_REQ_H

#include <nds/ndstypes.h>

// Counters, reported in the hello packets.
extern u16 probeReqRxFrames;   // packets drained from the chip (any kind)
extern u16 probeReqRequests;   // memory requests answered
extern u16 probeReqArpReplies; // ARP replies sent
extern u16 probeReqEapol;      // EAPOL frames seen (router key renewals)
extern u16 probeReqRepeats;    // requests the PC sent again (it didn't get the reply)

// Broadcast a gratuitous ARP so the PC learns our MAC right away. Call once
// when the handoff starts sending.
void ProbeReq_Announce(void);

// Drains part of at most one waiting packet from the chip
// (RPCPROBE_RX_BYTES_PER_VBLANK bytes), and handles it once it's complete
// (ARP request for our IP, or a memory request). Call once per VBlank.
// Returns 1 if it sent something (a reply) this call, else 0.
int ProbeReq_Service(void);

#endif // PROBE_REQ_H
