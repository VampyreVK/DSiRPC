// probe_req.c - see probe_req.h.
//
// Wire format (UDP port RPCPROBE_UDP_PORT, 4244, on the DSi's side):
//
//   Request  (PC -> DSi):  'R' | seq u16 | count u8 | count x (addr u32, len u8)
//   Response (DSi -> PC):  'D' | seq u16 | count u8 | status u8 | data...
//
// All multi-byte fields are big endian. `data` is the requested ranges
// back to back, in request order. Status: 0 = OK, 1 = malformed or too big
// (more than REQ_MAX_RANGES ranges or RESP_MAX_DATA bytes in total), 2 = a
// range falls outside main RAM. On a non-zero status no data follows.
//
// The reply goes back to whoever sent the request (IP, port and next-hop MAC
// taken from the request), not to a fixed address.

#include <nds/ndstypes.h>
#include <string.h>
#include "rpcprobe_build.h"

#if RPCPROBE_REQUESTS

#include "probe_req.h"
#include "twl_wifi.h"
#include "rpcprobe_config.h"

#define ETHERTYPE_IPV4  0x0800
#define ETHERTYPE_ARP   0x0806
#define ETHERTYPE_EAPOL 0x888E
#define IP_PROTO_UDP    17

// Main RAM (4 MB in DS mode). Anything outside is refused: the ARM7 has no
// MMU, so a bad read can hang the console.
#define MAINRAM_LO      0x02000000u
#define MAINRAM_HI      0x02400000u

#define REQ_MAX_RANGES  16
#define RESP_MAX_DATA   192

// Received packets: mailbox header (6) + data header (24) + payload. Big
// enough for ARP and for the largest valid request (IPv4 20 + UDP 8 +
// 4 + 16 x 5 = 112 payload bytes).
#define RX_BUF_SIZE     160

// LLC/SNAP (8) + IPv4 (20) + UDP (8) + response header (5) + data.
#define TX_FRAME_SIZE   (8 + 20 + 8 + 5 + RESP_MAX_DATA)

u16 probeReqRxFrames = 0;
u16 probeReqRequests = 0;
u16 probeReqArpReplies = 0;
u16 probeReqEapol = 0;

static u8 rxBuf[RX_BUF_SIZE] __attribute__((aligned(4)));
static u8 txFrame[TX_FRAME_SIZE] __attribute__((aligned(4)));

static const u8 broadcastMac[6] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };

static u16 get16(const u8 *p) { return (u16)((p[0] << 8) | p[1]); }
static u32 get32(const u8 *p) { return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3]; }
static void put16(u8 *p, u16 v) { p[0] = v >> 8; p[1] = v & 0xFF; }

static u16 checksum(const u8 *data, u32 len) {
	u32 sum = 0;
	while (len > 1) { sum += (data[0] << 8) | data[1]; data += 2; len -= 2; }
	if (len) sum += data[0] << 8;
	while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
	return (u16)~sum;
}

static void putLlc(u8 *p, u16 ethertype) {
	p[0] = 0xAA; p[1] = 0xAA; p[2] = 0x03;
	p[3] = 0x00; p[4] = 0x00; p[5] = 0x00;
	put16(&p[6], ethertype);
}

// ARP packet (28 bytes) after an LLC/SNAP header, then send.
static void sendArp(u16 op, const u8 dstMac[6], const u8 targetMac[6], const u8 targetIp[4]) {
	const u8 *myMac = rpcProbeHandoff.dsiMac;
	const u8 *myIp = rpcProbeHandoff.dsiIp;
	u8 *p = txFrame;
	putLlc(p, ETHERTYPE_ARP);
	u8 *a = p + 8;
	put16(&a[0], 1);              // hardware type: Ethernet
	put16(&a[2], ETHERTYPE_IPV4); // protocol type
	a[4] = 6; a[5] = 4;
	put16(&a[6], op);
	memcpy(&a[8], myMac, 6);
	memcpy(&a[14], myIp, 4);
	memcpy(&a[18], targetMac, 6);
	memcpy(&a[24], targetIp, 4);
	TwlWifi_SendLlcFrame(dstMac, myMac, txFrame, 8 + 28);
}

void ProbeReq_Announce(void) {
	// Gratuitous ARP: a request for our own IP, sent to everyone.
	static const u8 zeroMac[6] = { 0 };
	sendArp(1, broadcastMac, zeroMac, rpcProbeHandoff.dsiIp);
}

static void handleArp(const u8 *arp, int len) {
	if (len < 28) return;
	if (get16(&arp[6]) != 1) return;                         // not a request
	if (memcmp(&arp[24], rpcProbeHandoff.dsiIp, 4) != 0) return; // not for us
	sendArp(2, &arp[8], &arp[8], &arp[14]);
	probeReqArpReplies++;
}

