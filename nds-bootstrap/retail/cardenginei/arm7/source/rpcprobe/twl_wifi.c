// twl_wifi.c - see twl_wifi.h.
//
// Cut down from BlocksDS DSWiFi (MIT licensed): the polled command path of
// source/arm7/twl/sdio.twl.c, the byte-wise mailbox write path of
// card.twl.c (wifi_card_write_func_byte / wifi_card_mbox0_send_packet /
// wifi_card_mbox0_sendbytes), and mbox_hdr_tx_data_packet from
// common/common_twl_defs.h.
//
// Only CMD52 (one byte per SDIO command, polled) is used. That's slow - a
// small packet is ~128 commands - but it needs no DMA and no block-transfer
// state, so there's very little that can be left half-configured.

#include <nds/ndstypes.h>
#include <string.h>
#include "twl_wifi.h"

// DSi SDIO controller 2 (the wifi one; the SD card is controller 1).
#define TMIO2_BASE          0x04004A00u
#define SDIO_REG16(off)     (*(vu16 *)(TMIO2_BASE + (off)))

#define SDIO_CMD            0x000
#define SDIO_CMD_PARAM0     0x004
#define SDIO_CMD_PARAM1     0x006
#define SDIO_RESP0          0x00C
#define SDIO_IRQ_STAT0      0x01C
#define SDIO_IRQ_STAT1      0x01E

#define STAT0_CMDRESPEND    0x0001
#define STAT1_CMD_BUSY      0x4000
// ILL_ACCESS | CMDTIMEOUT | TXUNDERRUN | RXOVERFLOW | DATATIMEOUT |
// STOPBIT_ERR | CRCFAIL | CMD_IDX_ERR
#define STAT1_ERR_MASK      0x807F

// CMD52 (IO_RW_DIRECT), 48-bit response: cmd index 52 | response type 4 << 8
#define CMD52_RAW           0x0434

// Polling limit per command. Kept short on purpose: if the chip is gone we
// want to give up within a VBlank, not stall the game.
#define CMD_POLL_LIMIT      0x4000

// Function 1 addresses used by the mailbox path.
#define F1_HOST_INT_STATUS  0x400
#define F1_RX_LOOKAHEAD0    0x408
#define MBOX0_END           0x4000

// Mailbox packet: 6-byte mailbox header + 16 bytes of data header before
// the LLC/SNAP header. Rounded up to 0x80-byte blocks, like DSWiFi.
#define MBOX_TYPE_DATA      0x02
#define MBOX_NOACK          0x00
#define MBOX_FLAGS_DATA     0x2008 // what DSWiFi's normal IP data path uses
#define TX_BUF_SIZE         256

static u8 txBuf[TX_BUF_SIZE] __attribute__((aligned(4)));

static void sdioAck(void) {
	SDIO_REG16(SDIO_IRQ_STAT0) = 0;
	SDIO_REG16(SDIO_IRQ_STAT1) = 0;
}

static int cmd52(u32 args, u16 *resp) {
	u32 t = 0;
	while (SDIO_REG16(SDIO_IRQ_STAT1) & STAT1_CMD_BUSY) {
		if (++t > CMD_POLL_LIMIT) return -1;
	}

	sdioAck();
	SDIO_REG16(SDIO_CMD_PARAM0) = args & 0xFFFF;
	SDIO_REG16(SDIO_CMD_PARAM1) = args >> 16;
	SDIO_REG16(SDIO_CMD) = CMD52_RAW;

	t = 0;
	while (1) {
		u16 stat1 = SDIO_REG16(SDIO_IRQ_STAT1);
		if (stat1 & STAT1_ERR_MASK) {
			sdioAck();
			return -2;
		}
		if (!(stat1 & STAT1_CMD_BUSY) && (SDIO_REG16(SDIO_IRQ_STAT0) & STAT0_CMDRESPEND)) break;
		if (++t > CMD_POLL_LIMIT) {
			sdioAck();
			return -3;
		}
	}

	u16 r = SDIO_REG16(SDIO_RESP0);
	sdioAck();
	if (resp) *resp = r;
	return 0;
}

