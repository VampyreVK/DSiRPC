// probe_hook.c - DSiRPC's in-game side. cardengine.c's myIrqHandlerVBlank()
// calls Probe_VBlankTick() once per VBlank for the whole game session.
//
// The DSiRPC launcher has already connected the DSi's wifi chip in DSi mode
// (WPA2 is handled by the chip). This file loads /RPCPROBE.CFG and
// /RPCHAND.TXT, checks the chip still answers, then sends a hello packet once
// a second and (with RPCPROBE_REQUESTS) answers memory requests from the PC.
//
// SD card rule: the SD card is only touched on the very first VBlank (loading
// the two files). After that the game's own ARM7 code reads its save from the
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
#endif

// One-byte live status, readable with nds-bootstrap's in-game RAM viewer:
// bit 7 = set once running, bits 4-6 = stage (0 load, 1 probe, 2 sending,
// 3 failed, 4 waiting to restore DSi mode), bits 0-3 = packets sent (low 4 bits).
u8 probeStatusByte = 0;

#define HO_REG_GPIO_WIFI   (*(vu16*)0x04004C04) // bit 8 set = old DS wifi mode
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
static u8 hoDstMac[6];
static u8 hoFrame[136];

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
	u8 cfgOk = RpcProbeConfig_Load();
	u8 hoOk = RpcProbeHandoff_Load();
	if (cfgOk && hoOk) {
		// The launcher's DHCP lease wins over the static dsi_ip= in the cfg.
		for (int i = 0; i < 4; i++) rpcProbeConfig.dsiIp[i] = rpcProbeHandoff.dsiIp[i];

		// pc_mac= if set, otherwise broadcast (the PC still only accepts it
		// because the IP destination is pc_ip=).
		u8 havePcMac = 0;
		for (int i = 0; i < 6; i++) if (rpcProbeConfig.pcMac[i]) havePcMac = 1;
		for (int i = 0; i < 6; i++) hoDstMac[i] = havePcMac ? rpcProbeConfig.pcMac[i] : 0xFF;

		#ifdef DEBUG
		dbg_printf(havePcMac ? "rpcprobe: handoff ready, sending to pc_mac\n"
		                     : "rpcprobe: handoff ready, no pc_mac, using broadcast\n");
		#endif
		hoStage = HO_RESTORE;
	} else {
		#ifdef DEBUG
		dbg_printf("rpcprobe: config/handoff files missing, handoff off\n");
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
	if (hoStage == HO_RUN) ProbeReq_Announce();
#endif
}

static void handoffSend(void) {
	// "DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X" plus, with requests
	// on, " rx=N req=N arp=N eap=N" - at most 96 bytes.
	char msg[96];
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
#if RPCPROBE_REQUESTS
	n += putStr(&msg[n], " rx=");
	n += putDec(&msg[n], probeReqRxFrames);
	n += putStr(&msg[n], " req=");
	n += putDec(&msg[n], probeReqRequests);
	n += putStr(&msg[n], " arp=");
	n += putDec(&msg[n], probeReqArpReplies);
	n += putStr(&msg[n], " eap=");
	n += putDec(&msg[n], probeReqEapol);
#endif

	u16 llcLen = (u16)ProbeNet_BuildUdpFrame(hoFrame, (const u8 *)msg, (u16)n);
	int r = TwlWifi_SendLlcFrame(hoDstMac, rpcProbeHandoff.dsiMac, hoFrame, llcLen);
	hoLastSend = r;

	hoSent++;
	if (r < 0) {
		if (++hoSendFails >= HO_MAX_SEND_FAILS) hoStage = HO_FAILED;
	} else {
		hoSendFails = 0;
	}
}

void Probe_VBlankTick(void) {
#if RPCPROBE_REQUESTS
	if (hoStage == HO_RUN) ProbeReq_Service();
#endif
	if (hoTimer) {
		hoTimer--;
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
}
