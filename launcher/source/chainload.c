// SPDX-License-Identifier: MIT
//
// Starting our nds-bootstrap build straight from the launcher (see
// chainload.h and ../CHAINLOAD.md).
//
// BlocksDS has no "launch this .nds" call, but exit() follows the
// exit-to-loader protocol: if a bootstub sits at 0x02FF4000, exit() jumps
// into it. Whatever started the launcher (TWiLight Menu++) put its own
// there, which is why the launcher used to return to the menu. This puts
// ours there instead, the way NDS Homebrew Menu launches programs:
//
//   bootstub.bin  hands the ARM7 the loader that follows it
//   load.bin      nds-bootloader: reads the .nds by its first FAT cluster
//                 and boots it, with argv[0] = its path (nds-bootstrap
//                 finds its own files through argv[0])
//
// Both come from loader/ (GPLv2+), built along with the launcher.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include <nds.h>

#include "chainload.h"

// From source/loader_blobs.s
extern const u8 bootstub_bin[];
extern const u32 bootstub_bin_size;
extern const u8 load_bin[];
extern const u32 load_bin_size;

// nds-bootloader's header (loader/source/load_crt0.s)
typedef struct
{
    u32 branch;
    u32 storedFileCluster;  // the .nds file's first cluster
    u32 initDisc;
    u32 wantToPatchDLDI;
    u32 argStart;           // offset of the argv strings from the loader's start
    u32 argSize;            // their size, terminators included
    u32 dldiOffset;
    u32 dsiSD;              // read the DSi's own SD slot...
    u32 dsiMode;            // ...and stay in DSi mode
} LoaderHeader;

// The bootstub runs from 0x02FF4000. The ARM9 writes it through
// __system_bootstub (the 0x0CFF4000 mirror), because its DTCM covers
// 0x02FF4000. Like NDS Homebrew Menu's, it ends before 0x02FFA000, where
// loaders keep their exception handler (the bootstub, the loader with its
// .bss and argv take about 0x5E90 bytes).
#define BOOTSTUB_RUN_ADDRESS 0x02FF4000u
#define BOOTSTUB_MAX_SIZE    0x6000u

#define ALIGN4(x) (((x) + 3u) & ~3u)

void chainload(const char *path, char *msg, unsigned int msgsz)
{
    struct stat st;
    if (stat(path, &st) != 0)
    {
        snprintf(msg, msgsz, "Can't open\n%s", path);
        return;
    }
    if ((u32)st.st_ino < 2)  // BlocksDS: st_ino is the first FAT cluster
    {
        snprintf(msg, msgsz, "Can't find where\n%s\nis on the SD card.", path);
        return;
    }

    LoaderHeader header;
    memcpy(&header, load_bin, sizeof(header));
    u32 arg_start = ALIGN4(header.argStart);
    u32 arg_size = strlen(path) + 1;
    u32 loader_size = arg_start + ALIGN4(arg_size);
    if (bootstub_bin_size + loader_size > BOOTSTUB_MAX_SIZE)
    {
        snprintf(msg, msgsz, "The path of nds-bootstrap is\ntoo long:\n%s", path);
        return;
    }

    u8 *stub = (u8 *)__system_bootstub;
    u8 *loader = stub + bootstub_bin_size;
    memcpy(stub, bootstub_bin, bootstub_bin_size);
    memcpy(loader, load_bin, load_bin_size);
    memset(loader + load_bin_size, 0, loader_size - load_bin_size);
    memcpy(loader + arg_start, path, arg_size);

    LoaderHeader *h = (LoaderHeader *)loader;
    h->storedFileCluster = (u32)st.st_ino;
    h->initDisc = 1;
    h->wantToPatchDLDI = 0;
    h->argStart = arg_start;
    h->argSize = arg_size;
    h->dsiSD = 1;
    h->dsiMode = 1;

    // The bootstub's entry points are offsets until made into addresses.
    // bootsize is how much of what follows it gets copied for the ARM7, so
    // it covers argv too.
    struct __bootstub *bs = (struct __bootstub *)stub;
    bs->arm9reboot = (VoidFn)(BOOTSTUB_RUN_ADDRESS + (u32)bs->arm9reboot);
    bs->arm7reboot = (VoidFn)(BOOTSTUB_RUN_ADDRESS + (u32)bs->arm7reboot);
    bs->bootsize = loader_size;

    DC_FlushAll();

    // No Wifi_DisconnectAP()/Wifi_DisableWifi(): the chip stays associated
    // for the game, as before.
    exit(0);
}
