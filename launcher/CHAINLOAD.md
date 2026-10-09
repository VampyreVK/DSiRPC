# Starting our nds-bootstrap straight from the launcher (one-app flow)

Status: **works on hardware** (`source/chainload.c`, `loader/`): it's how
every game is started from the launcher, online and offline, and the
connection survives into the game. If it ever fails on a console, the
launcher's **Y** still exits connected, back to the menu.

## Why it needs a loader

BlocksDS has no "launch this other .nds" function. Its `exit()` only follows
the *exit-to-loader protocol*: if a valid bootstub sits at the bootstub
address, `exit()` jumps into it. Whatever launched the launcher (TWiLight)
put its own bootstub there, which is why exiting returns to the menu.

So the launcher installs its **own** bootstub, pointed at our nds-bootstrap,
then calls `exit(0)`. This is how NDS Homebrew Menu (hbmenu) itself launches
programs, and BlocksDS's own exit-to-loader tests use hbmenu's bootstub, so
the protocol on both sides matches.

## Pieces

1. **`bootstub.bin`**: hbmenu's `bootstub/bootstub.s` (GPLv2+), plain ARM
   assembly whose header matches BlocksDS's `struct __bootstub`: `"bootstub"`
   signature, ARM9 reboot offset, ARM7 reboot offset, loader size.
2. **`load.bin`**: devkitPro's `nds-bootloader`, the ARM7 loader that reads an
   .nds off the DSi SD card by its starting cluster and boots it with argv.
   Its master branch needs libnds 2 ("calico"), so `loader/` has commit
   `35f54d8`, the last one before that, built with BlocksDS's toolchain (a
   small `blocksds_compat.c` supplies the few C library calls it needs).
3. **Launcher code** (`source/chainload.c`), once the game is picked and the
   ini written:
   - `stat()` our nds-bootstrap. In BlocksDS, `st_ino` is the file's starting
     FAT cluster, which is what the loader needs.
   - Copy `bootstub.bin`, then `load.bin` right after it, into the bootstub
     area. The ARM9 writes it through `__system_bootstub` (the `0x0CFF4000`
     mirror in DSi mode), because its DTCM covers `0x02FF4000`. Turn the two
     reboot offsets into addresses at `0x02FF4000`, where it runs from, as
     hbmenu's `installBootStub()` does.
   - Fill in the loader header: `storedFileCluster` = that cluster,
     `initDisc` = 1, `wantToPatchDLDI` = 0, `dsiSD` = 1, `dsiMode` = 1. Put
     argv[0] (nds-bootstrap's own path) at `argStart`, and its length with
     the terminator in `argSize`.
   - Set `bootsize` to cover `load.bin` **plus** argv. hbmenu sets it to the
     loader's size alone, which would drop argv when the stub copies the
     loader.
   - `DC_FlushAll()`, then `exit(0)`. Like the old START, nothing
     disconnects the Wi-Fi.
4. Both .bin files are embedded with `.incbin` (`source/loader_blobs.s`).
   The Makefile builds `loader/` first, so it's still one `make` (and one
   Docker command) for everything.

## Traps

- **argv[0] must be our build's real path.** nds-bootstrap loads its
  cardengine binaries from its *own* file via argv[0]. If that's missing, it
  falls back to `sd:/_nds/nds-bootstrap-nightly.nds`, which could be a stock
  nightly. That's the "handoff must use our bootstrap" issue, so our build
  has its own name and folder, next to the launcher.
- **The loader's reset** sets `REG_POWCNT` to sound-only. That should be
  harmless: DSWiFi's DSi mode never turns that bit on, and the connection
  already survived TWiLight's loader, a fork of the same code. The loader
  doesn't touch `REG_GPIO_WIFI` (`0x04004C04`) or the SDIO Wi-Fi registers.
- **The ini is shared with TWiLight** (`sd:/_nds/nds-bootstrap.ini`). The
  launcher rewrites `NDS_PATH`, `SAV_PATH` and the last game's per-game
  values before starting nds-bootstrap (`source/bootstrap_ini.c`, described
  in [README.md](README.md#the-game-the-ini-and-your-save)), and only an
  existing save is ever used.
