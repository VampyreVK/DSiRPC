# Debugging rpcprobe (the in-game side)

The in-game side has three ways to tell you what it's doing, from least to
most invasive: the hello packets, the RAM viewer status byte, and a debug
build's log file. Start with the hello packets. They cover almost everything
and need no rebuild.

## 1. Hello packets (always on)

Once running, the DSi broadcasts one UDP packet per second to
255.255.255.255, port 4244:

```
DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X gc=XXXX v=XX hc=XXXX rx=N req=N arp=N eap=N rxm=N e53=N txm=N t53=N rep=N a9=N vb=N
```

Watch them with `launcher/pc/hello_listener.py`.

| Field | Meaning |
|---|---|
| `gpio` | `0x04004C04` when the chip was probed. `0000` is expected. Bit 8 (`0100`) would mean the board was in old DS mode. |
| `rev`, `ioen` | SDIO CCCR responses from the one-time chip probe. `ioen=02` means SDIO function 1 is still enabled, so the chip hasn't been reset since the launcher set it up. `00` means it was reset and the connection is gone. |
| `last` | Result of the previous send: `0` OK, `1` the chip reported a TX mailbox overflow, anything else is an SDIO error. Three SDIO errors in a row stop sending. |
| `gc` | The running game's 4-letter code, from its header (`CPUE` = Platinum US, `IRBO` = Black US); `?` for unreadable characters. Read once, on the first VBlank. Older builds don't send `gc`, `v` or `hc`. |
| `v` | The game's ROM version (hex) |
| `hc` | The game's header CRC (hex), which tells apart dumps and hacks that share a game code |
| `rx` | Packets drained from the chip's receive mailbox (any kind) |
| `req` | Memory requests answered |
| `arp` | ARP replies sent. If this is 0 and requests time out, the PC can't find the DSi's MAC. |
| `eap` | EAPOL frames seen, meaning the router renewed its keys. If hellos stop right after this goes up, that's the group-key renewal problem. |
| `rxm` | How received frames are read from the chip: `53` = CMD53 block transfers (one SDIO command per frame), `52` = one CMD52 per byte (the `RPCPROBE_RX_CMD53` switch is off, or CMD53 failed three times on this console and it switched itself back). |
| `e53` | CMD53 reads that failed: an SDIO error or timeout, or data that didn't match the frame's header. A few right at the start followed by `rxm=52` means CMD53 doesn't work on this console. |
| `txm` | How frames are sent: `53` = CMD53 block writes (replies, ARP replies and 9 hellos in 10; every 10th hello always goes out with CMD52 so the PC keeps hearing from the DSi), `52` = CMD52 for everything (`RPCPROBE_TX_CMD53` off, CMD53 writes failed three times, or the PC had to re-send the same request twice in a row, which means CMD53 replies weren't arriving). |
| `t53` | CMD53 writes that failed (SDIO error or timeout). |
| `rep` | Requests the PC sent again with the same sequence number, meaning it never got the reply. |
| `a9` | `1` when rpcprobe found the ARM9 half of the per-frame capture in the ARM9 cardengine, so captured values are read by the ARM9 (through its cache). `0`: an ARM9 cardengine without it (DLDI or GSDD variant, or an older build), so the ARM7 reads main RAM itself. Older builds don't send `a9`. |
| `vb` | Longest VBlank tick of the in-game side since the previous hello, in scanlines (about 64 µs each; a whole frame is 263). A tick that sends a 256-byte frame with CMD52 (roughly 19 µs per SDIO command) takes about 76 lines, 4.8 ms, and play was smooth at that on hardware. With CMD53 sending (`txm=53`) it should be far lower, except in the hello right after each 10th one, which covers a CMD52 hello tick. Values approaching a whole frame mean rpcprobe is holding up the game's own ARM7 work long enough to stutter; lower `RPCPROBE_RX_BYTES_PER_VBLANK` in `rpcprobe_build.h`. |

If hellos arrive but reads are slow or time out now and then, run the link
check on the PC: `core\dsirpc_client.py --stats 60` (see DOCUMENTATION.md,
section 5). It compares what the PC sent with the `req` and `rx` counters.

No hellos at all means one of the startup steps failed. Check, in order:

1. The launcher ran in DSi mode and wrote `/RPCHAND.TXT`.
2. The build has `DSIRPC_KEEP_DSI_WIFI`.
3. The Windows firewall lets Python receive on the port.
4. The network passes broadcasts between Wi-Fi and the PC. If it doesn't,
   hellos never arrive but memory requests can still work: pass the IP
   the launcher showed to the PC tools with `--dsi-ip`.

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

- `rpcprobe: RPCHAND.TXT not found (run the launcher first)`,
  `rpcprobe: handoff loaded`, or `... found but no usable mac=/ip=`
- `rpcprobe: handoff ready, hellos will be broadcast`, or
  `rpcprobe: no usable RPCHAND.TXT, handoff off`

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

- **The SD card is only touched on the very first VBlank** (loading
  `RPCHAND.TXT`). Later, the game reads its save from the SD card outside
  interrupts, and SD access from the VBlank interrupt in the middle of that
  hangs the game (seen as a white screen).
- **Everything runs inside the VBlank interrupt,** so each tick has to stay
  short. The receive path reads at most `RPCPROBE_RX_BYTES_PER_VBLANK`
  bytes per VBlank, and no hello goes out in a tick that already sent a
  reply. `vb=` in the hellos shows the longest tick.
- **Space is tight.** `cardenginei_arm7` has a fixed 61 KB region.
  `RPCPROBE_REQUESTS 0` in `rpcprobe_build.h` builds a hello-only version,
  which is useful for ruling the receive path out.
