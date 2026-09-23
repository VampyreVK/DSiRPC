// probe_net.c - see probe_net.h.

#include <nds/ndstypes.h>
#include "probe_net.h"
#include "rpcprobe_config.h"

#define ETHERTYPE_IPV4   0x0800
#define IP_PROTO_UDP     17

static u16 internetChecksum(const u8 *data, u32 len, u32 initial) {
	u32 sum = initial;
	while (len > 1) { sum += (data[0] << 8) | data[1]; data += 2; len -= 2; }
	if (len) sum += data[0] << 8;
	while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
	return (u16)~sum;
}

int ProbeNet_BuildUdpFrame(u8 *out, const u8 *payload, u16 payloadLen) {
	const u8 *dsiIp = rpcProbeHandoff.dsiIp;

	u8 *llc = out;
	llc[0] = 0xAA; llc[1] = 0xAA; llc[2] = 0x03;
	llc[3] = 0x00; llc[4] = 0x00; llc[5] = 0x00;
	llc[6] = (ETHERTYPE_IPV4 >> 8) & 0xFF; llc[7] = ETHERTYPE_IPV4 & 0xFF;

	u8 *ip = llc + 8;
	u16 udpTotalLen = 8 + payloadLen;
	u16 ipTotalLen = 20 + udpTotalLen;
	ip[0] = 0x45; ip[1] = 0x00;
	ip[2] = (ipTotalLen >> 8) & 0xFF; ip[3] = ipTotalLen & 0xFF;
	ip[4] = 0x00; ip[5] = 0x00; // identification - fine to leave at 0, we never fragment
	ip[6] = 0x40; ip[7] = 0x00; // flags=don't-fragment, frag offset 0
	ip[8] = 64;                  // TTL
	ip[9] = IP_PROTO_UDP;
	ip[10] = 0; ip[11] = 0;      // checksum, filled below
	ip[12] = dsiIp[0]; ip[13] = dsiIp[1]; ip[14] = dsiIp[2]; ip[15] = dsiIp[3];
	ip[16] = 0xFF; ip[17] = 0xFF; ip[18] = 0xFF; ip[19] = 0xFF; // broadcast
	u16 ipChecksum = internetChecksum(ip, 20, 0);
	ip[10] = (ipChecksum >> 8) & 0xFF; ip[11] = ipChecksum & 0xFF;

	u8 *udp = ip + 20;
	udp[0] = (RPCPROBE_UDP_PORT >> 8) & 0xFF; udp[1] = RPCPROBE_UDP_PORT & 0xFF; // src port
	udp[2] = (RPCPROBE_UDP_PORT >> 8) & 0xFF; udp[3] = RPCPROBE_UDP_PORT & 0xFF; // dst port (same port both ends)
	udp[4] = (udpTotalLen >> 8) & 0xFF; udp[5] = udpTotalLen & 0xFF;
	udp[6] = 0; udp[7] = 0; // checksum - 0 is valid/"unused" for UDP over IPv4

	u8 *body = udp + 8;
	for (u16 i = 0; i < payloadLen; i++) body[i] = payload[i];

	return 8 + 20 + 8 + payloadLen;
}