static int readByte(u32 func, u32 addr, u16 *resp) {
	return cmd52((func << 28) | ((addr & 0x1FFFF) << 9), resp);
}

static int writeByte(u32 func, u32 addr, u8 val) {
	return cmd52(BIT(31) | (func << 28) | ((addr & 0x1FFFF) << 9) | val, NULL);
}

int TwlWifi_Probe(TwlWifiProbeResult *out) {
	int r = readByte(0, 0x00, &out->revResp);
	if (r < 0) return r;
	return readByte(0, 0x02, &out->ioEnableResp);
}

int TwlWifi_SendLlcFrame(const u8 dstMac[6], const u8 srcMac[6], const u8 *llcFrame, u16 llcLen) {
	u16 dataLen = 16 + llcLen;
	u16 total = 6 + dataLen;
	u16 rounded = (total + 0x7F) & ~0x7F;
	if (rounded > TX_BUF_SIZE) return -10;

	u8 *p = txBuf;
	// Mailbox header
	p[0] = MBOX_TYPE_DATA;
	p[1] = MBOX_NOACK;
	p[2] = dataLen & 0xFF;
	p[3] = dataLen >> 8;
	p[4] = MBOX_FLAGS_DATA & 0xFF;
	p[5] = MBOX_FLAGS_DATA >> 8;
	// Data header (mbox_hdr_tx_data_packet, minus the LLC/ethertype, which
	// is already at the start of llcFrame)
	p[6] = 0;
	p[7] = 0;
	memcpy(&p[8], dstMac, 6);
	memcpy(&p[14], srcMac, 6);
	p[20] = llcLen >> 8; // big endian: length of everything after this field
	p[21] = llcLen & 0xFF;
	memcpy(&p[22], llcFrame, llcLen);
	memset(&p[total], 0, rounded - total);

	// Write the packet so its last byte lands on the last address of the
	// mailbox window - that's what tells the chip the message is complete.
	u32 addr = MBOX0_END - rounded;
	for (u16 i = 0; i < rounded; i++) {
		int r = writeByte(1, addr + i, p[i]);
		if (r < 0) return r;
	}

	// Bit 16 of HOST_INT_STATUS (bit 0 of its third byte) = TX overflow.
	u16 status = 0;
	if (readByte(1, F1_HOST_INT_STATUS + 2, &status) < 0) return -4;
	return (status & 0x01) ? 1 : 0;
}

int TwlWifi_RxPending(void) {
	u16 status = 0;
	if (readByte(1, F1_HOST_INT_STATUS, &status) < 0) return 0;
	return status & 0x01; // bit 0: mailbox 0 has data
}

int TwlWifi_ReadPacket(u8 *buf, u16 bufSize) {
	if (!TwlWifi_RxPending()) return 0;

	// Lookahead: byte 0 type, byte 1 ack present, bytes 2-3 length.
	u8 look[4];
	for (int i = 0; i < 4; i++) {
		u16 r = 0;
		if (readByte(1, F1_RX_LOOKAHEAD0 + i, &r) < 0) return -5;
		look[i] = r & 0xFF;
	}
	u16 len = look[2] | (look[3] << 8);
	if (len > 0x2000) return -6; // lookahead makes no sense; don't guess

	// Same mailbox window we write to: the packet is read as a run of
	// addresses ending on the last mailbox address (DSWiFi's block path,
	// wifi_card_mbox0_readbytes, reads 0x4000 - fullLen the same way).
	u16 fullLen = (len + 6 + 0x7F) & ~0x7F;
	u32 addr = MBOX0_END - fullLen;
	for (u16 i = 0; i < fullLen; i++) {
		u16 r = 0;
		if (readByte(1, addr + i, &r) < 0) return -7;
		if (i < bufSize) buf[i] = r & 0xFF;
	}
	return fullLen;
}
