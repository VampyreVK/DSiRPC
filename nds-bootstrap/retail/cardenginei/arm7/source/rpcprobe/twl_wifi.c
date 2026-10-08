// twl_wifi.c - see twl_wifi.h.
//
// Cut down from BlocksDS DSWiFi (MIT licensed): the polled command path of
// source/arm7/twl/sdio.twl.c, the byte-wise mailbox write path of
// card.twl.c (wifi_card_write_func_byte / wifi_card_mbox0_send_packet /
// wifi_card_mbox0_sendbytes), mbox_hdr_tx_data_packet from
// common/common_twl_defs.h, and for TwlWifi_Shutdown(), wmi_disconnect_cmd()
// and wifi_card_deinit().
//
// Packets are moved with CMD53 block transfers (RPCPROBE_RX_CMD53 and
// RPCPROBE_TX_CMD53, from the non-NDMA path of DSWiFi's
// wifi_sdio_send_command and its wifi_card_read_func1_block /
// wifi_card_write_func1_block): one command per packet, the data moved 32
// bits at a time through the controller's FIFO by the CPU (no NDMA, which
// nds-bootstrap uses for the SD card). The small register reads use CMD52
// (one byte per SDIO command, polled), and so does anything CMD53 can't do:
// if it fails, that direction falls back to CMD52 for good (see
// TwlWifi_RxMode / TwlWifi_TxMode).

#include <nds/ndstypes.h>
#include <string.h>
#include "rpcprobe_build.h"
#include "twl_wifi.h"

// DSi SDIO controller 2 (the wifi one; the SD card is controller 1).
#define TMIO2_BASE          0x04004A00u
#ifndef SDIO_REG16
#define SDIO_REG16(off)          (*(vu16 *)(TMIO2_BASE + (off)))
#define SDIO_FIFO32_READ()       (*(vu32 *)(TMIO2_BASE + SDIO_DATA32_FIFO))
#define SDIO_FIFO32_WRITE(v)     (*(vu32 *)(TMIO2_BASE + SDIO_DATA32_FIFO) = (v))
#endif

#define SDIO_CMD            0x000
#define SDIO_CMD_PARAM0     0x004
#define SDIO_CMD_PARAM1     0x006
#define SDIO_STOP           0x008
#define SDIO_BLK_CNT16      0x00A
#define SDIO_RESP0          0x00C
#define SDIO_IRQ_STAT0      0x01C
#define SDIO_IRQ_STAT1      0x01E
#define SDIO_BLK_LEN16      0x026
#define SDIO_DATA_CTL       0x0D8
#define SDIO_IRQ32          0x100
#define SDIO_BLK_LEN32      0x104
#define SDIO_BLK_CNT32      0x108
#define SDIO_DATA32_FIFO    0x10C

#define STAT0_CMDRESPEND    0x0001
#define STAT0_DATAEND       0x0004
#define STAT1_RXRDY         0x0100
#define STAT1_TXRQ          0x0200
#define STAT1_CMD_BUSY      0x4000
// ILL_ACCESS | CMDTIMEOUT | TXUNDERRUN | RXOVERFLOW | DATATIMEOUT |
// STOPBIT_ERR | CRCFAIL | CMD_IDX_ERR
#define STAT1_ERR_MASK      0x807F

// CMD52 (IO_RW_DIRECT), 48-bit response: cmd index 52 | response type 4 << 8
#define CMD52_RAW           0x0434
// CMD53 (IO_RW_EXTENDED) block read, as DSWiFi's cmd53_read: cmd index 53 |
// 48-bit response (4 << 8) | data (bit 11) | read (bit 12) | multiple blocks
// (bit 13) | bit 14 ("secure", set by DSWiFi for every CMD53).
#define CMD53_READ_RAW      0x7C35
// ... and block write, as DSWiFi's cmd53_write: the same without bit 12.
#define CMD53_WRITE_RAW     0x6C35

// SD_DATA32_IRQ: bit 1 = 32-bit FIFO, bit 8 = a block is waiting in the FIFO
// (read only), bit 10 = clear the FIFO, bit 11 = enable that as an IRQ.
// 0x0C02 is what DSWiFi writes before a block read, 0x1402 before a block
// write (bit 12 = FIFO-has-room IRQ enable), 0x0402 its idle value.
#define IRQ32_BLOCK_READY   0x0100
#define IRQ32_READ          0x0C02
#define IRQ32_WRITE         0x1402
#define IRQ32_IDLE          0x0402
// SD_STOP_INTERNAL_ACTION as DSWiFi's wifi_sdio_stop() sets it.
#define STOP_VALUE          0x0100
// The mailbox block size DSWiFi set for function 1 when the launcher
// brought the chip up (and the size every mailbox packet is rounded to).
#define MBOX_BLOCK          0x80

