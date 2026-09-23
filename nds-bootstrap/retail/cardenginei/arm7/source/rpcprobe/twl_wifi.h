// twl_wifi.h - minimal send/receive access to the DSi's own (Atheros) wifi
// chip, through a connection the DSiRPC launcher already made in DSi mode.
// Nothing here initializes, resets or configures the chip. See twl_wifi.c.

#ifndef TWL_WIFI_H
#define TWL_WIFI_H

#include <nds/ndstypes.h>

typedef struct {
	u16 revResp;      // raw R5 response for CCCR 0x00 (low byte = SDIO/CCCR revision)
	u16 ioEnableResp; // raw R5 response for CCCR 0x02 (bit 1 of low byte = function 1 enabled)
} TwlWifiProbeResult;

// Reads two SDIO card registers to check the chip is still powered, on the
// bus, and still set up the way the launcher left it (function 1 enabled).
// Returns 0 if both reads succeeded, negative on an SDIO error/timeout.
int TwlWifi_Probe(TwlWifiProbeResult *out);

// Sends one data frame through the chip, which does the 802.11 framing and
// WPA2 encryption itself. `llcFrame` starts at the LLC/SNAP header (what
// ProbeNet_BuildUdpFrame() produces). Returns 0 on success, 1 if the chip
// reported a TX mailbox overflow afterwards, negative on SDIO error.
int TwlWifi_SendLlcFrame(const u8 dstMac[6], const u8 srcMac[6], const u8 *llcFrame, u16 llcLen);

// Receive side (stage 5). Everything here is polled - nothing is set up to
// interrupt. See TWL_RX_NOTES.md for the chip-side details.

// 1 if the chip has a received packet waiting in its mailbox.
int TwlWifi_RxPending(void);

// Reads one waiting packet out of the chip's mailbox. The whole packet is
// always drained from the chip; bytes past `bufSize` are read and dropped.
// On success returns the packet's full mailbox length (header included) and
// fills `buf` with the start of it; returns 0 if nothing was waiting,
// negative on SDIO error. Layout of `buf` (see mbox_hdr_rx_data_packet in
// DSWiFi's common/common_twl_defs.h):
//   [0] type (2-5 = data)  [2..3] length (LE)  [6] RSSI
//   [8..13] dst MAC  [14..19] src MAC  [20..21] length (BE)
//   [22..27] LLC/SNAP  [28..29] ethertype (BE)  [30...] payload
int TwlWifi_ReadPacket(u8 *buf, u16 bufSize);

#endif // TWL_WIFI_H
