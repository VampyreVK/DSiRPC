# DSiRPC project history

> **This is the original project log, kept for history.** It was the repo's
> README while the project was being figured out, so parts of it are out of
> date: the memory-map section (party stats *are* encrypted, playtime is at
> `+0x9E`), the old DS-mode WPA2 driver plan, and the folder names (`vendor/`,
> `stage4-handoff-spike/`, `stage5-memory/`). For the current state, see the
> [README](../README.md) and [DOCUMENTATION.md](DOCUMENTATION.md). The progress
> log at the bottom is newest first.

## End goal

Code injected at boot alongside nds-bootstrap on a modded Nintendo DSi that reads
live game memory (test case: Pokemon Platinum, using memory addresses similar to
what RetroAchievements uses) and streams it over Wi-Fi/UDP to a PC, which drives
a custom Discord Rich Presence status. The DSi-side code needs to persist
alongside an actual running retail game, not run as a standalone/separately
launched homebrew app (DS/DSi has no multitasking for user code).

This file is the durable project log. Update it as work happens so a new chat
session can pick up context without re-deriving everything. Each major change
should get a short entry in the Progress Log at the bottom rather than editing
history away.

## Architecture decisions

- **Integration point: nds-bootstrap's retail cardengine VBlank hook.**
  `vendor/nds-bootstrap` has two build trees: `hb/` (homebrew loading, simple,
  no multitasking-friendly hook) and `retail/cardenginei` (retail ROM
  emulation via cardengine trickery, DSi-specific). `retail/cardenginei`
  already has a proven cheat-code interpreter
  (`arm7_cheat/source/cheat_engine.s`, ARM assembly, GPLv3, from NitroHax)
  invoked every VBlank (`code_handler_start_vblank` in
  `arm7/source/card_engine_header.s`) for the entire duration a retail DSi
  game plays, on ARM7, directly against Main RAM. This is the chosen
  injection point for persistent, alongside-the-game memory access.
- **DS side stays a dumb memory probe, not a parser.** The DS side listens
  for a requested address (or address range), and returns the raw memory at
  that address. All interpretation/parsing of what those bytes mean happens
  PC-side. This keeps the DS side minimal, expandable without new on-device
  builds, and avoids most of the testing/reliability burden — a change to
  what data we want is a PC-side parser change, not a new ROM build.
- **Test-ROM validation path (`stage3-testrom`) is abandoned.** It was built
  through `hb/`'s homebrew loader, which never exercises
  `retail/cardenginei`'s VBlank hook — the actual mechanism we need to
  prove out. Going straight at a real Pokemon Platinum ROM backup through
  the retail path is the only route that actually tests the real mechanism,
  so the synthetic test ROM doesn't buy us anything here. Kept in the repo
  for history only.
- **Memory map source of truth: RetroAchievements code notes**, cross-checked
  against Viv's earlier `vendor/melonDS-RPC-Suite-unfinished` research and
  ProjectPokemon's community breakpoints page, in that priority order. See
  "Memory map" below.

## ARM7 wifi-output gap — design complete, first draft written, UNTESTED

How to get probe-response data OUT over Wi-Fi from the ARM7 VBlank-hook
context. Stages 1-2 proved the pipe using dswifi9's BSD-socket API, which
only ever runs on ARM9 — and ARM9 is occupied by the actual retail game once
we're past the proof-of-concept stage. ARM7 has never hosted a full IP stack
in dswifi's history (checked both the current dswifi2.1.0+calico stack and
the old self-contained dswifi 0.4.2 — sgIP, the TCP/IP stack, has only ever
built for ARM9 in either generation).

