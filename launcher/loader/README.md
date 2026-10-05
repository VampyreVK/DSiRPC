# Loader

The two pieces `../source/chainload.c` installs to start our nds-bootstrap
build straight from the launcher (see [../CHAINLOAD.md](../CHAINLOAD.md)).
The launcher's Makefile builds them with BlocksDS's toolchain (`make` here
does it on its own) into `build/`, and `../source/loader_blobs.s` embeds them.

| Output | From | What it does |
|---|---|---|
| `build/bootstub.bin` | `bootstub.s`, NDS Homebrew Menu's bootstub ([devkitPro/nds-hb-menu](https://github.com/devkitPro/nds-hb-menu), `bootstub/bootstub.s`), unchanged | What `exit()` jumps to: it copies the loader that follows it to VRAM C and resets the ARM7 into it |
| `build/load.bin` | `source/`, `arm9code/`, `load.ld`: devkitPro's nds-bootloader ([devkitPro/nds-bootloader](https://github.com/devkitPro/nds-bootloader)) at commit `35f54d8`, the last one before it moved to libnds 2 ("calico") | ARM7 code that reads an `.nds` off the DSi's SD card by its first cluster, loads it (DSi sections too) and boots it with `argv` |

Changes from upstream: this Makefile (upstream's needs devkitARM), and
`source/blocksds_compat.c`, which adds the few C library and libnds functions
the loader calls (`memcpy`, `memset`, `memcmp`, `strlen`, `dmaSetParams`),
because it's linked on its own here. The loader's sources are otherwise as
upstream left them.

## License

Both are GPLv2 or later (see the headers of the files), and so is the
launcher `.nds` they end up in. `source/blocksds_compat.c` and the Makefile
are new here (MIT and CC0).
