// SPDX-License-Identifier: MIT
//
// Starting another .nds from the SD card (our nds-bootstrap build) without
// going back to the menu, so the Wi-Fi connection stays up. See
// ../CHAINLOAD.md.

#ifndef CHAINLOAD_H__
#define CHAINLOAD_H__

// Installs a bootstub and loader that boot `path` (an "sd:/..." path, passed
// to it as argv[0]) and exits into them. Only returns on failure, with a
// message for the screen in msg.
void chainload(const char *path, char *msg, unsigned int msgsz);

#endif // CHAINLOAD_H__
