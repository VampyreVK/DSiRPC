# Making START launch our nds-bootstrap directly (one-ROM flow)

Status: researched, **not built yet**. The handoff itself works on hardware
(the connection survives into the game), so this is the next step for a
one-app flow.

## Why it needs a loader

BlocksDS has no "launch this other .nds" function. Its `exit()` only follows
the *exit-to-loader protocol*: if a valid bootstub sits at the bootstub
address, `exit()` jumps into it. Today that bootstub belongs to whatever
launched the launcher (TWiLight), which is why START returns there.

So the launcher installs its **own** bootstub, pointed at our nds-bootstrap,
then calls `exit(0)`. This is how NDS Homebrew Menu (hbmenu) itself launches
programs. BlocksDS's own exit-to-loader tests use hbmenu 0.11.0, so the
protocol on both sides already matches.

## Pieces

1. **`bootstub.bin`**: hbmenu's `bootstub/bootstub.s` (GPLv2+). It's
   plain, self-contained ARM assembly whose header matches BlocksDS's
   `struct __bootstub` exactly: `"bootstub"` signature, ARM9 reboot offset,
   ARM7 reboot offset, loader size.
2. **`load.bin`**: devkitPro's `nds-bootloader`. This is the ARM7 loader
   that reads an .nds off the DSi SD card by starting cluster and boots it
   with argv. The current master branch needs libnds 2 ("calico"). Our
   `devkitpro/devkitarm:20241104` image appears to have libnds 1.x (it builds
   nds-bootstrap, which uses 1.x APIs), so use the last `nds-bootloader` tag
   from before calico. The repo's tags run up to v0.9.0; which one is the
   last pre-calico tag still needs checking.
3. **Launcher code** (`source/main.c`), on START:
   - `stat("sd:/_nds/dsirpc/nds-bootstrap-dsirpc.nds")`. In BlocksDS,
     `st_ino` is the file's starting FAT cluster, which is what the loader
     needs.
   - Copy `bootstub.bin`, then `load.bin` right after it, into the bootstub
     area (`__system_bootstub`, `0x0CFF4000` in DSi mode). Convert the two
     reboot offsets to absolute addresses, as hbmenu's `installBootStub()`
     does.
   - Fill in the loader header: `storedFileCluster` = that cluster,
     `wantToPatchDldi` = 0, `hasTwlSd` = 1, `isTwlMode` = 1. Pack argv[0]
     at `argStart`.
   - Set `bootsize` to cover `load.bin` **plus** the argv block. hbmenu sets
     it to `load_bin_size` alone, which would drop our argv when the stub
     copies the loader.
   - `DC_FlushAll()`, then `exit(0)`.
4. Embed both .bin files with BlocksDS's `BINDIRS := data`. Each one becomes
   a `*_bin.h` header with the bytes as an array.

## Traps

- **argv[0] must be our build's real path.** nds-bootstrap loads its
  cardengine binaries from its *own* file via argv[0]. If that's missing, it
  falls back to `sd:/_nds/nds-bootstrap-nightly.nds`, which could be a stock
  nightly. That's the "handoff must use our bootstrap" issue, so give our
  build its own name and folder.
- **The loader's reset** sets `REG_POWCNT` to sound-only. That should be
  harmless: DSWiFi's DSi mode never turns that bit on, and the connection
  worked. The chosen `nds-bootloader` version still needs a check that it
  doesn't touch `REG_GPIO_WIFI` (`0x04004C04`). Current master doesn't.
- **The ini is shared with TWiLight** (`sd:/_nds/nds-bootstrap.ini`). The
  launcher could rewrite `NDS_PATH`/`SAV_PATH` before launching, so it always
  boots Platinum no matter what TWiLight last wrote.

## Build flow once implemented

1. devkitARM image: build `load.bin` (one command).
2. Assemble `bootstub.s` → `bootstub.bin`. This can run in the same devkitARM
   container, since it's just `arm-none-eabi-as` + `objcopy`.
3. Copy both into `launcher/data/`, then run the normal BlocksDS
   build.
