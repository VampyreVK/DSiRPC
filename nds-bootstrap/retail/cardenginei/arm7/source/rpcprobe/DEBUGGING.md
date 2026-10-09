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

Watch them with `tools/hello_listener.py` (in the repo root).

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
| `a9` | The ARM9 half of the per-frame capture. `1`: rpcprobe found it in the ARM9 cardengine, so captured values are read by the ARM9 (through its cache). `2`: found, and its VBlank hook is in (it goes in when a capture starts). `3` to `5`: the game replaced its VBlank handler and the hook was put back (`a9` is 1 + hooks put in; after four, the ARM7 reads by itself). `0`: an ARM9 cardengine without it (DLDI or GSDD variant, or an older build), so the ARM7 reads main RAM itself. Older builds don't send `a9`. |
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

### The achievement checker's report

With a set loaded for offline play (`RPCSET.BIN`, see `probe_ach.c`), the
VBlank after each hello also sends:

```
DSiRPC ach n=N t=N p=N l=N s=N x=N w=N f=N fr=N fd=N fc=N h=N st=XXXXXXXX ids=ID,ID,...
```

DSiRPC logs these (`Console: ...` lines in `logs\dsirpc.log`).

| Field | Meaning |
|---|---|
| `n` | Achievements the checker runs (both lanes). Below 0, why it doesn't: `-1` `RPCSET.BIN` isn't a version 2, 3 or 4 set (DSiRPC and the launcher are from a different release than this nds-bootstrap), `-2` it's another game's set (the game wasn't started from the launcher), `-3` too big for its 250 KB (256 KB less the 4 KB `RPCUNLK.BIN` is read into and the capture's 2 KB ring), `-4` a program doesn't add up, `-5` damaged (CRC-32). No report at all: there's no `RPCSET.BIN` (no set for this game, or it wasn't started from the launcher). |
| `t` | Achievements it has unlocked since the game started |
| `p` | Passes over the pass lane since the last report (about a second). A pass is rcheevos' "frame": the higher, the closer to checking every frame. |
| `l` | The most scanlines it used in one VBlank since the last report. With `h=1`, that's the frame lane's sampling (DSiRPC sizes it to about 19 at most); with `h=0`, the sampling plus its checking (`RPCPROBE_ACH_LINES_PER_VBLANK` is that budget, 20; it can go a scanline or two over, since it checks the time every 8 conditions). `vb=` in the hello includes it. |
| `s` | Of those, how many were saved to `RPCUNLK.BIN` |
| `x` | Of those, how many couldn't be: no `RPCUNLK.BIN` (the game wasn't started from the launcher), the file is full (255 unlocks wait for DSiRPC), more than 7 waiting to be saved at once, or a write that failed |
| `w` | This game's unlocks already waiting in `RPCUNLK.BIN` when it started; those aren't checked again |
| `f` | Of the `n`, how many are checked every frame (the set's frame lane) |
| `fr` | Frame lane samples checked since the last report: about 60 a second when it keeps up |
| `fd` | Frames the frame lane couldn't sample since the last report, because its checking had fallen 8 frames behind (the game's ARM7 had little idle time, or the frame lane is too big for this game). Should be 0. |
| `fc` | Samples taken without the ARM9's data cache write-back first (its VBlank hook isn't in: the game replaced its VBlank handler, or the doorbell couldn't ring yet). Should be 0 after the first second; rpcprobe rings again while it isn't. |
| `h` | 1: the checking runs in the game's idle time (nds-bootstrap's swiHalt hook). 0: in the VBlank (that hook hasn't run for half a second: a game whose swiHalt nds-bootstrap couldn't hook) |
| `st` | The set's stamp (its CRC-32): DSiRPC knows from it which achievements the console checks, and leaves them to it |
| `ids` | The latest unlocks, at most 8 (as many as fit) |

`s` should follow `t` within a frame. If `t` goes up and `s` doesn't (and
`x` doesn't either), nothing is saving them: the swiHalt hook isn't running
and the VBlank fallback hasn't kicked in (`RPCPROBE_ACH_SAVE_FALLBACK`, two
seconds).

If the game stutters with a set loaded and not without one (rename
`RPCSET.BIN` to test), look at `l=` first: a large frame lane's sampling
can be made smaller on the PC side (`FRAME_SAMPLE_CYCLES` in DSiRPC's
`core/offline.py`). With `h=1`, lower `RPCPROBE_ACH_IDLE_LINES_PER_VISIT`
or `RPCPROBE_ACH_IDLE_LINES_PER_FRAME`; with `h=0`, lower
`RPCPROBE_ACH_LINES_PER_VBLANK`. `RPCPROBE_ACH 0` builds without the
checker.

## 2. RAM viewer status byte

`probe_hook.c` keeps a one-byte status, `probeStatusByte`, that you can
watch with nds-bootstrap's in-game menu RAM viewer. That menu relays ARM7
memory too.