**Resolution: skip the IP stack, keep the radio driver.** ARM7 has always
owned the actual wifi hardware and already does the full 802.11 auth/assoc
handshake plus raw frame TX/RX entirely on its own, in both dswifi
generations, with zero ARM9 involvement. sgIP only adds DHCP/ARP/TCP/sockets
on top — none of which a stateless UDP probe needs. So: port dswifi 0.4.2's
self-contained ARM7 driver (`wifi_arm7.c`, non-threaded, matches
nds-bootstrap's simple polled style — unlike the modern
dswifi2.1.0+calico/ntrwifi stack, which is RTOS-threaded and doesn't fit),
skip AP scanning entirely (hardcode the one target network instead of the
~150 lines of beacon/IE parsing scanning needs), and hand-roll a minimal
LLC/SNAP + IPv4 + UDP encapsulation around the driver's raw-frame-TX
primitive instead of sgIP.

First-draft implementation is written:
`vendor/nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/` (`probe_wifi.*`,
`probe_net.*`, `probe_hook.c`, plus new WPA2 support — see below). **Not yet
compiled, not yet wired into the actual build, not yet tested on hardware**
— see that folder's `INTEGRATION.md` for exact wiring steps and known-
unverified pieces (the riskiest being CCMP's AAD construction — flagged
clearly there).

**WPA2 is now supported, not just open networks.** The earlier framing here
("this driver only supports open networks") was based on a real but
incomplete understanding: Open System Authentication — what this driver has
always sent — is not the same thing as "no encryption." A WPA2 network uses
the exact same open-system auth/assoc frames; WPA2's actual security is a
separate 4-way handshake (EAPOL-Key frames) that runs *after* association,
followed by AES-CCMP encryption of data frames. So the existing auth/assoc
code didn't need to change — it just needed the handshake and CCMP layered
on top. That's now written: PBKDF2-HMAC-SHA1 (passphrase → PMK, chunked
across VBlanks so it doesn't stall a frame), the 4-way handshake state
machine, AES-128, and CCMP encrypt/decrypt on the data path. An open or WEP
network still works too (WEP's actual per-frame RC4 encryption still isn't
implemented, only association — arguably not worth finishing now that WPA2
is supported). See `INTEGRATION.md`'s "WPA2 — what's actually implemented"
section for the full breakdown of what's solid vs. still unverified.

**Nothing network-related is compiled in anymore.** SSID, BSSID, channel,
security mode, WPA2 passphrase, PC/DSi static IPs, and UDP port all live in
`/RPCPROBE.CFG` on the SD card, read at boot — see `INTEGRATION.md`'s
"Configuration" section for the file format and how it's read (a small
self-contained ARM7-side SD read, not nds-bootstrap's ARM9-side `.ini`
pipeline — see "Why not a TWiLight Menu++-style launcher" below for why).