// Polling limit per command. Kept short on purpose: if the chip is gone we
// want to give up within a VBlank, not stall the game.
#define CMD_POLL_LIMIT      0x4000

// Function 1 addresses used by the mailbox path.
#define F1_HOST_INT_STATUS  0x400
#define F1_RX_LOOKAHEAD0    0x408
#define MBOX0_END           0x4000

// Used by TwlWifi_Shutdown() only. The chip's four interrupt enable bytes
// (host, CPU, error, counter; DSWiFi's F1_INT_STATUS_ENABLE), the CCCR's
// Int Enable register, and the controller's card interrupt registers
// (DSWiFi's WIFI_SDIO_OFFS_CARDIRQ_CTL / _MASK).
#define F1_INT_STATUS_ENABLE 0x418
#define CCCR_INT_ENABLE     0x04
#define SDIO_CARDIRQ_CTL    0x034
#define SDIO_CARDIRQ_MASK   0x038
// A WMI command: mailbox endpoint 1, with an ack asked for, as DSWiFi's
// wmi_send_pkt() sends them. WMI_DISCONNECT_CMD has no parameters.
#define MBOX_TYPE_WMI       0x01
#define MBOX_REQACK         0x01
#define WMI_DISCONNECT_CMD  0x0003

// Mailbox packet: 6-byte mailbox header + 16 bytes of data header before
// the LLC/SNAP header. Rounded up to 0x80-byte blocks, like DSWiFi.
#define MBOX_TYPE_DATA      0x02
#define MBOX_NOACK          0x00
#define MBOX_FLAGS_DATA     0x2008 // what DSWiFi's normal IP data path uses
#define TX_BUF_SIZE         256

static u8 txBuf[TX_BUF_SIZE] __attribute__((aligned(4)));

// Receive state, so a packet can be drained across several calls.
static u8  rxActive = 0;   // 1 while a packet is partly read
static u16 rxFullLen = 0;  // its mailbox length, rounded to 0x80
static u16 rxPos = 0;      // bytes read so far
static u8  rxLook[4];      // its lookahead (mailbox header bytes 0-3)

// 53 while received packets are read with CMD53, 52 once that's off (the
// build switch) or has failed CMD53_MAX_ERRORS times.
static u8  rxMode = RPCPROBE_RX_CMD53 ? 53 : 52;
static u16 rxCmd53Errors = 0;
#define CMD53_MAX_ERRORS    3

// The same for sending.
static u8  txMode = RPCPROBE_TX_CMD53 ? 53 : 52;
static u16 txCmd53Errors = 0;

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

// Reads `blocks` mailbox blocks ending at MBOX0_END with one CMD53. The
// first `bufSize` bytes go to `buf`, the rest are read and dropped.
// Returns 0 on success, negative on error; `*done` is the number of blocks
// that came across either way.
static int cmd53ReadBlocks(u16 blocks, u8 *buf, u16 bufSize, u16 *done) {
	*done = 0;
	u32 t = 0;
	while (SDIO_REG16(SDIO_IRQ_STAT1) & STAT1_CMD_BUSY) {
		if (++t > CMD_POLL_LIMIT) return -1;
	}

	u32 addr = MBOX0_END - blocks * MBOX_BLOCK;
	// Function 1, block mode (bit 27), incrementing address (bit 26).
	u32 args = (1u << 28) | (1u << 27) | (1u << 26) | ((addr & 0x1FFFF) << 9) | blocks;
	SDIO_REG16(SDIO_STOP) = STOP_VALUE;
	sdioAck();
	SDIO_REG16(SDIO_CMD_PARAM0) = args & 0xFFFF;
	SDIO_REG16(SDIO_CMD_PARAM1) = args >> 16;
	SDIO_REG16(SDIO_BLK_LEN16) = MBOX_BLOCK;
	SDIO_REG16(SDIO_BLK_CNT16) = blocks;
	SDIO_REG16(SDIO_BLK_LEN32) = MBOX_BLOCK;
	SDIO_REG16(SDIO_BLK_CNT32) = blocks;
	SDIO_REG16(SDIO_DATA_CTL) = 0x0002; // 32-bit data
	SDIO_REG16(SDIO_IRQ32) = IRQ32_READ;
	SDIO_REG16(SDIO_CMD) = CMD53_READ_RAW;

	u16 got = 0;
	int result = -3; // timed out
	t = 0;
	while (1) {
		u16 stat1 = SDIO_REG16(SDIO_IRQ_STAT1);
		if (stat1 & STAT1_ERR_MASK) {
			result = -2;
			break;
		}
		if (*done < blocks && (SDIO_REG16(SDIO_IRQ32) & IRQ32_BLOCK_READY)) {
			SDIO_REG16(SDIO_IRQ_STAT1) = SDIO_REG16(SDIO_IRQ_STAT1) & ~STAT1_RXRDY;
			for (int i = 0; i < MBOX_BLOCK / 4; i++) {
				u32 w = SDIO_FIFO32_READ();
				for (int k = 0; k < 4; k++, got++) {
					if (got < bufSize) buf[got] = (u8)(w >> (8 * k));
				}
			}
			(*done)++;
			t = 0;
		}
		if (*done == blocks) {
			u16 want = STAT0_CMDRESPEND | STAT0_DATAEND;
			if ((SDIO_REG16(SDIO_IRQ_STAT0) & want) == want) {
				result = 0;
				break;
			}
		}
		if (++t > CMD_POLL_LIMIT) break;
	}

	sdioAck();
	SDIO_REG16(SDIO_STOP) = STOP_VALUE;
	SDIO_REG16(SDIO_IRQ32) = IRQ32_IDLE; // FIFO emptied, its IRQ off again
	if (result < 0) {
		// End whatever the card thinks is still going: the SDIO way to
		// abort a function's transfer is writing its number to the CCCR's
		// I/O Abort register (0x06).
		writeByte(0, 0x06, 1);
	}
	return result;
}

