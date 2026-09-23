// probe_net.h - hand-rolled LLC/SNAP + IPv4 + UDP framing for the packets the
// DSi sends to the PC (the hello packets). No DHCP, no fragmentation, no TCP:
// addresses and the port come from rpcprobe_config.h. Memory request replies
// are built in probe_req.c, which answers whoever sent the request.

#ifndef PROBE_NET_H
#define PROBE_NET_H

#include <nds/ndstypes.h>

// Writes the LLC/SNAP + IPv4 + UDP headers (DSi IP -> pc_ip=, port= on both
// ends) followed by `payload` into `out`. Returns the total number of bytes
// written (headers + payload). `out` must have room for 36 + payloadLen bytes.
int ProbeNet_BuildUdpFrame(u8 *out, const u8 *payload, u16 payloadLen);

#endif // PROBE_NET_H
