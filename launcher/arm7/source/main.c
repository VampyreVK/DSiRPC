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

#include "arm7watch.h"

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

// The watchdog's record (arm7watch.h): the link sends every interrupt
// handler the libraries set through a stub that counts it
// (-Wl,--wrap=irqSet,--wrap=irqSetAUX in the Makefile), so if the ARM7 ever
// stops, the ARM9 can show which handlers it was in.
void __real_irqSet(u32 mask, VoidFn handler);
void __real_irqSetAUX(u32 mask, VoidFn handler);

extern char __end__[];          // the end of the ARM7's data: the stack's floor

static Arm7Watch *volatile watch;
static VoidFn handlers[64];     // by IRQ bit, 32-63: AUX

static void run(int n)
{
    Arm7Watch *w = watch;
    if (w)
    {
        uint32_t sp;
        asm volatile("mov %0, sp" : "=r"(sp));
        w->started[n]++;
        w->running[n]++;
        if (++w->depth > w->depth_max)
            w->depth_max = w->depth;
        if (sp < w->stack_low)
            w->stack_low = sp;
        w->last = n;
        w->last_beat = w->beats;
    }
    VoidFn fn = handlers[n];
    if (fn)
        fn();
    if (w)
    {
        w->running[n]--;
        w->depth--;
    }
}

#define STUB(n) static void stub_##n(void) { run(n); }
STUB(0) STUB(1) STUB(2) STUB(3) STUB(4) STUB(5) STUB(6) STUB(7)
STUB(8) STUB(9) STUB(10) STUB(11) STUB(12) STUB(13) STUB(14) STUB(15)
STUB(16) STUB(17) STUB(18) STUB(19) STUB(20) STUB(21) STUB(22) STUB(23)
STUB(24) STUB(25) STUB(26) STUB(27) STUB(28) STUB(29) STUB(30) STUB(31)
STUB(32) STUB(33) STUB(34) STUB(35) STUB(36) STUB(37) STUB(38) STUB(39)
STUB(40) STUB(41) STUB(42) STUB(43) STUB(44) STUB(45) STUB(46) STUB(47)
STUB(48) STUB(49) STUB(50) STUB(51) STUB(52) STUB(53) STUB(54) STUB(55)
STUB(56) STUB(57) STUB(58) STUB(59) STUB(60) STUB(61) STUB(62) STUB(63)

static const VoidFn STUBS[64] = {
    stub_0, stub_1, stub_2, stub_3, stub_4, stub_5, stub_6, stub_7,
    stub_8, stub_9, stub_10, stub_11, stub_12, stub_13, stub_14, stub_15,
    stub_16, stub_17, stub_18, stub_19, stub_20, stub_21, stub_22, stub_23,
    stub_24, stub_25, stub_26, stub_27, stub_28, stub_29, stub_30, stub_31,
    stub_32, stub_33, stub_34, stub_35, stub_36, stub_37, stub_38, stub_39,
    stub_40, stub_41, stub_42, stub_43, stub_44, stub_45, stub_46, stub_47,
    stub_48, stub_49, stub_50, stub_51, stub_52, stub_53, stub_54, stub_55,
    stub_56, stub_57, stub_58, stub_59, stub_60, stub_61, stub_62, stub_63,
};

static void set_handlers(u32 mask, VoidFn handler, int first, void (*set)(u32, VoidFn))
{
    for (int bit = 0; bit < 32; bit++)
    {
        if (!(mask & BIT(bit)))
            continue;
        handlers[first + bit] = handler;
        set(BIT(bit), handler != NULL ? STUBS[first + bit] : NULL);
    }
}

void __wrap_irqSet(u32 mask, VoidFn handler)
{
    set_handlers(mask, handler, 0, __real_irqSet);
}

void __wrap_irqSetAUX(u32 mask, VoidFn handler)
{
    set_handlers(mask, handler, 32, __real_irqSetAUX);
}

static void watch_address(void *address, void *userdata)
{
    (void)userdata;
    Arm7Watch *w = address;
    if (w->magic != ARM7WATCH_MAGIC)
        return;
    w->stack_floor = (uint32_t)__end__;
    watch = w;
}

volatile bool exit_loop = false;

void power_button_callback(void)
{
    exit_loop = true;
}

void vblank_handler(void)
{
    Arm7Watch *w = watch;
    if (w)
    {
        w->beats++;
        w->ie = REG_IE;
        w->ie_aux = isDSiMode() ? REG_AUXIE : 0;
        for (int i = 0; i < 4; i++)
            w->timers[i] = TIMER_CR(i);
    }
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
    fifoSetAddressHandler(ARM7WATCH_FIFO, watch_address, NULL);

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