// Writes `blocks` mailbox blocks from `buf` (4-byte aligned) with one CMD53,
// ending at MBOX0_END. Returns 0 on success, negative on error; `*done` is
// the number of blocks that went out either way.
static int cmd53WriteBlocks(const u8 *buf, u16 blocks, u16 *done) {
	*done = 0;
	u32 t = 0;
	while (SDIO_REG16(SDIO_IRQ_STAT1) & STAT1_CMD_BUSY) {
		if (++t > CMD_POLL_LIMIT) return -1;
	}

	u32 addr = MBOX0_END - blocks * MBOX_BLOCK;
	// Write (bit 31), function 1, block mode, incrementing address.
	u32 args = BIT(31) | (1u << 28) | (1u << 27) | (1u << 26) | ((addr & 0x1FFFF) << 9) | blocks;
	SDIO_REG16(SDIO_STOP) = STOP_VALUE;
	sdioAck();
	SDIO_REG16(SDIO_CMD_PARAM0) = args & 0xFFFF;
	SDIO_REG16(SDIO_CMD_PARAM1) = args >> 16;
	SDIO_REG16(SDIO_BLK_LEN16) = MBOX_BLOCK;
	SDIO_REG16(SDIO_BLK_CNT16) = blocks;
	SDIO_REG16(SDIO_BLK_LEN32) = MBOX_BLOCK;
	SDIO_REG16(SDIO_BLK_CNT32) = blocks;
	SDIO_REG16(SDIO_DATA_CTL) = 0x0002; // 32-bit data
	SDIO_REG16(SDIO_IRQ32) = IRQ32_WRITE;
	SDIO_REG16(SDIO_CMD) = CMD53_WRITE_RAW;

	const u32 *w = (const u32 *)buf;
	int result = -3; // timed out
	t = 0;
	while (1) {
		u16 stat1 = SDIO_REG16(SDIO_IRQ_STAT1);
		if (stat1 & STAT1_ERR_MASK) {
			result = -2;
			break;
		}
		// The controller asks for each block with TXRQ.
		if (*done < blocks && (stat1 & STAT1_TXRQ)) {
			SDIO_REG16(SDIO_IRQ_STAT1) = SDIO_REG16(SDIO_IRQ_STAT1) & ~STAT1_TXRQ;
			for (int i = 0; i < MBOX_BLOCK / 4; i++) SDIO_FIFO32_WRITE(*w++);
			(*done)++;
			t = 0;
		}
		if (*done == blocks) {
			u16 want = STAT0_CMDRESPEND | STAT0_DATAEND;
			if ((SDIO_REG16(SDIO_IRQ_STAT0) & want) == want) {
				result = 0;
				break;
			}
		}
		if (++t > CMD_POLL_LIMIT) break;
	}

	sdioAck();
	SDIO_REG16(SDIO_STOP) = STOP_VALUE;
	SDIO_REG16(SDIO_IRQ32) = IRQ32_IDLE;
	if (result < 0) writeByte(0, 0x06, 1); // I/O Abort, function 1
	return result;
}

// Writes a mailbox message (`rounded` bytes, a multiple of MBOX_BLOCK) so
// its last byte lands on the last address of the mailbox window - that's
// what tells the chip the message is complete. `fast` = 1 lets it go out
// with one CMD53 (while txMode is 53). Returns 0 on success, negative on
// SDIO error.
static int mboxWrite(const u8 *p, u16 rounded, int fast) {
	int sent = 0;
#if RPCPROBE_TX_CMD53
	if (fast && txMode == 53) {
		u16 done = 0;
		int r = cmd53WriteBlocks(p, rounded / MBOX_BLOCK, &done);
		if (r == 0) {
			sent = 1;
		} else {
			if (++txCmd53Errors >= CMD53_MAX_ERRORS) txMode = 52;
			// Part of it went out: the chip has a broken message, so don't
			// send it again on top. Nothing went out: send it byte by byte.
			if (done) return r;
		}
	}
#else
	(void)fast;
#endif
	if (!sent) {
		u32 addr = MBOX0_END - rounded;
		for (u16 i = 0; i < rounded; i++) {
			int r = writeByte(1, addr + i, p[i]);
			if (r < 0) return r;
		}
	}
	return 0;
}

