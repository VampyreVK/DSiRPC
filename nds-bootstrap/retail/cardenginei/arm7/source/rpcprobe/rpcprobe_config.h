// rpcprobe_config.h - reads /RPCHAND.TXT off the SD card root, once, on the
// first VBlank. The DSiRPC launcher writes that file before it starts a game:
// the DSi's MAC and IP (online only) and the console's clock (time=, which
// dates offline unlocks). Nothing else is configured on the SD card: hellos are
// broadcast, so the DSi doesn't need to know the PC's address, and memory
// replies go back to whoever sent the request.
//
// It uses nds-bootstrap's own ARM7-side FAT access (getBootFileCluster +
// fileRead from my_fat.h), the same calls cardengine.c uses for its debug
// log. That lookup only matches 8.3 names, hence the short file name.
#ifndef RPCPROBE_CONFIG_H
#define RPCPROBE_CONFIG_H

#include <nds/ndstypes.h>

// UDP port for everything: the hellos, the PC's memory requests and the
// replies. The PC tools use the same port.
#define RPCPROBE_UDP_PORT 4244

// Connection details written by the DSiRPC launcher after it associates in
// DSi mode. The launcher owns the actual WPA2 connection; this is just what
// the in-game side needs to address its packets.
typedef struct {
	u8 dsiMac[6];
	u8 dsiIp[4];
	u8 gateway[4];
	u8 valid; // 1 if the file was found and had a usable mac= and ip=
	u32 time; // time=: the console's clock at the handoff, seconds since 2000 (0 = none)
} RpcProbeHandoff;

extern RpcProbeHandoff rpcProbeHandoff;

// Stops parsing at a line reading "end" (the launcher writes one), since
// fileRead() can return leftover bytes past the file's real end. Returns
// rpcProbeHandoff.valid.
u8 RpcProbeHandoff_Load(void);

#endif
