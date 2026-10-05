// probe_hook.c - DSiRPC's in-game side. cardengine.c's myIrqHandlerVBlank()
// calls Probe_VBlankTick() once per VBlank for the whole game session.
//
// The DSiRPC launcher has already connected the DSi's wifi chip in DSi mode
// (WPA2 is handled by the chip). This file loads /RPCHAND.TXT, checks the
// chip still answers, then broadcasts a hello packet once a second (so the
// PC finds the DSi without any configuration) and, with RPCPROBE_REQUESTS,
// answers memory requests from the PC.
//
// SD card rule: the SD card is only touched on the very first VBlank (loading
// RPCHAND.TXT). After that the game's own ARM7 code reads its save from the
// SD card outside interrupts, and a VBlank that touches the SD card in the
// middle of that corrupts nds-bootstrap's SD/file state and hangs the game.
// Diagnostics after the first VBlank go into the hello packets instead.

#include <nds/ndstypes.h>
#include "debug_file.h"
#include "rpcprobe_build.h"
#include "twl_wifi.h"
#include "rpcprobe_config.h"
#include "probe_net.h"
#if RPCPROBE_REQUESTS
#include "probe_req.h"
#include "probe_watch.h"
#endif

// One-byte live status, readable with nds-bootstrap's in-game RAM viewer:
// bit 7 = set once running, bits 4-6 = stage (0 load, 1 probe, 2 sending,
// 3 failed, 4 waiting to restore DSi mode), bits 0-3 = packets sent (low 4 bits).
u8 probeStatusByte = 0;

#define HO_REG_GPIO_WIFI   (*(vu16*)0x04004C04) // bit 8 set = old DS wifi mode
#define HO_REG_VCOUNT      (*(vu16*)0x04000006) // current scanline, 0-262
#define HO_LINES_PER_FRAME 263
#define HO_TICKS_PER_STEP  60 // ~1 second between steps/packets
#define HO_MAX_SEND_FAILS  3
// nds-bootstrap is built with DSIRPC_KEEP_DSI_WIFI, so the board normally
// stays in DSi mode and the restore step passes straight through. If
// something did switch it to DS mode, wait until the game is past its boot
// (~15 steps) before switching back. Steps are ~1 second each.
#define HO_RESTORE_AFTER_STEPS 15

enum { HO_LOAD = 0, HO_PROBE = 1, HO_RUN = 2, HO_FAILED = 3, HO_RESTORE = 4 };

static u8 hoStage = HO_LOAD;
static u8 hoTimer = 0;
static u8 hoSendFails = 0;
static u8 hoRestoreSteps = 0;
static u16 hoGpio = 0;
static TwlWifiProbeResult hoProbe = { 0, 0 };
static int hoLastSend = 0;
static u16 hoSent = 0;
static const u8 hoBroadcastMac[6] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };
static u8 hoFrame[224];        // 36 bytes of headers + the hello text (at most 176)
static u16 hoTickMaxLines = 0; // longest Probe_VBlankTick() since the last hello, in scanlines

// Which game is running, from its NDS header, taken on the first tick (the
// bootloader has just written the header; a game can reuse that memory
// later). The hellos report it so the PC knows which game it is talking to.
static char hoGameCode[4] = { '?', '?', '?', '?' };
static u8 hoRomVersion = 0;
static u16 hoHeaderCrc = 0;

static void gameLoad(const u8 *hdr) {
	if (!hdr) return;
	for (int i = 0; i < 4; i++) {
		u8 c = hdr[0x0C + i];
		hoGameCode[i] = (c >= 0x20 && c < 0x7F) ? (char)c : '?';
	}
	hoRomVersion = hdr[0x1E];
	hoHeaderCrc = (u16)(hdr[0x15E] | (hdr[0x15F] << 8));
}

static int putDec(char *p, u16 v) {
	char tmp[5];
	int n = 0;
	do { tmp[n++] = (char)('0' + (v % 10)); v /= 10; } while (v);
	for (int i = 0; i < n; i++) p[i] = tmp[n - 1 - i];
	return n;
}

static int putHex(char *p, u32 v, int digits) {
	for (int i = digits - 1; i >= 0; i--) {
		u32 nib = v & 0xF;
		p[i] = (char)(nib < 10 ? '0' + nib : 'A' + nib - 10);
		v >>= 4;
	}
	return digits;
}

static int putStr(char *p, const char *str) {
	int n = 0;
	while (str[n]) { p[n] = str[n]; n++; }
	return n;
}

static void handoffLoad(void) {
	if (RpcProbeHandoff_Load()) {
		#ifdef DEBUG
		dbg_printf("rpcprobe: handoff ready, hellos will be broadcast\n");
		#endif
		hoStage = HO_RESTORE;
	} else {
		#ifdef DEBUG
		dbg_printf("rpcprobe: no usable RPCHAND.TXT, handoff off\n");
		#endif
		hoStage = HO_FAILED;
	}
}

static void handoffRestore(void) {
	if (!(HO_REG_GPIO_WIFI & 0x100)) {
		hoStage = HO_PROBE; // already in DSi mode, nothing to undo
		return;
	}
	if (++hoRestoreSteps < HO_RESTORE_AFTER_STEPS) return;

	HO_REG_GPIO_WIFI &= ~0x100;
	hoStage = HO_PROBE;
}

static void handoffProbe(void) {
	hoGpio = HO_REG_GPIO_WIFI;
	int r = TwlWifi_Probe(&hoProbe);
	hoStage = (r == 0) ? HO_RUN : HO_FAILED;
#if RPCPROBE_REQUESTS
	if (hoStage == HO_RUN) {
		ProbeReq_Announce();
		ProbeWatch_Init(); // find the ARM9 half of the per-frame capture
	}
#endif
}