**IP discovery**: kept the stage 1/2 pattern (DSi sends to a configured PC
IP; the PC learns the DSi's own IP from whatever address the first packet
arrives from, so it doesn't need to be told in advance) rather than having
the DSi display its IP on-screen for the user to enter PC-side. The
display-IP approach doesn't work at this integration point anyway — the
retail-game VBlank hook has no console/screen access of its own (Platinum
owns both screens), unlike `stage3-testrom`'s standalone homebrew context.

**Why not a TWiLight Menu++-style launcher**: nds-bootstrap does have a
real per-game `.ini` config system already (`retail/arm9/source/conf_sd.cpp`,
the same one TWiLight Menu++ itself uses) — but it's ARM9-only, and no
ARM9→ARM7 bridge for arbitrary app config was found anywhere in the
codebase. Building a whole separate launcher application (TWiLight Menu++
is a full multi-game frontend with its own UI and game database) to solve
"get a few settings to ARM7" would be a lot of new surface area for what
turned out to be a problem ARM7 could already solve on its own — cardengine.c
opens a named file off the SD card root today for its own debug log, and
`RpcProbeConfig_Load()` just follows that same pattern. Lower risk (nothing
shared gets touched) and less to build.

## Stage progress

- **Stage 1 — DONE.** `stage1-listen/`: standalone DSi homebrew app connects
  to Wi-Fi, sends one hardcoded UDP packet to a PC listener
  (`stage1-listen/pc/listener.py`). Proved the wifi pipe works end to end.
- **Stage 2 — DONE.** `stage2-echo/`: call-and-response test. DSi sends a
  startup ping, binds a UDP socket, and echoes back a reversed string for
  whatever it receives (`EXIT` breaks the loop). PC side
  (`stage2-echo/pc/echo_test.py`) auto-discovers the DSi's address from its
  startup ping rather than using a hardcoded IP.
- **Stage 3 — IN PROGRESS, pivoted.** Original plan was a synthetic test ROM
  (`stage3-testrom/`) to validate against known values before touching real
  game memory; abandoned per the decision above. Current direction: build the
  generic memory-probe protocol (request: address + length; response: raw
  bytes) and get it running inside `nds-bootstrap`'s `retail/cardenginei`
  VBlank hook against a real Pokemon Platinum ROM backup. The wire protocol
  is implemented: request is `'Q' + address(u32) + length(u16)` (7 bytes),
  response is `'A' + address(u32) + length(u16) + raw bytes` (7+N bytes),
  both over UDP port 4244. Responses are capped at 64 bytes on purpose —
  per Viv's call, lots of small polled requests beat one big payload, to
  avoid frame drops and to allow lazy-loading slow-changing fields (trainer
  name, etc.) separately from fast-changing ones. See the ARM7 wifi-output
  gap section below for where the implementation stands.

## Repo layout

- `stage1-listen/` — Stage 1 artifact (standalone, kept for reference).
- `stage2-echo/` — Stage 2 artifact (standalone, kept for reference).
- `stage3-testrom/` — Stage 3's abandoned test-ROM approach (kept for history).
- `vendor/nds-bootstrap/` — DS-Homebrew/nds-bootstrap, full clone.
  `retail/cardenginei/arm7/source/rpcprobe/` holds the new memory-probe wifi
  driver, including WPA2 support (first draft, unbuilt — see that folder's
  `INTEGRATION.md`). One existing file has been touched:
  `retail/cardenginei/arm7/Makefile` (added `source/rpcprobe` to `SOURCES`
  so the new files actually get compiled) — everything else in this clone
  is still untouched, including the VBlank hook wiring itself, which is
  flagged but deliberately not done yet (see `INTEGRATION.md`).
- `tools/rpcprobe-crypto-test/` — host-side (regular gcc, no devkitARM
  needed) test harness for the WPA2 crypto primitives (SHA-1, HMAC-SHA1,
  PBKDF2-HMAC-SHA1, AES-128, CCMP), checked against published test vectors.
  All passing as of this commit — see that folder's README.
- `vendor/melonDS-RPC-Suite-unfinished/` — Viv's earlier, separate project:
  partial Pokemon Platinum memory-mapping work against a modified melonDS
  (via melonDS-shmem), used here as a reference/cross-check, not as the
  source of truth.
- `docs/memory-map/` — Reference material pulled in for the Platinum memory
  map: raw RetroAchievements code notes export and ProjectPokemon's
  "Notable Breakpoints" page. See "Memory map" below for the digested,
  cross-checked version.

## Memory map (Pokemon Platinum (USA) (Rev 1))

All addresses below are hardware ARM9 addresses (`0x02000000`-based Main RAM).
RetroAchievements' own addressing scheme is offset by `-0x02000000` from
hardware (their docs: "system memory at address $00000000, immediately
followed by cartridge memory") — so an RA note address of `0x101d40` is
hardware `0x02101d40`. Keep that translation in mind when cross-referencing
`docs/memory-map/Pokemon Platinum Code Notes (RetroAchievements).md` directly.

**Anchor pointer: `0x02101D40`.** Static, never moves. Dereferencing it gives
the current address of the live save-data block (the game relocates this
block on the heap as it transitions overworld/menu/battle, so this pointer
must be re-resolved on every read, not cached). Confirmed independently by:
RA code notes (game 11732, note on `0x101d40`), a second independent RA note
on the same address from a related Platinum-hack game entry ("Professor Oak
Challenge", RA game notes doc, second block), and all three of Viv's earlier
melonDS-project docs. Also matches the `B2101D40` Action Replay code
convention referenced in that earlier research.

Offsets below are from the resolved live-save-block pointer unless noted
otherwise. Source column: RA = RetroAchievements code notes (community
vetted, treat as ground truth), PP = ProjectPokemon Notable Breakpoints
(community vetted), melonDS-doc = Viv's earlier project docs (treat as
unverified until cross-checked — see conflict note below).

| Offset / Address | Field | Size | Source |
|---|---|---|---|
| `+0x8C` | Trainer ID | 16-bit | RA (confirmed 2x independently) |
| `+0x8E` | Secret Trainer ID | 16-bit | RA (confirmed 2x independently) |
| `+0x90` | Money | 32-bit | RA (confirmed 2x independently) |
| `+0x7C` | Trainer Name | 16 bytes (8x u16, Gen4 char encoding) | melonDS-doc (`parser.py`), hand-verified by Viv via HxD/ImHex |
| `+0x96` | Badges Obtained | bitfield | RA |
| `+0xAC` | Party capacity (slots usable) / Playtime (unverified, see note) | 32-bit | RA / melonDS-doc |
| `+0xB0` | Party count (# Pokemon) | 32-bit | RA |
| `+0xB4` | Party Slot 1 data | 236 bytes | RA |
| `+0x1A0` / `+0x28C` / `+0x378` / `+0x464` / `+0x550` | Party Slots 2-6 | 236 bytes each | RA |
| `+0x644` | Bag — Items pocket start | 32-bit entries | RA (confirmed 2x independently) |
| `+0x8D8` | Bag — Key Items pocket start | 32-bit entries | RA |
| `+0x9A0` | Bag — TMs/HMs pocket start | 32-bit entries | RA |
| `+0xB30` | Bag — Mail pocket start | 32-bit entries | RA |
| `+0xB60` | Bag — Medicine pocket start | 32-bit entries | RA |
| `+0xC00` | Bag — Berries pocket start | 32-bit entries | RA |
| `+0xD00` | Bag — Poke Balls pocket start | 32-bit entries | RA |
| `+0xD3C` | Bag — Battle Items pocket start | 32-bit entries | RA |
| `+0x1294` | Current Map ID | 16/32-bit (RA notes disagree on width) | RA (2 notes) |
| `+0x12AC` | Pokedex caught flags | bitfield | RA |
| `+0x1380` | Pokedex seen flags (National Dex order) | 62 bytes | RA |
| `+0x1656` | Pokedex available flag | bit0 | RA |
| `+0x1657` | National Dex obtained flag | bit0 | RA |
| `+0x285AC..+0x285C8` | Per-badge "shining" flags (8 badges, 4 bytes apart) | 32-bit each | RA |

Within a 236-byte **party** Pokemon struct (offsets below are relative to the
start of that Pokemon's own 236 bytes, e.g. `+0xB4 +0x8C` for lead's level):

| Offset | Field | Size | Source |
|---|---|---|---|
| `+0x8C` | Current level | 8-bit | RA / melonDS-doc (agree) |
| `+0x8E` | Current HP | 16-bit | RA / melonDS-doc (agree) |
| `+0x90` | Max HP | 16-bit | RA / melonDS-doc (agree) |

This unencrypted battle-stat tail (bytes `0x88`-`0xEB` of the 236-byte
struct) is why level/HP don't need the full Gen4 decrypt/unshuffle
pipeline — only the first 136 bytes (species, IVs, PID, etc.) are encrypted
and block-shuffled.

**Overworld player position** — direct hardware addresses (not anchor-relative,
per RA note, described as "mirror" values): X `0x021C5CCE`, Y `0x021C5CD2`,
Z `0x021C5CD6`, all 16-bit. These come from RA and should be preferred over
the melonDS-doc's guessed `0x0223B48A`-range addresses (see conflict note).

**Trainer name conflict — resolved.** Viv's three earlier melonDS-project
docs disagreed on the trainer-name offset (`+0x64`, `+0x68`, `+0x7C` were all
seen). Per Viv: `parser.py`'s `+0x7C` is the one she hand-verified against
real save data with HxD/ImHex and trusts (it was the first field she parsed
and tested reliably) — treat `parser.py` as accurate going forward unless a
specific field is later shown otherwise. This also lines up structurally
with RA's data: `+0x7C` + 16 bytes = `+0x8C`, exactly where RA's
independently-confirmed Trainer ID begins — i.e. the trainer name field
fits perfectly in the gap immediately before it, which is good corroborating
evidence on top of Viv's own testing.

**Playtime — still unverified.** `parser.py`'s `+0xAC` is the current
working guess (per the same "trust parser.py for now" call above), but
unlike trainer name it hasn't been independently hand-verified or cross-
checked against RA (RA's notes don't cover it), and it collides with RA's
confirmed "party capacity" field at the same offset — worth resolving before
relying on it, e.g. by checking whether party capacity is even a real,
separately-stored field in Platinum (it might always just equal 6) versus
Viv's parser having mis-identified playtime's true offset.

**Not yet extracted from RA notes:** battle-state detection (in-battle
flag), opponent Pokemon data during battle, player facing/movement state.
The raw RA export (`docs/memory-map/Pokemon Platinum Code Notes
(RetroAchievements).md`) is large (~160 notes, 6.5MB raw scrape) and has
plenty more in it than what's digested above — grep it for anything not yet
in this table before assuming it's missing from RA entirely.

## Progress log

- 2026-09-26: **Livelier battles in the overlay.** Hardware check of the
  stutter fix: smooth in play, with `vb=` steady around 76 scanlines (about
  4.8 ms, once a second, most likely the tick that sends the hello). The
  battle view now has a background drawn in code (time of day, clouds, hills,
  terrain from the location name, weather from the save), both Pokémon placed
  like `process_diorama.py` does, slide-in, lunge, hit and faint animations,
  and a move panel with type colours and PP. The parser now reads each
  battler's current PP and PP Ups (BattleMon `+0x2C`/`+0x30`), and
  `platinum_data` has move types and weather names from the decomp.
- 2026-09-25: **Stutter fix and a stream overlay window.** The in-game side
  used to drain every frame the Wi-Fi chip received (including other
  devices' broadcasts, up to ~1.5 KB) in one VBlank interrupt, one SDIO
  command per byte, which could hold up the game's own ARM7 work for
  several milliseconds. It now drains at most 128 bytes per VBlank
  (`RPCPROBE_RX_BYTES_PER_VBLANK`), no hello goes out in a tick that
  already sent a reply, and the hellos report the longest tick as `vb=`
  (scanlines). Built and checked against a simulated chip mailbox; needs a
  hardware check. The DS's ~59.83 Hz refresh is normal and wasn't the
  cause. Also new: `core/hub.py` (the state hub), `core/demo.py`, and
  `dsirpc_overlay.py`, a pixel-art party/battle window for OBS that can run
  the Rich Presence too (`--discord`).
- 2026-09-23 (night): **Zero-config SD card and a persistent presence.**
  The in-game side now broadcasts its hellos to 255.255.255.255, so it no
  longer needs the PC's IP. `RPCPROBE.CFG` and all the code reading it are
  gone (the ARM7 engine is about 1.3 KB smaller), and the launcher
  broadcasts its test packets too. The only SD file left is the launcher's
  own `RPCHAND.TXT`. `dsirpc.py` now runs until stopped: it waits for the
  DSi, connects to Discord only while the game answers, clears the
  presence after about 30 s of silence and waits again. Both were built and
  tested against a simulated DSi in the cloud.
- 2026-09-23 (night): **Renames, CI and two fixes.** `dsi_battle_rpc.py`
  became `dsirpc.py` and `Affinity/` became `art-source/`. A GitHub Action
  (`.github/workflows/build.yml`) builds both `.nds` files and publishes a
  release for `v*` tags. Clean debug builds compile again (GCC 14 fixes in
  upstream's debug-only `my_fat.c`/`my_sd.c` code), and rival battles show
  the name you gave your rival (`S+0x27FC`).
- 2026-09-23 (evening): **Repo restructured into DSiRPC.** The
  melonDS-RPC-Suite repo became the main repo (its git history and `Assets/`
  paths are unchanged, so GitHub Pages keeps working after the rename to
  DSiRPC). nds-bootstrap moved from `vendor/` to `nds-bootstrap/` as a plain
  copy of upstream `f5f9ea48` plus our changes (see its `DSIRPC_CHANGES.md`).
  Stage 4 became `launcher/`, the stage 5 client became
  `core/dsirpc_client.py`, and stages 1-3 moved to `spikes/`. Removed: the
  compiled-out DS-mode WPA2 driver and its crypto tests (nds-bootstrap still
  builds, and the ARM7 binary is 688 bytes smaller), the melonDS TCP path,
  the old AI research notes (distilled into `docs/research.md`), and build
  leftovers. `RPCPROBE.CFG` now only needs `pc_ip=`.
- 2026-09-23: **Rich Presence works end to end on hardware.** Stage 5 reads
  passed on hardware, 30 of 30 correct. The party-menu black screen was stale
  debug object files, fixed by rebuilding every source. The melonDS suite now
  reads the DSi (`core/dsi_memory.py`) and decrypts the party. It also has
  `dsi_status.py` for a plain-text readout and `dsi_battle_rpc.py` for the
  Discord presence: Competing in battles and Playing in the overworld, with
  shiny-aware sprites and a walking trainer that follows your facing. **The
  full current reference is now `DOCUMENTATION.md`.** The memory map section
  above is out of date: party battle stats are encrypted, and playtime is at
  `+0x9E`.
- 2026-09-22 (night): **Handoff works end to end in gameplay.** Viv loaded
  her save and the DSi kept sending for 6+ minutes. The fixes that got
  there: rpcprobe only touches the SD card on the first VBlank (VBlank log
  writes were colliding with the game's own save reads and hanging it); the
  wifi board stays in DSi mode (`DSIRPC_KEEP_DSI_WIFI 1`; DS mode loses the
  association); and a Platinum US Rev 1 patch
  (`DSIRPC_PLATINUM_NO_WIRELESS_SEARCH` in `bootloaderi/.../patch_common.c`)
  turns the main menu's DS-mode wireless search into a no-op. Addresses
  were found by scanning the ROM, and the code matches pret/pokeplatinum.
  Opening the party menu crashed once, so `-DDEBUG` is off again (prime
  suspect). **Stage 5 built, not yet run on hardware:** batched memory
  requests (`rpcprobe/probe_req.c`, polled receive path in `twl_wifi.c`,
  ARP replies), the old WPA2 code compiled out (~9.8 KB freed), and the PC
  client `stage5-memory/pc/dsirpc_client.py` (tested against a local fake
  DSi). Direction noted for the PC side: evaluate RetroAchievements' Rich
  Presence script locally with rcheevos and drive Discord directly.
- 2026-09-22 (evening): **DSi-mode connection confirmed on hardware.** The
  spike connected via the saved slot 4 WPA2 settings (Viv: "the connection
  works"). The router's client list turned out to be useless for testing
  the handoff (it kept listing a powered-off DSi for 5+ minutes), so the
  in-game side now sends its own proof packet. Built the first handoff
  version, **not yet built or run**:
  - `bootloaderi/source/arm7/main.arm7.c`: `DSIRPC_KEEP_DSI_WIFI` stops
    nds-bootstrap switching the wifi board into DS mode. Platinum's own wifi
    is off as a result, which Viv is fine with.
  - `rpcprobe/probe_hook.c`: `RPCPROBE_TWL_HANDOFF` switches the old DS-mode
    path off.
  - `rpcprobe/twl_wifi.c`: new, CMD52-only send path through the DSi-mode
    chip, cut down from DSWiFi.
  - `rpcprobe_config.c`: reads `/RPCHAND.TXT` from the launcher.
  - The in-game side sends one UDP hello per second. The PC side is
    `stage4-handoff-spike/pc/hello_listener.py`.
  - All new code passes a syntax check with -Wall -Wextra. Estimated at
    ~1.9 KB of the 3.9 KB free ARM7 space.
  - Next: the direct chainload from the launcher (`stage4-handoff-spike/CHAINLOAD.md`),
    then the receive path and group-key renewals.
- 2026-09-22 (later): Got `-DDEBUG` logging working (it needed four fixes
  to nds-bootstrap's own debug-only code, plus stale object files forced to
  rebuild). The first real log showed rpcprobe suspending itself right after
  init. Cause: the "is the game using wifi?" check reads `0x04808012`, which
  is a mirror of `W_IE`, and our own init sets `W_IE = 0x40B3`. That same
  register also feeds nds-bootstrap's own wifi-in-use flag, which is a
  suspect for the pause-menu glitches. An earlier guessed fix (writing to
  0x8012) was wrong and has been reverted. **Direction change under
  evaluation:** use the DSi's native wifi mode instead of hand-rolled WPA2.
  In DSi mode the chip encrypts packets itself, and BlocksDS DSWiFi already
  connects to the saved slot 4-6 WPA2 settings. The DSi-mode driver still
  handles the handshake and group-key renewals in software. Built
  `stage4-handoff-spike/` to test whether a connection made by a
  launcher-style app survives into gameplay under nds-bootstrap. See its
  README for the test protocol. Not yet run on hardware.
- 2026-09-22 (cont'd): Corrected a wrong framing from earlier today — Open
  System Authentication (what the driver already sends) isn't the same as
  "unencrypted network," so WPA2 didn't need a separate open/guest network
  after all, just the 4-way handshake + CCMP layered on top of the existing
  auth/assoc code. Implemented WPA2-Personal support in full: SHA-1,
  HMAC-SHA1, PBKDF2-HMAC-SHA1 (chunked across VBlanks — PMK derivation is
  ~4096 iterations, too slow to do in one tick without a visible stall),
  AES-128 (encrypt-only — CCM never needs decrypt), CCMP frame
  encrypt/decrypt, and the 4-way handshake state machine. Moved every
  network-related setting (SSID, BSSID, channel, security, WPA2 passphrase,
  static IPs, port) out of compile-time `#define`s into `/RPCPROBE.CFG` on
  the SD card, read at boot via nds-bootstrap's existing ARM7-side FAT
  access (found `getBootFileCluster()` already does exactly this for
  cardengine's own debug log — reused that pattern instead of building an
  ARM9→ARM7 config bridge or a separate launcher app). Confirmed IP
  discovery should stay the stage 1/2 pattern (DSi → configured PC IP; PC
  learns DSi's IP from the first packet) rather than an on-screen-IP
  approach, since the retail VBlank hook has no screen access to display
  one. All new code lives alongside the existing rpcprobe files — see that
  folder's INTEGRATION.md for the full breakdown, especially CCMP's AAD
  construction, which is the riskiest untested piece. Still needed from
  Viv: the actual SSID/WPA2 passphrase for the target network, and its
  BSSID/channel, to put in `/RPCPROBE.CFG`.
- 2026-09-22: Viv supplied real RA code notes export + ProjectPokemon
  breakpoints doc (used last session) and confirmed trainer name's offset
  (`+0x7C`, hand-verified via HxD/ImHex) — see Memory map section, conflict
  now resolved. Main focus: the ARM7 wifi-output gap. Read dswifi 0.4.2's
  full ARM7 driver source (`wifi_arm7.c`) and confirmed nds-bootstrap's
  retail cardengine does NOT run its own wifi stack today (only watches
  REG_WIFIIRQ to pause DMA during the game's own wifi use) — so there's
  nothing to conflict with. Wrote a first-draft, unbuilt implementation:
  ported the driver's hardware bring-up + raw-frame TX/RX + auth/assoc,
  dropped AP scanning in favor of hardcoded target-network config, and
  hand-rolled a minimal LLC/SNAP+IPv4+UDP framing layer in place of sgIP.
  Lives in `vendor/nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/` —
  see that folder's INTEGRATION.md for wiring steps, what's unverified, and
  the network config (AP BSSID/channel, security, PC MAC, static IPs)
  needed from Viv before a build attempt. Key open decision surfaced: this
  driver only supports open/unencrypted auth correctly right now, not
  WPA/WPA2 — needs a dedicated open (or WEP) network, separate from a WPA2
  home network, for testing.
- 2026-09-21: Stages 1-2 confirmed working on hardware. Read through
  nds-bootstrap's `hb/` and `retail/cardenginei` source; identified the
  VBlank cheat-engine hook as the integration point. Read Viv's earlier
  melonDS-RPC-Suite-unfinished project for prior Platinum memory-map work.
  Researched RetroAchievements' code-notes API (undocumented "Connect API",
  `GET /dorequest.php?r=codenotes2&g=<gameID>`, Platinum's RA game ID is
  11732) — confirmed to exist via the `go-retroachievements` client source,
  but blocked by egress allowlists in both sandboxes, so couldn't pull it
  live. Viv supplied real RA code notes + ProjectPokemon breakpoints exports
  directly; cross-checked against melonDS-project docs (see Memory map
  section above for the resolved table and open conflicts). Decided:
  abandon `stage3-testrom`, go straight at real Platinum through
  `retail/cardenginei`; DS side will be a generic address/range memory
  probe rather than doing any parsing on-device. Created this README.
