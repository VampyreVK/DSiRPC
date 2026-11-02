// probe_hook.c - DSiRPC's in-game side. cardengine.c's myIrqHandlerVBlank()
// calls Probe_VBlankTick() once per VBlank for the whole game session, and
// its swiHalt hook calls Probe_HaltTick() whenever the game's ARM7 idles
// (where the achievement checker does its checking).
//
// The DSiRPC launcher has already connected the DSi's wifi chip in DSi mode
// (WPA2 is handled by the chip). This file loads /RPCHAND.TXT, checks the
// chip still answers, then broadcasts a hello packet once a second (so the
// PC finds the DSi without any configuration) and, with RPCPROBE_REQUESTS,
// answers memory requests from the PC. With RPCPROBE_ACH it also runs the
// achievement checker for offline play (probe_ach.c), Wi-Fi or not, and
// saves its unlocks to the SD card.
//
// SD card rule: the VBlank only reads the SD card on the very first VBlank
// (RPCHAND.TXT, RPCSET.BIN and RPCUNLK.BIN). After that the game's own ARM7
// code reads its save and ROM from the SD card outside interrupts, and a
// VBlank that touches the SD card in the middle of that corrupts
// nds-bootstrap's SD/file state and hangs the game. Diagnostics after the
// first VBlank go into the hello packets instead. The one later SD access,
// saving the achievement checker's unlocks, happens in Probe_HaltTick()
// (outside interrupts) and only while it holds nds-bootstrap's SD card lock
// (saveMutex), which its save and ROM reads take too. Only for a game whose
// swiHalt nds-bootstrap couldn't hook, or one whose ROM reads it serves from
// the IPC interrupt (altReadMethod: they may come in the middle of the
// hook), does the VBlank save them, with the same lock and only when no ROM
// read is under way.
//
// Lid rule: a DSi that goes to sleep (the game's own sleep when the lid
// closes) while the Wi-Fi chip is still connected to the access point shuts
// off instead; one whose launcher went offline sleeps fine, and so does a
// 3DS. So on a DSi, as soon as the lid closes, rpcprobe sends DSiRPC a
// "DSiRPC lid" packet, turns the connection off the way the launcher does
// when it goes offline (TwlWifi_Shutdown(), a few SDIO commands), then
// switches the chip's SDIO power off (ProbeLed_WifiPowerOff()), all before
// the game gets to its sleep, and stays off the Wi-Fi for the rest of the
// game. The checker and its saves carry on, so it's offline play from then
// on: unlocks are sent at the next sync.
//
// Unless the launcher's "Lid closed: Stay connected" is on
// (DSIRPC_STAY_CONNECTED in nds-bootstrap.ini, rpcFlags bit 0): then the
// bootloader points the game's ARM7 SVC_Sleep at Probe_SleepWait(), so the
// game pauses and turns its screens and sound off as it sleeps, but instead
// of the console sleeping, rpcprobe waits awake for the lid to open, the
// Wi-Fi still connected ("DSiRPC lid pause"), and the game carries on.
// Where that call can't be found, nds-bootstrap's sleep mode is off instead:
// the game carries on with the lid closed, as a Wi-Fi game does, and the lid
// turns the screens' backlights and the volume off until it opens
// (Probe_LidDark()).
//
// Achievement LED: while achievements unlocked this game haven't been seen
// in nds-bootstrap's in-game menu yet, the LED of TWiLight's "ROM read LED"
// setting pulses (probe_led.c). Opening the menu counts as seeing them.

#include <nds/ndstypes.h>
#include <nds/arm7/i2c.h>
#include "debug_file.h"
#include "rpcprobe_build.h"
#include "twl_wifi.h"
#include "rpcprobe_config.h"
#include "probe_net.h"
#include "probe_led.h"
#if RPCPROBE_REQUESTS
#include "probe_req.h"
#include "probe_watch.h"
#endif
#if RPCPROBE_ACH
#include "probe_ach.h"
#endif

extern void swiDelay(u32 duration); // the BIOS's WaitByLoop: 4 cycles a count
// One-byte live status, readable with nds-bootstrap's in-game RAM viewer:
// bit 7 = set once running, bits 4-6 = stage (0 load, 1 probe, 2 sending,
// 3 failed, 4 waiting to restore DSi mode, 5 Wi-Fi off: the lid closed),
// bits 0-3 = packets sent (low 4 bits).
u8 probeStatusByte = 0;

