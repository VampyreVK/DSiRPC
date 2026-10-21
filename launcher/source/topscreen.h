// SPDX-License-Identifier: MIT
//
// The top screen: DSiRPC's pixel DSi, as on the desktop app's waiting
// screen, with its Wi-Fi sign lighting up arc by arc while the launcher
// connects and turning green once it's connected.

#ifndef TOPSCREEN_H__
#define TOPSCREEN_H__

typedef enum
{
    TOP_CONNECTING,     // the Wi-Fi sign's arcs light up one by one
    TOP_CONNECTED,      // green
    TOP_FAILED,         // red: it couldn't connect
    TOP_OFFLINE,        // dark: playing offline
} TopState;

// Draws it and starts the animation (a cothread that runs whenever the
// launcher waits for a frame). Call once, after consoleDemoInit().
void top_init(void);

void top_set(TopState state);

#endif // TOPSCREEN_H__
