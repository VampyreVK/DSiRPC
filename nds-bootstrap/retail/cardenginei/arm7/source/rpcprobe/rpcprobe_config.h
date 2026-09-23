// rpcprobe_config.h - reads the two small text files the in-game side needs
// off the SD card root, once, on the first VBlank:
//
//   /RPCPROBE.CFG  - where to send packets: pc_ip=, port=, optional pc_mac=
//                    and dsi_ip= (overridden by the launcher's DHCP lease).
//   /RPCHAND.TXT   - written by the DSiRPC launcher after it connects: the
//                    DSi's MAC and IP.
//
// Both use nds-bootstrap's own ARM7-side FAT access (getBootFileCluster +
// fileRead from my_fat.h), the same calls cardengine.c uses for its debug
// log. That lookup only matches 8.3 names, hence the short file names.
#ifndef RPCPROBE_CONFIG_H
#define RPCPROBE_CONFIG_H

#include <nds/ndstypes.h>

typedef struct {
	u8   pcMac[6];
	u8   dsiIp[4];
	u8   pcIp[4];
	u16  udpPort;

	u8   valid; // 1 if RPCPROBE.CFG was found and has a usable pc_ip=
} RpcProbeConfig;

extern RpcProbeConfig rpcProbeConfig;

// Reads and parses /RPCPROBE.CFG. port= defaults to 4244 when missing. Keys
// this build doesn't use (for example old ssid=/wpa2_passphrase= lines) are
// ignored. Returns rpcProbeConfig.valid.
u8 RpcProbeConfig_Load(void);

// Connection details written by the DSiRPC launcher after it associates in
// DSi mode. The launcher owns the actual WPA2 connection; this is just what
// the in-game side needs to address its packets.
typedef struct {
	u8 dsiMac[6];
	u8 dsiIp[4];
	u8 gateway[4];
	u8 valid; // 1 if the file was found and had a usable mac= and ip=
} RpcProbeHandoff;

extern RpcProbeHandoff rpcProbeHandoff;

// Same SD access pattern as RpcProbeConfig_Load(). Stops parsing at a line
// reading "end" (the launcher writes one), since fileRead() can return
// leftover bytes past the file's real end. Returns rpcProbeHandoff.valid.
u8 RpcProbeHandoff_Load(void);

#endif