int TwlWifi_Probe(TwlWifiProbeResult *out) {
	int r = readByte(0, 0x00, &out->revResp);
	if (r < 0) return r;
	return readByte(0, 0x02, &out->ioEnableResp);
}

int TwlWifi_SendLlcFrame(const u8 dstMac[6], const u8 srcMac[6], const u8 *llcFrame, u16 llcLen, int fast) {
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

	int r = mboxWrite(p, rounded, fast);
	if (r < 0) return r;

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

int TwlWifi_RxBusy(void) {
	return rxActive;
}

int TwlWifi_RxMode(void) {
	return rxMode;
}

int TwlWifi_RxCmd53Errors(void) {
	return rxCmd53Errors;
}

int TwlWifi_TxMode(void) {
	return txMode;
}

int TwlWifi_TxCmd53Errors(void) {
	return txCmd53Errors;
}

void TwlWifi_TxGiveUpCmd53(void) {
	txMode = 52;
}

int TwlWifi_Shutdown(void) {
	rxActive = 0; // a half-read packet is left in the chip

	// WMI_DISCONNECT_CMD, as DSWiFi's wmi_disconnect_cmd(): the mailbox
	// header (2 bytes long), then the command's id. Sent with CMD52, the
	// slow but surest way, since it only happens once.
	u8 *p = txBuf;
	memset(p, 0, MBOX_BLOCK);
	p[0] = MBOX_TYPE_WMI;
	p[1] = MBOX_REQACK;
	p[2] = 2;
	p[6] = WMI_DISCONNECT_CMD & 0xFF;
	p[7] = WMI_DISCONNECT_CMD >> 8;
	int r = mboxWrite(p, MBOX_BLOCK, 0);

	// Then what DSWiFi's wifi_card_deinit() does: the controller's card
	// interrupt off, then the chip's interrupts
	SDIO_REG16(SDIO_CARDIRQ_CTL) &= ~0x0001;
	SDIO_REG16(SDIO_CARDIRQ_MASK) |= 0x0003;
	for (int i = 0; i < 4 && r >= 0; i++) r = writeByte(1, F1_INT_STATUS_ENABLE + i, 0);
	if (r >= 0) r = writeByte(0, CCCR_INT_ENABLE, 0);
	return r;
}

int TwlWifi_ReadPacket(u8 *buf, u16 bufSize, u16 budget) {
	if (!rxActive) {
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

		rxFullLen = (len + 6 + 0x7F) & ~0x7F;
		rxPos = 0;
		rxActive = 1;
		memcpy(rxLook, look, 4);
	}

#if RPCPROBE_RX_CMD53
	// The whole packet in one CMD53. Its first 4 bytes must repeat the
	// lookahead; anything else means the transfer can't be trusted.
	if (rxMode == 53 && rxPos == 0) {
		u16 done = 0;
		int r = cmd53ReadBlocks(rxFullLen / MBOX_BLOCK, buf, bufSize, &done);
		if (r == 0 && bufSize >= 4 && memcmp(buf, rxLook, 4) == 0) {
			rxActive = 0;
			return rxFullLen;
		}
		if (++rxCmd53Errors >= CMD53_MAX_ERRORS) rxMode = 52;
		if (r == 0 || done) {
			// Some or all of the packet came across, wrong: it's gone.
			rxActive = 0;
			return -8;
		}
		// Nothing came across: read this one byte by byte below.
	}
#endif

	// Same mailbox window we write to: the packet is read as a run of
	// addresses ending on the last mailbox address (DSWiFi's block path,
	// wifi_card_mbox0_readbytes, reads 0x4000 - fullLen the same way). The
	// chip only treats the message as consumed once that last address is
	// read, so the run can be split across calls.
	u32 addr = MBOX0_END - rxFullLen;
	u16 stop = rxFullLen;
	if (budget && rxFullLen - rxPos > budget) stop = rxPos + budget;
	for (; rxPos < stop; rxPos++) {
		u16 r = 0;
		if (readByte(1, addr + rxPos, &r) < 0) {
			rxActive = 0;
			return -7;
		}
		if (rxPos < bufSize) buf[rxPos] = r & 0xFF;
	}
	if (rxPos < rxFullLen) return 0; // more next time

	rxActive = 0;
	return rxFullLen;
}
