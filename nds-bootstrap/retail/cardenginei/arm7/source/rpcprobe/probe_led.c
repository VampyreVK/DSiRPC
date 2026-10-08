// probe_led.c - see probe_led.h.
//
// The achievement LED is the one TWiLight Menu++'s "ROM read LED" setting
// picks (ROMREAD_LED in nds-bootstrap.ini, the cardengine's romRead_LED):
// 1 = Wi-Fi LED, 2 = power LED (purple), 3 = camera LED, 0 = none. In
// DSiRPC's nds-bootstrap that LED no longer lights up for ROM reads
// (cardengine.c's cardReadLED() returns at once), so rpcprobe is the only
// thing writing to it, and nothing uses the I2C bus from outside interrupts
// while the game runs. Like upstream's ROM read LED: DSi only, and never on
// a console whose I2C is marked broken (i2cBricked).
//
// The values are nds-bootstrap's own (cardReadLED()): the power LED is
// forced purple with FFh and back to normal with 00h, or the other way
// round if it was already FFh when the game started (a console set to
// purple).

#include <nds/ndstypes.h>
#include <nds/arm7/i2c.h>
#include "probe_led.h"

extern u32 valueBits;   // card_engine_header.s
extern u8 consoleModel; // 0-1 = DSi, 2-3 = 3DS
extern u8 romRead_LED;  // the ROM read LED setting
#define LED_I2C_BRICKED BIT(30) // cardengine.c's i2cBricked

#define BPTWL        0x4A
#define BPTWL_WIFI   0x30 // bits 0-1 Wi-Fi LED (0/2 off, 1 on, 3 blink on traffic), bit 4 the chip's SDIO enable
#define BPTWL_CAMERA 0x31 // 0 off, 1 on
#define BPTWL_POWER  0x63 // forced power LED colour

// The pulse: lit for LED_LIT_TICKS VBlanks out of every LED_PERIOD
// (half a second every second and a half)
#define LED_PERIOD    90
#define LED_LIT_TICKS 30

enum { LED_NONE = 0, LED_WIFI = 1, LED_POWER = 2, LED_CAMERA = 3 };
enum { SHOW_NORMAL = 0, SHOW_LIT = 1, SHOW_DARK = 2 };

static u8 ledReady;      // 0 = not set up yet, 1 = ready, 2 = no achievement LED
static u8 ledShown;      // SHOW_* last written
static u8 ledCount;      // VBlanks into the pulse
static u8 powerNormal;   // BPTWL[63h] normally ...
static u8 powerLit;      // ... and lit up
static u8 wifiRead;      // 1 once wifiReg has been read
static u8 wifiReg;       // BPTWL[30h] as last read or written
static u8 wifiLedNormal; // its LED bits when not pulsing

static int i2cOk(void) {
	return consoleModel < 2 && !(valueBits & LED_I2C_BRICKED);
}

static void wifiLoad(void) {
	if (wifiRead) return;
	wifiReg = i2cReadRegister(BPTWL, BPTWL_WIFI);
	wifiLedNormal = wifiReg & 3;
	wifiRead = 1;
}

static void ledSetup(void) {
	ledReady = 2;
	if (!i2cOk()) return;
	switch (romRead_LED) {
		case LED_WIFI:
			wifiLoad();
			break;
		case LED_POWER: {
			u8 v = i2cReadRegister(BPTWL, BPTWL_POWER);
			powerNormal = (v == 0xFF) ? 0xFF : 0x00;
			powerLit = (v == 0xFF) ? 0x00 : 0xFF;
			break;
		}
		case LED_CAMERA:
			break;
		default:
			return;
	}
	ledReady = 1;
}

static void ledShow(u8 show) {
	switch (romRead_LED) {
		case LED_WIFI: {
			u8 bits = (show == SHOW_LIT) ? 1 : (show == SHOW_DARK) ? 2 : wifiLedNormal;
			wifiReg = (u8)((wifiReg & ~3) | bits);
			i2cWriteRegister(BPTWL, BPTWL_WIFI, wifiReg);
			break;
		}
		case LED_POWER:
			i2cWriteRegister(BPTWL, BPTWL_POWER, show == SHOW_LIT ? powerLit : powerNormal);
			break;
		case LED_CAMERA:
			i2cWriteRegister(BPTWL, BPTWL_CAMERA, show == SHOW_LIT ? 1 : 0);
			break;
	}
	ledShown = show;
}

void ProbeLed_Tick(int unread, int lidClosed) {
	if (!ledReady) ledSetup();
	if (ledReady != 1) return;
	u8 show = SHOW_NORMAL;
	if (unread > 0 && !lidClosed) {
		show = (ledCount < LED_LIT_TICKS) ? SHOW_LIT : SHOW_DARK;
		if (++ledCount >= LED_PERIOD) ledCount = 0;
	} else {
		ledCount = 0;
	}
	// Only the Wi-Fi LED's normal state (blinking on traffic) differs from dark
	if (show == SHOW_DARK && romRead_LED != LED_WIFI) show = SHOW_NORMAL;
	if (show != ledShown) ledShow(show);
}

void ProbeLed_WifiPowerOff(void) {
	if (!i2cOk()) return;
	wifiLoad();
	wifiLedNormal = 2; // no Wi-Fi from now on: its LED stays off
	wifiReg = (u8)((wifiReg & ~0x13) | 2); // SDIO enable off, LED off
	i2cWriteRegister(BPTWL, BPTWL_WIFI, wifiReg);
	if (romRead_LED == LED_WIFI) ledShown = SHOW_NORMAL;
}
