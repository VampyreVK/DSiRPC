# Debugging rpcprobe (the in-game side)

The in-game side has three ways to tell you what it's doing, from least to
most invasive: the hello packets, the RAM viewer status byte, and a debug
build's log file. Start with the hello packets. They cover almost everything
and need no rebuild.

## 1. Hello packets (always on)

Once running, the DSi sends one UDP packet per second to `pc_ip:port` from
`/RPCPROBE.CFG`:

```
DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X rx=N req=N arp=N eap=N
```

Watch them with `launcher/pc/hello_listener.py`.

| Field | Meaning |
|---|---|
| `gpio` | `0x04004C04` when the chip was probed. `0000` is expected. Bit 8 (`0100`) would mean the board was in old DS mode. |
| `rev`, `ioen` | SDIO CCCR responses from the one-time chip probe. `ioen=02` means SDIO function 1 is still enabled, so the chip hasn't been reset since the launcher set it up. `00` means it was reset and the connection is gone. |
| `last` | Result of the previous send: `0` OK, `1` the chip reported a TX mailbox overflow, anything else is an SDIO error. Three SDIO errors in a row stop sending. |
| `rx` | Packets drained from the chip's receive mailbox (any kind) |
| `req` | Memory requests answered |
| `arp` | ARP replies sent. If this is 0 and requests time out, the PC can't find the DSi's MAC. |
| `eap` | EAPOL frames seen, meaning the router renewed its keys. If hellos stop right after this goes up, that's the group-key renewal problem. |

No hellos at all means one of the startup steps failed. Check, in order:

1. The launcher ran in DSi mode and wrote `/RPCHAND.TXT`.
2. `/RPCPROBE.CFG` exists with a valid `pc_ip=`.
3. The build has `DSIRPC_KEEP_DSI_WIFI`.
4. The Windows firewall lets Python receive on the port.

If all of that looks right, use a debug build (section 3).

## 2. RAM viewer status byte

`probe_hook.c` keeps a one-byte status, `probeStatusByte`, that you can
watch with nds-bootstrap's in-game menu RAM viewer. That menu relays ARM7
memory too.

- bit 7: set once the state machine has run
- bits 4-6: stage (0 loading files, 1 probing the chip, 2 sending,
  3 failed, 4 waiting to switch the board back to DSi mode)
- bits 0-3: low 4 bits of the hello count

For example, `A5` means sending, 5th packet (mod 16), and `B0` means failed.

The address changes between builds. After building, look it up in the ELF.
From PowerShell, in the repo root:

```
docker run --rm -v "C:\Projects\DSiRPC\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 /opt/devkitpro/devkitARM/bin/arm-none-eabi-nm retail/cardenginei/arm7/build/cardenginei_arm7.elf | findstr probeStatusByte
```

## 3. Debug build (`NDSBTSRP.LOG`)

nds-bootstrap has a debug logger that writes `NDSBTSRP.LOG` to the SD root.
To turn it on, add `-DDEBUG` to the `CFLAGS += $(INCLUDE) -DARM7 -DTWOCARD`
line in `retail/cardenginei/arm7/Makefile`. Then do a clean build, because
make won't notice a flag change on its own. Delete
`retail/cardenginei/arm7/build`, or touch the sources.

rpcprobe logs only during the first VBlank:

- `rpcprobe: RPCPROBE.CFG not found`, `rpcprobe: config loaded`, or
  `rpcprobe: RPCPROBE.CFG found but no usable pc_ip=`
- `rpcprobe: RPCHAND.TXT not found (run the launcher first)`,
  `rpcprobe: handoff loaded`, or `... found but no usable mac=/ip=`
- `rpcprobe: handoff ready, sending to pc_mac` (or `... using broadcast`),
  or `rpcprobe: config/handoff files missing, handoff off`

Two things to know:

- **Only use debug builds for short startup checks.** nds-bootstrap's own
  debug logging keeps writing to the SD card from interrupts during
  gameplay, and that has crashed the game (for example, opening the party
  menu). Turn it off again and do another clean build afterwards.
- **Clean debug builds compile.** Upstream's debug-only code in
  `retail/common/source/my_fat.c` and `my_sd.c` didn't compile with GCC 14
  (devkitARM r64+): it called `nocashMessage()` without including
  `nocashMessage.h`, and passed pointers to `dbg_hexa()` without a cast.
  DSiRPC adds the include (only when `DEBUG` is defined) and the `(u32)`
  casts, so non-debug builds are unchanged. Earlier debug builds only worked
  because a stale `my_fat.o` from a non-debug build was being reused.

## Rules the in-game code has to follow

- **The SD card is only touched on the very first VBlank** (loading the
  two files). Later, the game reads its save from the SD card outside
  interrupts, and SD access from the VBlank interrupt in the middle of that
  hangs the game (seen as a white screen).
- **Everything runs inside the VBlank interrupt,** so each tick has to stay
  short. The receive path handles at most one packet per VBlank.
- **Space is tight.** `cardenginei_arm7` has a fixed 61 KB region.
  `RPCPROBE_REQUESTS 0` in `rpcprobe_build.h` builds a hello-only version,
  which is useful for ruling the receive path out.
