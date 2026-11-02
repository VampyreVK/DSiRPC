// SPDX-License-Identifier: Zlib
// SPDX-FileNotice: Modified from the original version by the BlocksDS project.
//
// Copyright (C) 2005 Michael Noland (joat)
// Copyright (C) 2005 Jason Rogers (Dovoto)
// Copyright (C) 2005-2015 Dave Murphy (WinterMute)
// Copyright (C) 2023 Antonio Niño Díaz

// The launcher's ARM7 core: BlocksDS's default one with DSWiFi and maxmod
// (sys/arm7/main_core in BlocksDS 1.24.0), changed for the menu music, which
// 0.9.1 didn't have (maxmod was linked in but never started):
//
// - maxmod's music timer handler, mmFrame(), lets other interrupts in once
//   its timing-critical part is done (REG_IME = 1), and libnds runs the
//   FIFO's callbacks with interrupts on too, the DSi's SD card reads among
//   them, which take milliseconds. So when the ARM9 asked for a read while
//   mmFrame() was working, the next music tick could start mmFrame() again
//   inside it, and maxmod isn't made for that: the launcher froze on a 3DS a
//   minute or so in, or crashed as it read the saves at boot (in
//   mmLockChannels(), the first message mmFrame() handles). The link gives
//   maxmod's irqSet() music_frame() instead (-Wl,--wrap=irqSet), which keeps
//   the music timer's interrupt off while mmFrame() runs: a tick that comes
//   meanwhile waits in REG_IF and runs as soon as it's done.
// - More room for the interrupt stacks (__irq_stack_size and __svc_stack_size
//   in the Makefile): each interrupt that comes inside another takes 40
//   bytes of the IRQ stack, and BlocksDS's 256 bytes hold six.
// - A guard on Wifi_Update(), which DSWiFi calls from the VBlank handler and
//   from its FIFO handler, so one call could start inside another. BlocksDS
//   added the same after 1.24.0 (DSWiFi 59d2636, -Wl,--wrap=Wifi_Update).
//
// It also keeps a record for the ARM9's watchdog (arm7watch.h): its VBlanks,
// how much of the interrupt stacks has been used and how often a music tick
// had to wait.

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

static Arm7Watch *volatile watch;   // the watchdog's record, once the ARM9 sends it

// maxmod's music tick, one at a time (see above). A handler starts with
// interrupts off, so REG_IE can be changed without a critical section then.
static void music_frame(void)
{
    const u32 timer = IRQ_TIMER(LIBNDS_DEFAULT_TIMER_MUSIC);
    REG_IE &= ~timer;
    mmFrame();
    int ime = enterCriticalSection();
    Arm7Watch *w = watch;
    if (w && (REG_IF & timer))
        w->music_waits++;
    REG_IE |= timer;
    leaveCriticalSection(ime);
}

void __real_irqSet(u32 mask, VoidFn handler);

void __wrap_irqSet(u32 mask, VoidFn handler)
{
    __real_irqSet(mask, handler == mmFrame ? music_frame : handler);
}

// The interrupt stacks are painted at the start, so how far they've gone
// shows in what's left of the paint (the linker script's symbols: each
// stack's top, the IRQ stack above the SVC one above the rest)
extern u32 __sp_irq[], __sp_svc[], __sp_usr[];

#define PAINT 0xFDFDFDFDu

static void paint(u32 *bottom, u32 *top)
{
    for (u32 *p = bottom; p < top; p++)
        *p = PAINT;
}

static u32 used(const u32 *bottom, const u32 *top)
{
    const u32 *p = bottom;
    while (p < top && *p == PAINT)
        p++;
    return (u32)(top - p) * 4;
}

static void watch_address(void *address, void *userdata)
{
    (void)userdata;
    Arm7Watch *w = address;
    if (w->magic != ARM7WATCH_MAGIC)
        return;
    w->irq_size = (u32)(__sp_irq - __sp_svc) * 4;
    w->svc_size = (u32)(__sp_svc - __sp_usr) * 4;
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
        if ((w->beats & 63) == 1)
        {
            w->irq_used = used(__sp_svc, __sp_irq);
            w->svc_used = used(__sp_usr, __sp_svc);
        }
    }
    inputGetAndSend();
    Wifi_Update();
}

int main(void)
{
    // Undefined instructions on the ARM7 are shown on the ARM9's screen
    // instead of freezing (that's how the music's crash showed itself)
    defaultExceptionHandler();

    // Nothing has used the interrupt stacks yet (interrupts are off)
    paint(__sp_svc, __sp_irq);
    paint(__sp_usr, __sp_svc);

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