#define HO_REG_GPIO_WIFI   (*(vu16*)0x04004C04) // bit 8 set = old DS wifi mode
#define HO_REG_VCOUNT      (*(vu16*)0x04000006) // current scanline, 0-262
#define HO_REG_KEYXY       (*(vu16*)0x04000136) // bit 7 set = the lid is closed
#define HO_LINES_PER_FRAME 263
#define HO_TICKS_PER_STEP  60 // ~1 second between steps/packets
#define HO_MAX_SEND_FAILS  3
// nds-bootstrap is built with DSIRPC_KEEP_DSI_WIFI, so the board normally
// stays in DSi mode and the restore step passes straight through. If
// something did switch it to DS mode, wait until the game is past its boot
// (~15 steps) before switching back. Steps are ~1 second each.
#define HO_RESTORE_AFTER_STEPS 15

enum { HO_LOAD = 0, HO_PROBE = 1, HO_RUN = 2, HO_FAILED = 3, HO_RESTORE = 4, HO_OFF = 5 };

extern u8 consoleModel; // card_engine_header.s: 0-1 = DSi, 2-3 = 3DS
extern u32 valueBits;   // card_engine_header.s
extern u32 rpcFlags;    // card_engine_header.s, from the loader
#define RPC_SLEEP_HOOKED 2    // rpcFlags: the game's SVC_Sleep goes to Probe_SleepWait()
#define VB_SLEEP_MODE BIT(17) // nds-bootstrap's sleep mode (off: "Stay connected")
extern int writePowerManagement(int reg, int command); // libnds/spi.c
#define PM_BACKLIGHTS 0x0C    // the PM's control register (0): both screens' backlights

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
#if RPCPROBE_ACH
static u8 hoAchDue = 0;        // send the checker's report (achSend()) next VBlank
static u8 hoNoHalt = 0;        // VBlanks since Probe_HaltTick() last ran (stops at 255)
static u8 hoHaltNoSd = 0;      // Probe_HaltTick() may not use the SD card (ROM reads from the IPC interrupt)
static u16 hoAchSeen = 0;      // probeAchTriggered when the in-game menu last opened
extern int tryLockMutex(int *addr);   // card_engine_header.s
extern int unlockMutex(int *addr);
#endif

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

