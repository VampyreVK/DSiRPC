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
// ProbeNet_BuildUdpFrame() produces). `fast` = 1 lets it go out with one
// CMD53 (while TwlWifi_TxMode() is 53); 0 always uses CMD52. Returns 0 on
// success, 1 if the chip reported a TX mailbox overflow afterwards,
// negative on SDIO error.
int TwlWifi_SendLlcFrame(const u8 dstMac[6], const u8 srcMac[6], const u8 *llcFrame, u16 llcLen, int fast);

// Receive side (stage 5). Everything here is polled - nothing is set up to
// interrupt. See TWL_RX_NOTES.md for the chip-side details.

// 1 if the chip has a received packet waiting in its mailbox.
int TwlWifi_RxPending(void);

// Reads a waiting packet out of the chip's mailbox. With CMD53 (see
// TwlWifi_RxMode) the whole packet comes out in one call. With CMD52 it's
// at most `budget` bytes per call (0 = no limit), so a big frame is drained
// over several calls (one per VBlank) instead of stalling one VBlank. The
// whole packet is always drained from the chip; bytes past `bufSize` are
// read and dropped.
// Returns the packet's full mailbox length (header included) on the call
// that finishes it, with `buf` holding the start of it. Returns 0 if
// nothing was waiting or the packet isn't finished yet, negative on SDIO
// error (the partial packet is abandoned). Layout of `buf` (see
// mbox_hdr_rx_data_packet in DSWiFi's common/common_twl_defs.h):
//   [0] type (2-5 = data)  [2..3] length (LE)  [6] RSSI
//   [8..13] dst MAC  [14..19] src MAC  [20..21] length (BE)
//   [22..27] LLC/SNAP  [28..29] ethertype (BE)  [30...] payload
int TwlWifi_ReadPacket(u8 *buf, u16 bufSize, u16 budget);

// 1 while a packet has been partly read. Don't send in the meantime.
int TwlWifi_RxBusy(void);

// How received packets are read: 53 = CMD53 block transfers, 52 = one CMD52
// per byte (RPCPROBE_RX_CMD53 off, or CMD53 failed CMD53_MAX_ERRORS times).
int TwlWifi_RxMode(void);

// CMD53 reads that failed (an SDIO error or timeout, or data that didn't
// match the packet's lookahead).
int TwlWifi_RxCmd53Errors(void);

// How frames are sent: 53 = CMD53 block transfers (for sends that allow
// it), 52 = one CMD52 per byte (RPCPROBE_TX_CMD53 off, CMD53 failed
// CMD53_MAX_ERRORS times, or TwlWifi_TxGiveUpCmd53() was called).
int TwlWifi_TxMode(void);

// CMD53 writes that failed (an SDIO error or timeout).
int TwlWifi_TxCmd53Errors(void);

// Sends with CMD52 from now on. For when frames sent with CMD53 look like
// they never arrive (the chip didn't complain, but the PC keeps asking).
void TwlWifi_TxGiveUpCmd53(void);

#endif // TWL_WIFI_H