static void handoffSend(void) {
	// "DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X gc=XXXX v=XX hc=XXXX"
	// plus, with requests on, " rx=N req=N arp=N eap=N rxm=N e53=N txm=N
	// t53=N rep=N a9=N", then " vb=N" - at most 169 bytes. Static rather than
	// on the stack: this runs on the game's ARM7 IRQ stack, which is small.
	static char msg[176];
	int n = 0;
	n += putStr(&msg[n], "DSiRPC hello #");
	n += putDec(&msg[n], hoSent);
	n += putStr(&msg[n], " gpio=");
	n += putHex(&msg[n], hoGpio, 4);
	n += putStr(&msg[n], " rev=");
	n += putHex(&msg[n], hoProbe.revResp & 0xFF, 2);
	n += putStr(&msg[n], " ioen=");
	n += putHex(&msg[n], hoProbe.ioEnableResp & 0xFF, 2);
	n += putStr(&msg[n], " last=");
	n += putHex(&msg[n], (u32)hoLastSend & 0xF, 1);
	// The game: its 4-letter code, ROM version and header CRC.
	n += putStr(&msg[n], " gc=");
	for (int i = 0; i < 4; i++) msg[n++] = hoGameCode[i];
	n += putStr(&msg[n], " v=");
	n += putHex(&msg[n], hoRomVersion, 2);
	n += putStr(&msg[n], " hc=");
	n += putHex(&msg[n], hoHeaderCrc, 4);
#if RPCPROBE_REQUESTS
	n += putStr(&msg[n], " rx=");
	n += putDec(&msg[n], probeReqRxFrames);
	n += putStr(&msg[n], " req=");
	n += putDec(&msg[n], probeReqRequests);
	n += putStr(&msg[n], " arp=");
	n += putDec(&msg[n], probeReqArpReplies);
	n += putStr(&msg[n], " eap=");
	n += putDec(&msg[n], probeReqEapol);
	n += putStr(&msg[n], " rxm=");
	n += putDec(&msg[n], (u16)TwlWifi_RxMode());
	n += putStr(&msg[n], " e53=");
	n += putDec(&msg[n], (u16)TwlWifi_RxCmd53Errors());
	n += putStr(&msg[n], " txm=");
	n += putDec(&msg[n], (u16)TwlWifi_TxMode());
	n += putStr(&msg[n], " t53=");
	n += putDec(&msg[n], (u16)TwlWifi_TxCmd53Errors());
	n += putStr(&msg[n], " rep=");
	n += putDec(&msg[n], probeReqRepeats);
	// The per-frame capture's ARM9 half: 0 = none, 1 = found, 2+ = its
	// VBlank hook is in (probe_watch.h).
	n += putStr(&msg[n], " a9=");
	n += putDec(&msg[n], probeWatchArm9);
#endif
	// Longest VBlank tick since the last hello, in scanlines (one is about
	// 64 us; a whole frame is 263). Big values mean rpcprobe is eating
	// enough ARM7 time to make the game stutter.
	n += putStr(&msg[n], " vb=");
	n += putDec(&msg[n], hoTickMaxLines);
	hoTickMaxLines = 0;

	u16 llcLen = (u16)ProbeNet_BuildUdpFrame(hoFrame, (const u8 *)msg, (u16)n);
	// Every RPCPROBE_HELLO_CMD52_EVERY-th hello (the first included) goes
	// out with CMD52, so the PC keeps hearing from the DSi even if CMD53
	// sends silently went nowhere.
	int fast = (hoSent % RPCPROBE_HELLO_CMD52_EVERY) != 0;
	int r = TwlWifi_SendLlcFrame(hoBroadcastMac, rpcProbeHandoff.dsiMac, hoFrame, llcLen, fast);
	hoLastSend = r;

	hoSent++;
	if (r < 0) {
		if (++hoSendFails >= HO_MAX_SEND_FAILS) hoStage = HO_FAILED;
	} else {
		hoSendFails = 0;
	}
}

void Probe_VBlankTick(const void *ndsHeader) {
	u16 lineStart = HO_REG_VCOUNT & 0x1FF;
	int sentThisTick = 0;
#if RPCPROBE_REQUESTS
	// Per-frame capture first, so every sample is taken at the same point
	// in the frame (and before anything else this tick costs time).
	if (hoStage == HO_RUN) ProbeWatch_Sample(lineStart);
	if (hoStage == HO_RUN) sentThisTick = ProbeReq_Service();
#endif
	if (hoStage == HO_LOAD && hoTimer == 0) gameLoad((const u8 *)ndsHeader);
	if (hoTimer) {
		hoTimer--;
	} else if (hoStage == HO_RUN && (sentThisTick || TwlWifi_RxBusy())) {
		// Keep each tick short: no hello in a tick that already sent a reply,
		// or while a packet is half read. Try again next VBlank.
	} else {
		hoTimer = HO_TICKS_PER_STEP;
		switch (hoStage) {
			case HO_LOAD:    handoffLoad();    break;
			case HO_RESTORE: handoffRestore(); break;
			case HO_PROBE:   handoffProbe();   break;
			case HO_RUN:     handoffSend();    break;
			default: break;
		}
	}

	probeStatusByte = 0x80 | (u8)(hoStage << 4) | (u8)(hoSent & 0x0F);

	u16 lineEnd = HO_REG_VCOUNT & 0x1FF;
	u16 lines = (lineEnd >= lineStart) ? lineEnd - lineStart
	                                   : lineEnd + HO_LINES_PER_FRAME - lineStart;
	if (lines > hoTickMaxLines) hoTickMaxLines = lines;
}