static int putDec32(char *p, u32 v) {
	char tmp[10];
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
	u8 valid = RpcProbeHandoff_Load();
#ifdef DSIRPC_NO_WIFI
	valid = 0; // test build: the Wi-Fi chip is never touched (the checker still runs)
#endif
#if RPCPROBE_ACH
	ProbeAch_SetTime(rpcProbeHandoff.time); // offline too: it dates the unlocks
#endif
	if (valid) {
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
		ProbeWatch_Init(); // the ARM9 half (found again: probe_watch.h)
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
	// DSiRPC's ARM9 half: 0 = none, 1 = found, 2+ = the game's OS_Halt
	// patched, so the ARM9 writes its cache back in the game's idle time
	// (probe_watch.h).
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
#if RPCPROBE_ACH
	hoAchDue = (probeAchLoaded != PROBE_ACH_NONE);
#endif
}

#if RPCPROBE_ACH
// "DSiRPC ach n=<achievements> t=<unlocked> p=<passes> l=<lines> s=<saved>
// x=<not saved> w=<waiting> f=<frame lane> fr=<frames> fd=<dropped>
// fc=<unclean> h=<idle> st=<stamp> ids=<ids>", in the VBlank after each
// hello: n is the number being checked (0 = no set, below 0 = probe_ach.h's
// PROBE_ACH_E_*), t the unlocks so far, p the passes over the pass lane
// since the last one (about a second ago), l the longest the checker took
// in one VBlank, in scanlines, s and x how many of the unlocks were saved to
// RPCUNLK.BIN and how many couldn't be, w how many were already waiting
// there when the game started, f how many of the n are checked every frame,
// fr the frames they were checked for since the last one, fd the frames they
// couldn't be sampled for (the checking fell behind) and fc the samples taken
// without the ARM9's cache write-back, h 1 if the checking runs in the
// game's idle time (0: in the VBlank), st the set's stamp, ids the latest
// unlocks (at most 8, as many as fit). DSiRPC logs them, to compare with its
// own unlocks, and counts the unlocks right away.
static void achSend(void) {
	static char msg[176];
	int n = 0;
	ProbeAchStats st;
	u32 ids[8];

	ProbeAch_TakeStats(&st);
	n += putStr(&msg[n], "DSiRPC ach n=");
	if (probeAchLoaded < 0) {
		msg[n++] = '-';
		n += putDec(&msg[n], (u16)-probeAchLoaded);
	} else {
		n += putDec(&msg[n], (u16)probeAchLoaded);
	}
	n += putStr(&msg[n], " t=");
	n += putDec(&msg[n], probeAchTriggered);
	n += putStr(&msg[n], " p=");
	n += putDec(&msg[n], st.passes);
	n += putStr(&msg[n], " l=");
	n += putDec(&msg[n], st.maxLines);
	n += putStr(&msg[n], " s=");
	n += putDec(&msg[n], probeAchSaved);
	n += putStr(&msg[n], " x=");
	n += putDec(&msg[n], probeAchLost + probeAchSaveFailed);
	n += putStr(&msg[n], " w=");
	n += putDec(&msg[n], probeAchWaiting);
	n += putStr(&msg[n], " f=");
	n += putDec(&msg[n], probeAchFrameLane);
	n += putStr(&msg[n], " fr=");
	n += putDec(&msg[n], st.frames);
	n += putStr(&msg[n], " fd=");
	n += putDec(&msg[n], st.dropped);
	n += putStr(&msg[n], " fc=");
	n += putDec(&msg[n], st.unclean);
	n += putStr(&msg[n], " h=");
	n += putDec(&msg[n], st.idle);
	n += putStr(&msg[n], " st=");
	n += putHex(&msg[n], probeAchStamp, 8);
	int k = ProbeAch_RecentIds(ids, 8);
	for (int i = 0; i < k && n < (int)sizeof(msg) - 11; i++) {
		n += putStr(&msg[n], i ? "," : " ids=");
		n += putDec32(&msg[n], ids[i]);
	}

	u16 llcLen = (u16)ProbeNet_BuildUdpFrame(hoFrame, (const u8 *)msg, (u16)n);
	TwlWifi_SendLlcFrame(hoBroadcastMac, rpcProbeHandoff.dsiMac, hoFrame, llcLen, 1);
}

// Saves the oldest waiting unlock, if there is one and the SD card lock is
// free (nds-bootstrap's own SD access holds it; see the SD card rule above)
static void achSave(int *sdMutex) {
	if (ProbeAch_SavePending() && tryLockMutex(sdMutex)) {
		ProbeAch_SaveOne();
		unlockMutex(sdMutex);
	}
}
#endif

// "DSiRPC lid n=<hellos sent>": tells DSiRPC the Wi-Fi is going off because
// the lid closed (and shows the lid rule ran before the console slept), or
// with "pause" that the game paused with it still connected. Sent with CMD52,
// then given about 3 ms to go out (before the chip is told to leave the
// access point).
static void lidSend(int pause) {
	static char msg[32];
	int n = 0;
	n += putStr(&msg[n], pause ? "DSiRPC lid pause n=" : "DSiRPC lid n=");
	n += putDec(&msg[n], hoSent);
	u16 llcLen = (u16)ProbeNet_BuildUdpFrame(hoFrame, (const u8 *)msg, (u16)n);
	TwlWifi_SendLlcFrame(hoBroadcastMac, rpcProbeHandoff.dsiMac, hoFrame, llcLen, 0);
	swiDelay(25000);
}

void Probe_LidClosed(void) {
	// Not before handoffLoad() has run (the first tick), and only once
	if (hoStage == HO_LOAD || hoStage == HO_OFF) return;
	// Only if the launcher left the chip connected (a usable RPCHAND.TXT;
	// an offline one has no addresses)
	if (rpcProbeHandoff.valid) {
		// In DS mode the chip can't be reached over SDIO
		if (!(HO_REG_GPIO_WIFI & 0x100)) {
			if (hoStage == HO_RUN) lidSend(0);
			TwlWifi_Shutdown();
		}
		ProbeLed_WifiPowerOff();
	}
	hoStage = HO_OFF;
}

int Probe_SleepWait(void) {
	// Only while the launcher's connection is up: else the real sleep (a DSi
	// whose launcher went offline sleeps fine)
	if (!(rpcFlags & RPC_SLEEP_HOOKED) || !rpcProbeHandoff.valid || hoStage == HO_LOAD || hoStage == HO_OFF) return 0;
	if (hoStage == HO_RUN) lidSend(1);   // (running: the chip's back in DSi mode)
	while (HO_REG_KEYXY & 0x80) swiDelay(0x20000);
	return 1;
}

void Probe_LidDark(int closed) {
	static u8 dark, pm, volume;
	if (!closed == !dark) return;
	dark = closed != 0;
	if (dark) {
		pm = (u8)writePowerManagement(0x80, 0);     // read the control register
		volume = i2cReadRegister(I2C_PM, I2CREGPM_VOL);
		writePowerManagement(0, pm & ~PM_BACKLIGHTS);
		i2cWriteRegister(I2C_PM, I2CREGPM_VOL, 0);
	} else {
		writePowerManagement(0, pm);
		i2cWriteRegister(I2C_PM, I2CREGPM_VOL, volume);
	}
}

void Probe_MenuOpened(void) {
#if RPCPROBE_ACH
	hoAchSeen = probeAchTriggered;
	ProbeLed_Tick(0, 0); // now, since the VBlank ticks stop while the menu is open
	ProbeAch_MenuOpened(); // what the menu shows of them (dsirpc_ach_menu.h)
#endif
}

void Probe_MenuClosed(void) {
#if RPCPROBE_ACH
	ProbeAch_MenuClosed();
#endif
}

int Probe_HaltTick(int *sdMutex, int (*romWaiting)(void)) {
#if RPCPROBE_REQUESTS
	// Looking for the game's OS_Halt (only at the start, until it's found)
	if (ProbeWatch_Idle(RPCPROBE_WATCH_SCAN_LINES, romWaiting)) return 1;
#endif
#if RPCPROBE_ACH
	hoNoHalt = 0;
	// No SD card lock here (sdMutex NULL): the VBlank saves instead
	hoHaltNoSd = !sdMutex;
	if (sdMutex) achSave(sdMutex);
	return ProbeAch_Idle(romWaiting);
#else
	(void)sdMutex;
	(void)romWaiting;
	return 0;
#endif
}

void Probe_VBlankTick(const void *ndsHeader, int *sdMutex) {
	u16 lineStart = HO_REG_VCOUNT & 0x1FF;
	int sentThisTick = 0;
	// DSi: the lid closing turns the Wi-Fi off (the lid rule at the top), or
	// the screens and the sound when the game doesn't sleep
	int lidClosed = consoleModel < 2 && (HO_REG_KEYXY & 0x80);
	if (!(valueBits & VB_SLEEP_MODE)) Probe_LidDark(lidClosed);
	else if (lidClosed && !(rpcFlags & RPC_SLEEP_HOOKED)) Probe_LidClosed();
#if RPCPROBE_REQUESTS
	// Did the ARM9 write its cache back since the last VBlank (the samples
	// below say so), and is OS_Halt patched (if not, ask)
	ProbeWatch_Tick();
#endif
#if RPCPROBE_ACH
	// The checker's frame lane samples first, at the same point of every frame
	ProbeAch_Sample();
	// The achievement LED (not on the first tick, which reads the SD card)
	if (hoStage != HO_LOAD) ProbeLed_Tick((int)probeAchTriggered - (int)hoAchSeen, lidClosed);
#endif
#if RPCPROBE_REQUESTS
	// Per-frame capture first, so every sample is taken at the same point
	// in the frame (and before anything else this tick costs time).
	if (hoStage == HO_RUN) ProbeWatch_Sample(lineStart);
	if (hoStage == HO_RUN) sentThisTick = ProbeReq_Service(RPCPROBE_RX53_FRAMES_PER_VBLANK);
#endif
	if (hoStage == HO_LOAD && hoTimer == 0) {
		gameLoad((const u8 *)ndsHeader);
#if RPCPROBE_REQUESTS
		ProbeWatch_Init(); // the ARM9 half, for the checker's frame lane too
		ProbeWatch_Game(ndsHeader); // where to look for OS_Halt
#endif
#if RPCPROBE_ACH
		ProbeAch_Load(ndsHeader); // first VBlank: the SD card is safe to read
#endif
	}
	if (hoTimer) {
		hoTimer--;
#if RPCPROBE_ACH
		// the checker's report, a VBlank after the hello
		if (hoAchDue && hoStage == HO_RUN && !sentThisTick && !TwlWifi_RxBusy()) {
			hoAchDue = 0;
			achSend();
			sentThisTick = 1;
		}
#endif
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

#if RPCPROBE_ACH
	// Last, with whatever time this tick has left: the checking itself only
	// if Probe_HaltTick() hasn't run for a while (nds-bootstrap couldn't
	// hook this game's swiHalt)
	if (hoNoHalt < 255) hoNoHalt++;
	ProbeAch_Tick(lineStart, hoNoHalt < RPCPROBE_ACH_IDLE_DEAD);
#if RPCPROBE_REQUESTS
	// Looking for OS_Halt here instead, a little at a time, if the
	// swiHalt hook doesn't run
	if (hoNoHalt >= RPCPROBE_ACH_IDLE_DEAD) ProbeWatch_Idle(2, 0);
#endif

	// Unlocks are saved from Probe_HaltTick() too. If that hasn't run for a
	// while, or can't use the SD card, here instead, unless a ROM read is
	// under way (sdMutex is NULL then).
	if ((hoNoHalt >= RPCPROBE_ACH_SAVE_FALLBACK || hoHaltNoSd) && sdMutex) achSave(sdMutex);
#else
	(void)sdMutex;
#endif

	u16 lineEnd = HO_REG_VCOUNT & 0x1FF;
	u16 lines = (lineEnd >= lineStart) ? lineEnd - lineStart
	                                   : lineEnd + HO_LINES_PER_FRAME - lineStart;
	if (lines > hoTickMaxLines) hoTickMaxLines = lines;
}