- bit 7: set once the state machine has run
- bits 4-6: stage (0 loading files, 1 probing the chip, 2 sending,
  3 failed, 4 waiting to switch the board back to DSi mode, 5 Wi-Fi off
  because the lid closed on a DSi)
- bits 0-3: low 4 bits of the hello count

For example, `A5` means sending, 5th packet (mod 16), `B0` means failed,
and `D` followed by anything means the lid closed (on a DSi) and the Wi-Fi
is off.

The address changes between builds. After building, look it up in the ELF.
From PowerShell, in the repo root:

```
docker run --rm -v "C:\Projects\DSiRPC\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 /opt/devkitpro/devkitARM/bin/arm-none-eabi-nm retail/cardenginei/arm7/build/cardenginei_arm7.elf | findstr probeStatusByte
```

### The in-game menu's achievements

The main screen of nds-bootstrap's in-game menu (L + Down + SELECT) says
what the checker is doing: "Achievements: 12 of 102 earned", or why there
are none ("no set loaded": the game wasn't started from the launcher;
"checking set": the CRC isn't done yet; "set damaged", "set too big",
"another game's", "set version?": DSiRPC and this nds-bootstrap are from
different releases; "set not loaded": its program doesn't add up; "sync to
list": a version 2 set, without the list). Nothing at all means no
anchor: this isn't DSiRPC's nds-bootstrap, or the game runs in DSi mode. The
anchor is at `DSIRPC_ACH_LOCATION` + 40 (`0x0CFA0028`) if you want to look
at it with the RAM viewer: `"DRMA"`, the game code, the status, the last
unlock number, the one the menu last saw, open, and the list's offset
(`common/include/dsirpc_ach_menu.h`).

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

- **The VBlank only reads the SD card on the very first VBlank** (loading
  `RPCHAND.TXT`, `RPCSET.BIN` and `RPCUNLK.BIN`). Later, the game reads its save from the SD card outside
  interrupts, and SD access from the VBlank interrupt in the middle of that
  hangs the game (seen as a white screen).
- **Unlocks are saved outside interrupts, under nds-bootstrap's lock.**
  `Probe_HaltTick()`, called from nds-bootstrap's swiHalt hook
  (`runCardEngineCheckHalt()`), writes one 16-byte `RPCUNLK.BIN` slot at a
  time, only when `tryLockMutex(&saveMutex)` succeeds: the same lock
  nds-bootstrap's own save and ROM reads hold. Only if that hook hasn't run
  for `RPCPROBE_ACH_SAVE_FALLBACK` VBlanks (a game whose swiHalt couldn't be
  hooked) does the VBlank save them, with the same lock and only when no
  non-blocking ROM read is under way (`readOngoing`).
- **Everything runs inside the VBlank interrupt,** so each tick has to stay
  short. The receive path reads at most `RPCPROBE_RX53_FRAMES_PER_VBLANK`
  frames or `RPCPROBE_RX53_BYTES_PER_VBLANK` bytes per VBlank with CMD53
  (`RPCPROBE_RX_BYTES_PER_VBLANK` with CMD52), and no hello goes out in a
  tick that already sent a reply. The checker reads the console's clock
  only when an achievement unlocks (about 1 ms, only while the game isn't
  using the clock). `vb=` in the hellos shows the longest tick.
- **A DSi mustn't sleep while the chip is connected.** It shuts off
  instead (a 3DS doesn't). When the lid closes on a DSi, `Probe_LidClosed()`
  sends a "DSiRPC lid" packet (DSiRPC logs `Console: its lid closed ...`, so
  the log shows it ran), disconnects the chip and turns its interrupts off
  (`TwlWifi_Shutdown()`, what the launcher's DSWiFi does when it goes
  offline), then cuts the chip's SDIO power (BPTWL[30h] bit 4, which also
  turns the Wi-Fi LED off), all before the game gets to its sleep. rpcprobe
  stays off the Wi-Fi for the rest of the game. nds-bootstrap's in-game menu
  calls it too, before its own sleep. This works on hardware (a DSi XL).
- **The achievement LED only changes from the VBlank.** The LED of
  TWiLight's ROM read LED setting pulses while achievements unlocked this
  game haven't been seen in the in-game menu (`probe_led.c`). nds-bootstrap's
  own ROM read flashes, which used the I2C bus outside interrupts, are off in
  this build (`cardReadLED()` returns at once), so the two never fight over
  the bus.
- **Space is tight.** `cardenginei_arm7` has a fixed 61 KB region (about
  1 KB is left: 61,460 of 62,464 bytes). The achievement checker keeps its
  set and state in main RAM (`DSIRPC_ACH_LOCATION`) for that reason, and
  so does the per-frame capture's ring (`DSIRPC_WATCH_RING_LOCATION`).
  `RPCPROBE_REQUESTS 0` in `rpcprobe_build.h` builds a hello-only version,
  which is useful for ruling the receive path out.
