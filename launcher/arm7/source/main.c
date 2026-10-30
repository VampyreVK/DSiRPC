// SPDX-License-Identifier: Zlib
// SPDX-FileNotice: Modified from the original version by the BlocksDS project.
//
// Copyright (C) 2005 Michael Noland (joat)
// Copyright (C) 2005 Jason Rogers (Dovoto)
// Copyright (C) 2005-2015 Dave Murphy (WinterMute)
// Copyright (C) 2023 Antonio Niño Díaz

// The launcher's ARM7 core: BlocksDS's default one with DSWiFi and maxmod
// (sys/arm7/main_core in BlocksDS 1.24.0), plus a guard on Wifi_Update().
//
// Wifi_Update() runs from the VBlank handler below and from DSWiFi's FIFO
// handler, which libnds calls with interrupts on (and maxmod turns them on
// in its music timer too). So one call can start inside another, and inside
// that one another, which can overflow the ARM7's stack: the launcher froze
// a few minutes into its music on a 3DS. BlocksDS fixed this after 1.24.0
// (DSWiFi 59d2636, "Prevent Wifi_Update() from being nested"); until the SDK
// has it, the link sends every call through the same guard
// (-Wl,--wrap=Wifi_Update in the Makefile). This core can go once it does.

#include <nds.h>
#include <dswifi7.h>
#include <maxmod7.h>

void __real_Wifi_Update(void);

void __wrap_Wifi_Update(void)
{
    static volatile bool active;
    if (active)
        return;
    active = true;
    __real_Wifi_Update();
    active = false;
}

volatile bool exit_loop = false;

void power_button_callback(void)
{
    exit_loop = true;
}

void vblank_handler(void)
{
    inputGetAndSend();
    Wifi_Update();
}

int main(void)
{
    // Undefined instructions on the ARM7 (what running over a broken stack
    // tends to end in) are shown on the ARM9's screen instead of freezing
    defaultExceptionHandler();

    // Initialize sound hardware
    // Required for some functions within libnds
    enableSound();

    // Read user information from the firmware (name, birthday, etc)
    readUserSettings();

    // Stop LED blinking
    ledBlink(0);

    // Using the calibration values read from the firmware with
    // readUserSettings(), calculate some internal values to convert raw
    // coordinates into screen coordinates.
    touchInit();

    irqInit();
    fifoInit();

    installWifiFIFO();

    // Required for some functions within libnds
    installSoundFIFO();

    installSystemFIFO(); // Sleep mode, storage, firmware...
    if (isDSiMode())
        installCameraFIFO();

    // Initialize Maxmod. It uses timer 0 internally.
    mmInstall(FIFO_MAXMOD);

    // This sets a callback that is called when the power button in a DSi
    // console is pressed. It has no effect in a DS.
    setPowerButtonCB(power_button_callback);

    // Read current date from the RTC and setup an interrupt to update the time
    // regularly. The interrupt simply adds one second every time, it doesn't
    // read the date. Reading the RTC is very slow, so it's a bad idea to do it
    // frequently.
    initClockIRQTimer(LIBNDS_DEFAULT_TIMER_RTC);

    // Now that the FIFO is setup we can start sending input data to the ARM9.
    irqSet(IRQ_VBLANK, vblank_handler);
    irqEnable(IRQ_VBLANK);

    while (!exit_loop)
    {
        const uint16_t key_mask = KEY_SELECT | KEY_START | KEY_L | KEY_R;
        uint16_t keys_pressed = ~REG_KEYINPUT;

        if ((keys_pressed & key_mask) == key_mask)
            exit_loop = true;

        swiWaitForVBlank();
    }

    return 0;
}