// Builds LLC/SNAP + IPv4 + UDP headers around a payload already written at
// txFrame + 36, then sends it.
static void sendUdpReply(const u8 dstMac[6], const u8 dstIp[4], u16 dstPort, u16 payloadLen) {
	u8 *p = txFrame;
	putLlc(p, ETHERTYPE_IPV4);

	u8 *ip = p + 8;
	u16 udpLen = 8 + payloadLen;
	ip[0] = 0x45; ip[1] = 0x00;
	put16(&ip[2], 20 + udpLen);
	ip[4] = 0x00; ip[5] = 0x00;
	ip[6] = 0x40; ip[7] = 0x00; // don't fragment
	ip[8] = 64;
	ip[9] = IP_PROTO_UDP;
	ip[10] = 0; ip[11] = 0;
	memcpy(&ip[12], rpcProbeHandoff.dsiIp, 4);
	memcpy(&ip[16], dstIp, 4);
	put16(&ip[10], checksum(ip, 20));

	u8 *udp = ip + 20;
	put16(&udp[0], RPCPROBE_UDP_PORT);
	put16(&udp[2], dstPort);
	put16(&udp[4], udpLen);
	udp[6] = 0; udp[7] = 0; // no UDP checksum (valid for IPv4)

	TwlWifi_SendLlcFrame(dstMac, rpcProbeHandoff.dsiMac, txFrame, 8 + 20 + udpLen);
}

static void handleRequest(const u8 *srcMac, const u8 *srcIp, u16 srcPort, const u8 *req, int len) {
	if (len < 4 || req[0] != 'R') return;

	u8 *resp = txFrame + 8 + 20 + 8;
	resp[0] = 'D';
	resp[1] = req[1]; resp[2] = req[2]; // seq, echoed
	u8 count = req[3];
	resp[3] = count;

	u8 status = 0;
	u16 total = 0;
	if (count == 0 || count > REQ_MAX_RANGES || len < 4 + 5 * count) {
		status = 1;
	} else {
		for (int i = 0; i < count && status == 0; i++) {
			const u8 *r = &req[4 + 5 * i];
			u32 addr = get32(r);
			u8 n = r[4];
			if (n == 0 || total + n > RESP_MAX_DATA) status = 1;
			else if (addr < MAINRAM_LO || addr >= MAINRAM_HI || n > MAINRAM_HI - addr) status = 2;
			else total += n;
		}
	}
	resp[4] = status;

	u16 out = 5;
	if (status == 0) {
		for (int i = 0; i < count; i++) {
			const u8 *r = &req[4 + 5 * i];
			const u8 *src = (const u8 *)get32(r);
			u8 n = r[4];
			for (u8 k = 0; k < n; k++) resp[out + k] = src[k];
			out += n;
		}
	}

	sendUdpReply(srcMac, srcIp, srcPort, out);
	probeReqRequests++;
}

static void handleIpv4(const u8 *srcMac, const u8 *ip, int len) {
	if (len < 28) return;
	if ((ip[0] >> 4) != 4) return;
	int ihl = (ip[0] & 0x0F) * 4;
	if (ihl < 20 || ip[9] != IP_PROTO_UDP) return;
	if (memcmp(&ip[16], rpcProbeHandoff.dsiIp, 4) != 0) return;

	int ipLen = get16(&ip[2]);
	if (ipLen < len) len = ipLen;
	if (len < ihl + 8) return;

	const u8 *udp = ip + ihl;
	if (get16(&udp[2]) != RPCPROBE_UDP_PORT) return;
	int udpLen = get16(&udp[4]);
	if (udpLen < 8 || ihl + udpLen > len) return;

	handleRequest(srcMac, &ip[12], get16(&udp[0]), udp + 8, udpLen - 8);
}

void ProbeReq_Service(void) {
	int n = TwlWifi_ReadPacket(rxBuf, sizeof(rxBuf));
	if (n <= 0) return;
	probeReqRxFrames++;

	u8 type = rxBuf[0];
	if (type < 2 || type > 5) return; // chip control message, not data

	u16 len = rxBuf[2] | (rxBuf[3] << 8); // bytes after the 6-byte mailbox header
	if (rxBuf[1]) {                        // "ack present": trailer at the end
		u8 ackLen = rxBuf[4];
		if (ackLen < len) len -= ackLen;
	}
	if (len < 24) return;

	// Only what actually fit in rxBuf can be looked at.
	int avail = (n < RX_BUF_SIZE ? n : RX_BUF_SIZE) - 30;
	int payloadLen = len - 24;
	if (payloadLen > avail) payloadLen = avail;
	if (payloadLen <= 0) return;

	const u8 *srcMac = &rxBuf[14];
	const u8 *payload = &rxBuf[30];
	switch (get16(&rxBuf[28])) {
		case ETHERTYPE_ARP:   handleArp(payload, payloadLen); break;
		case ETHERTYPE_IPV4:  handleIpv4(srcMac, payload, payloadLen); break;
		case ETHERTYPE_EAPOL: probeReqEapol++; break;
		default: break;
	}
}

#endif // RPCPROBE_REQUESTS
