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

## Architecture decisions

*The plan as of 2026-09-22. The hook actually used is `myIrqHandlerVBlank`
in the ARM7 cardengine calling `Probe_VBlankTick()` (DOCUMENTATION.md,
section 8).*

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

## ARM7 wifi-output gap (superseded: this driver was removed on 2026-09-23)

*The launcher's DSi-mode handoff replaced it before it ever ran on hardware;
see the progress log and DOCUMENTATION.md, section 1.*

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

*As of 2026-09-22. The protocol became `'R'`/`'D'` with up to 16 ranges and
192 bytes a request (DOCUMENTATION.md, section 7).*

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
  gap section above for where the implementation stood.

## Repo layout

*As of 2026-09-22. The current layout is in DOCUMENTATION.md, section 13.*

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

*Superseded by DOCUMENTATION.md, section 9, which has the verified map; some
entries below are wrong (see the note at the top).*

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

- 2026-10-10 (later): **Black and White's slow battles: what the logs and
  the RAM dump say.** Viv's next session (a new save) played a whole rival
  battle and five minutes without freezing, but battles still loaded slowly
  (the first HP change came 96 s after the battle started). The RAM dump
  Viv sent is from the day before (6:47 playtime, Seen 3, Caught 1: the
  16:49 session), on the build with the checker at `0x0CFB0000` (its set,
  "DRSE" IRBO, is there), and not in a battle; it does show the bug fixed
  just before on hardware: nds-bootstrap's slot table (`0x027D8000`) has
  751 slots, the last three at `0x0CFF0000`-`0x0CFFC000`. The cache wasn't
  churning (353 of 751 slots used, no sector twice), and the last ROM read
  was an ordinary 16 KB fill. Nothing found ties slow loads to DSiRPC's code:
  Black and White's ROM reads go through the ARM7's IPC interrupt (its
  swiHalt hook never runs: the checker's `h=0`), in non-blocking steps the
  ARM9 re-pings every millisecond; the checker's VBlank turn is 34 to 44
  scanlines in battle and a reply tick about 76; the ARM9's cache write-back
  is 128 clean-by-index instructions; the IPC doorbell (3) only finishes a
  card DMA when nds-bootstrap's 'DMA9' marker is set. Next: time a battle
  with stock nds-bootstrap in DS mode (the mode DSiRPC needs) and with
  DSiRPC quit on the PC. To read the Wi-Fi side's cost from any log, DSiRPC
  now logs the hellos' `vb=` (longest and median), and their `rx` and `req`
  rates, once a minute.

- 2026-10-10: **Pokémon Black and White freezing, the real cause (likely),
  and fixes from Viv's Mac logs.** `romLocationAdjust()` (bootloaderi's
  `main.arm7.c`) checks upstream's skips first and DSiRPC's jump past the
  checker's memory last, so a ROM cache slot pushed past the checker landed
  on `0x0CFE0000` with nothing left to skip it, and the slots after it
  followed: for Black and White in DS mode (unit code 2, pkmnGen5), the
  cache's last 7 slots (112 KB; 3 with the checker at `0x0CFB0000`) sat in
  the top 128 KB the game uses, which upstream never touches (a simulation
  of the slot table: upstream ends at `0x0CFDC000`). Once the game had read
  about 12 MB of ROM, ROM data overwrote its memory: freezes a few minutes
  in, or in the intro. The jump now skips that 128 KB too for a DSi-enhanced
  game (744 slots, the last at `0x0CF9C000`). Viv's `dsirpc.log` also showed
  the checker's report going quiet and "its memory doesn't look the way
  DSiRPC expects" half a minute before a freeze. Also from those logs:
  quitting after the DSi had gone quiet crashed (`set_watch` with no IP:
  `_exchange` now raises `TimeoutError`, which every caller handles); the
  per-frame drain crashed on records of another watch list after the console
  came back (`FrameCapture.service` now sends its list again); the macOS
  app had no Black and White art (no download has `Assets/PokemonBlackUI`,
  and `unova_art.py`, unlike `sprites.py`, never downloaded: it now fetches
  a missing sheet in the background, and the battle background isn't cached
  while one is on its way); and the Dock icon was the full-bleed export, so
  it's now drawn on macOS's grid (824 of 1024 pixels, with a soft shadow).

- 2026-10-09: **Pokémon Black and White freezing, fixed (likely).** The
  in-game achievement checker's memory (`DSIRPC_ACH_LOCATION`, 256 KB) was at
  `0x0CFB0000`-`0x0CFF0000`, but a DSi-enhanced game (unit code > 0) uses the
  top 128 KB of the 16 MB, `0x0CFE0000` up (`0x02FE0000`, the same RAM;
  nds-bootstrap keeps its ROM cache out of it for those games too). So the
  checker's last 64 KB, the unlock file (read from the SD card at the start)
  and the per-frame capture's ring (written every VBlank), overwrote Black
  and White's memory: random freezes, and likely the Pokémon missing from
  the intro. Platinum, a plain DS game, keeps that memory elsewhere, so it
  was never hit. The area now ends at `0x0CFE0000`. Whether the minute-long
  battle loads were the same thing is still to be seen on Viv's DSi.

- 2026-10-09: **A macOS app.** `DSiRPC-<version>-macos.zip` (the `macos`
  job, `packaging/macos/build_app.py`): DSiRPC.app, made with PyInstaller,
  for Apple silicon, with Viv's icon set (`Assets/icons/adaptive.icns`). It's
  the tray as a menu bar icon with the same menu; setup stays the console
  wizard, run in Terminal (by itself the first time); Open at Login is a
  launch agent. macOS wants the menu bar and any window on the main thread,
  so the overlay window is a process of its own there (`overlay/remote.py`,
  fed the hub's snapshots through a pipe; tried headless on Linux with the
  demo hub) and icon/menu changes are handed to the main thread. The app
  writes to `~/Library/Application Support/DSiRPC` (`core/paths.py`), bundles
  `certifi` for HTTPS, builds the rcheevos library as a `.dylib`, and runs a
  `selfcheck` in CI. Not signed with a Developer ID (no paid Apple account),
  so the first launch is right-click > Open. Windows is unchanged. First
  test on Viv's Mac: the overlay window flashed black and closed, as it
  drew its first frame before the first snapshot came through the pipe
  (_PipeHub started with None); it starts with an empty Snapshot now, like
  a StateHub, and a state that can't be pickled is skipped, not fatal.
  Second test: text drawn on the canvas showed as black boxes, and the
  header's glow and the battle backgrounds were missing. A Mac's window has
  an alpha byte; the canvas, converted to its format, got pixels pygame
  blends onto with alpha 0, which a Mac shows black. The canvas is plain
  32-bit RGB now on every platform, and present() scales it in its own
  format and blits it, which converts it properly. On a Mac the window is a
  pygame.Window with allow_high_dpi (Retina pixels, so the canvas scales up
  by a whole number and stays sharp), with DSiRPC's icon for the Dock.

- 2026-10-09: **The launcher's icon on a 3DS.** On Viv's 3DS (TWiLight
  Menu++) three of the icon's four frames had scrambled colours: ndstool
  gives each frame its own palette, sorted by colour, and the all-lit
  frame had one colour fewer (no unlit arc), so its palette was shifted,
  and the menu draws every frame with one palette. The unlit arcs are now
  the speakers' colour, so every frame has the same colours and the same
  palette (tools/make_pixel_dsi.py checks it). The DSi stays 31 wide (a
  32-wide version, centred, was tried and taken back: Viv prefers the
  original), so it's a pixel off centre in the 32x32 icon.

- 2026-10-09: **The pixel DSi everywhere.** A third console picture for
  Discord, "Pixel DSi" (`Assets/Consoles/Pixel.gif`): the waiting screen's
  DSi looking for a connection, animated, with room around it for Discord's
  round picture. The launcher has it as its animated icon too, redrawn
  32x32 to fill the icon (its six lines as four at that size, and its
  colours the DS's own 15-bit ones, so the menu shows exactly the GIF), and
  is now "DSiRPC / RPC & RA Tracking / VampyreVK" in the DSi's menus. Both
  are made by `tools/make_pixel_dsi.py`, checked with BlocksDS's ndstool
  (an animated banner, 4 frames of 400 ms, every frame the same as the GIF).

- 2026-10-09: **The waiting screen knows the DSi's there, and a new DSi.**
  The launcher syncs with DSiRPC as soon as it's connected (and again when
  you pick a game), so the waiting screen now shows "DSi connected!" with a
  green Wi-Fi sign and step 1 ticked off, then "Starting <game>..." until the
  game says hello; the tray's status says the same. The DSi icon is redrawn
  after Viv's mockup: 35 pixels wide so both screens have even margins (it
  was 5 px left and 4 right), darker colours, speakers on the lid, the
  buttons moved, and the bottom screen's six lines of text, finer than a
  pixel, drawn at the window's resolution.

- 2026-10-09: **The party fraction leads Discord's second line.** Black and
  White's overworld line reads `1/1 PKMN | 0 Badges | Seen: 3 | Caught: 1`,
  in place of Discord's own "(1 of 1)" after it (the Subway, Institute and
  League lines start with it too).

- 2026-10-09: **Black and White's Discord text, trimmed.** The second line
  is now `Badges | Seen | Caught`, and the achievements moved to the big
  picture's text, which Discord shows as a third line (the place's trainers
  and items only show there when there are no achievements). The season's
  name is gone from Discord and the overlay's header, since it seldom
  changes: it still shows in its icon and effects.

- 2026-10-09: **The third line takes turns, and the season's back in the
  header.** Discord's third line now swaps every 30 s between the
  achievements and the place's trainers beaten and items found (when there
  are any), or only the Repel's steps left while one's active. The overlay's header reads `Castelia City • Summer`
  again (the season in its colour; the font got a `•`), and the footer has
  the Pokédex's seen above caught.

- 2026-10-09: **The party screen.** **V** used to cycle auto / party only /
  battle only, and a forgotten "party only" kept battles off the overlay.
  Now it opens a party screen of its own (moves with PP, nature, held item;
  live HP and PP in battle) and goes back to the battle or the main view,
  and a battle starting or ending resets it. Black and White's held items
  are named, Gen V's own included (`bw_data.ITEMS`, from IronMon Tracker's
  Gen 5 table: Gen IV's numbering with a few slots reused and the new items
  from 468 on).

- 2026-10-09: **Discord's Unova pictures, adjusted.** Hilbert and Hilda are
  drawn 3x (Viv's pick of the sizes tried), filling Discord's round picture, and
  the Pokémon on the Unova turfs face right like Platinum's dioramas (they
  had been mirrored the overlay's way).

- 2026-10-09: **Discord's Unova GIFs without trails, and the trainer's
  gait.** The GIFs only ever added pixels (`disposal=1`), so where a Pokémon
  moved away its old pixels stayed: they trailed. `process_unova.py` now
  writes them itself, clearing just the Pokémon's rectangle after a frame
  when the next one needs pixels gone and keeping the turf, checked frame
  by frame with Pillow, ffmpeg and ImageMagick, at about the same size.
  Discord's trainer now stands, walks, runs or rides like the overlay's
  ("Biking through Route 4"), held through short stops.

- 2026-10-09: **Black and White: the trainer walks when you walk.** With
  `dsirpc_client.py --watch` (new: prints whatever changes in some ranges)
  Viv confirmed the facing on a console. Between full reads the hub now
  reads the player's map object every 0.3 s, so the footer's trainer turns
  right away and walks, runs or rides the bike as you do (by how fast the
  object moves, and the bike byte), standing still when you stop.

- 2026-10-09: **Black and White on a console, first fixes.** Viv's first run
  on real cartridges: the facing byte always read "up", so the facing now
  comes from the player's map object (IronMon Tracker's table at
  `0x022521EC`); the Continue menu and the intro showed as Black City or
  White Forest in spring (the save is loaded but the field isn't), so with
  no player map object and the zone at 0 it's the game card until you're
  in. Winter's light is a frosty border instead of a wash over everything,
  and its nights are lighter.

- 2026-10-09: **Black and White, round four: seasons, places, Discord.**
  The Unova view dresses for the season (`overlay/seasons.py`: petals, sun
  rays and fireflies, leaves in gusts, snow piling on the panels with
  icicles, a drift and a night aurora, a light wash for the time of day,
  a banner when the season turns). From the RetroAchievements notes: the
  Repel steps, the trainers beaten and items found in each place (header
  chips), the badges' shine (dull, clean or polished on the footer), and
  panels of their own in the Battle Subway (streak, record, the set's
  seven cars), the Battle Institute (rank and points) and, only while
  challenging them, the Elite Four. In battle a wild Pokémon you own shows a
  Poké Ball, a catch gets a "Gotcha!" and a wobbling ball, a low HP bar
  pulses red, and in doubles your right Pokémon sits lower and in front.
  The party icons are drawn at the window's resolution (`Overlay.present`).
  Move animations pick a flavour by name (punches, kicks, bites, beams,
  orbs, jets, Surf's wave, quakes with a screen shake, meteors, songs,
  draining, stat arrows, barriers, hearts, powders, weather, ...) finished
  in the type's own style. Discord gets a presence of its own
  (`rpc/bw_presence.py`): the foe on the turf the battle view uses and your
  trainer walking on the place's turf, GIFs made by
  `Assets/Unova-Battle/process_unova.py` for Unova's Pokémon.

- 2026-10-09: **Black and White's battles, round three.** The new
  background (the "Arena" concept): Diamond and Pearl's skies with Black
  and White's detail drawn in code (a 3D-stretched floor with streaks, a
  skyline per place, horizon haze, sun shafts, particles, a vignette), and
  new tufted turfs placed like Black and White's, in a day look and a night
  look (`overlay/unova_backdrop.py`). From the RetroAchievements notes:
  Gym Leaders (their room while their music plays), the Elite Four and the
  Champion are named and stand on the far turf before sending out their
  first Pokémon; the in-game clock (with each season's day and night hours)
  lights the battles; the field's weather falls in them. In doubles your
  Pokémon stand a little lower, and the main view's trainer sits clear of
  the footer's border. The demo has a rainy forest battle and Burgh.

- 2026-10-09: **Black and White, round two.** The RetroAchievements code
  notes for both versions came in (`docs/memory-map/`): every address the
  parser reads that they cover matches, White's 0x20 higher, so White
  needed no new code; its place names now say White Forest where Black's
  say Black City. The notes also moved the battle PP: each move is stored
  twice in a battle copy, and the in-battle one (whose PP the notes watch
  go down) is 6 bytes later than first thought. The overlay: the party
  panels' text keeps clear of their cut corners (names further right, HP
  further left), the badges are smaller (2/5 of the trainer card's), and
  Black and White's battles get the games' own HUD (thin white arrow bars
  with the names above them, a dark plate for your HP numbers, the
  two-tone gauge, and a dark message band with maroon edges, the moves on
  it too). New backgrounds and platforms are being drafted as concepts.

- 2026-10-09: **Pokémon Black and White get their own overlay.** (Also:
  the overlay font has `|`, and the waiting screen's DSi has its D-pad and
  buttons beside the touch screen instead of above it.)
  - **A parser** (`core/bw_parser.py`, `core/bw_data.py`) for Black and
    White US: party (Gen V's 220-byte Pokémon, the same encryption as
    Gen IV's), trainer, money, badges, play time, zone, position, facing,
    season, Pokédex, and battles from the battle copies (HP and PP live,
    the max PP included). The addresses come from public emulator tools
    (PKHeX's save layout, which sits 1:1 in RAM; the Gen V RNG scripts;
    NDS-Ironmon-Tracker; pokebot-nds; Action Replay codes) and the zone
    names from the RetroAchievements rich presence for game 3887; White's
    are Black's plus `0x20`. The RetroAchievements notes attached for this
    turned out to be Platinum's, so none of it is checked on a console yet;
    the parser checks what it reads and the game card takes over when it
    doesn't look like the game.
  - **The Unova view** (`overlay/unova.py`): the party in the games' own
    chevron panels, three to a row; an achievements panel (latest unlock,
    next to earn, progress and points) on the main screen, which Platinum's
    view doesn't have; the season, place and play time; Hilbert or Hilda
    walking, money, the real Unova badges and the Pokédex. Battles use the
    battle view on the games' own skies and platforms. All of the art is
    cut at runtime from the sprite sheets in `Assets/PokemonBlackUI`
    (`overlay/unova_art.py`), so no image files were added.
  - **The hub** reads Black and White like Platinum (battlers only during
    a battle, one request) and adds the game card's RetroAchievements keys
    to their state. Discord shows them like any other game for now.
  - **The demo** has a Pokémon Black stretch (the Unova view with an
    achievement unlocking, then a battle in Pinwheel Forest).
  - Still to do: the opponent trainer (name, class and sprite, which needs
    the trainer data or the RetroAchievements notes for game 3887), battle
    status, types and stat changes, the Discord presence, and a try on a
    console.

- 2026-10-09: **Achievements checked every frame.** On a 3DS, Tetris DS's
  T-Spin Single never unlocked and "Look Ma, One Hand" unlocked when it
  shouldn't have: the first needs the T-spin flag on the exact frame the
  line count goes up, the second a ResetIf that catches every rotation, and
  the console checked about every 19 frames, DSiRPC once a second. Now:
  - **Two lanes on the console.** Sets are version 4: DSiRPC puts the
    achievements that need every frame (`offline.timing()`: hit targets,
    ResetIf, PauseIf, delta and prior values) in a frame lane, as many as
    its ARM7 cost model allows (`split_lanes()`, `frame_costs()`, fitted on
    `tools/arm7_model`), and the rest in the pass lane. The console samples
    the frame lane's memory values at the start of every VBlank into a ring
    and checks the samples in order (`AchVm_Sample()`, `AchVm_RunSampled()`),
    so every frame is checked as it was.
  - **The ARM9 writes its cache back.** A value the game wrote can sit in
    the ARM9's data cache past the end of the frame (a one-frame flag may
    never reach main RAM), so with a frame lane the ARM9's VBlank hook (the
    per-frame capture's) cleans the whole data cache at the start of every
    VBlank and counts it; the ARM7 samples right after.
  - **Idle time.** The checking moved out of the VBlank into
    nds-bootstrap's swiHalt hook, where the game's ARM7 idles (up to 16
    scanlines a visit and 120 a frame, stopping for ARM9 ROM reads); the
    VBlank still does it for a game whose swiHalt couldn't be hooked.
  - **Skipping what can't have changed.** An achievement whose memory
    values didn't change this frame or the last, and whose last check left
    its state and hits (hashed: exact for hit targets and AddHits/SubHits,
    none-or-some for the rest) as they were, is skipped: same results as
    rcheevos, a fraction of the cost. A steady frame of a 200-achievement
    test set costs 102,000 cycles instead of 450,000; the pass lane does
    tens of passes a second instead of one or two. (A first version
    tracked hit changes as they happened; an achievement true from the
    start bumps and resets its hits every frame, so it never settled.)
  - **DSiRPC every frame too.** `core/frame_capture.py` checks every frame
    the achievements that need it and that the console doesn't check every
    frame, as many as fit in the per-frame capture's 8 watched values, from
    the DSi's record of every frame (drained four times a second, also
    between the requests of a long read). When the console's report says it
    runs a set DSiRPC built (`st=`, `ra/cache/console_sets.json`), DSiRPC
    leaves those achievements to it instead of checking them once a second.
  - **DSiRPC's unlocks on the console.** `'U'` tells the console's checker
    about DSiRPC's own unlocks: it stops checking them and the in-game menu
    shows them as earned and new.
  - **Room.** The capture's 2 KB ring moved from the ARM7 cardengine to
    the end of DSiRPC's 256 KB in main RAM (sets now get 250 KB), which
    paid for all of it: the ARM7 is at 61,460 of 62,464 bytes, the ARM9
    cardengine has 792 bytes left.
  - **The overlay's game card** shows the latest unlock (any time, "NEW"
    for 5 minutes) in the left two thirds of its achievements panel and one
    to earn in the right third.
  Tested on a PC: the checker against rcheevos frame by frame on a
  simulated puzzle game (with and without skipping, sampled now and
  checked later, stopping at random points; 54 runs of 4,000-8,000
  frames, half with random achievements), `probe_ach.c` with real version
  4 sets (idle time, VBlank, a starved idle side), and DSiRPC's side
  against a fake DSi at 60 frames a second. Builds with the CI's Docker
  image. Needs a hardware test: the report's `f=`, `fr=` (about 60), `fd=`
  (0), `fc=` (0) and `h=` (1).
- 2026-10-08: **The overlay's game card, and a docs pass.** Any game but
  Platinum used to get a lone panel in the overlay; now it gets a game card
  laid out like the party view (`overlay/gamecard.py`): the title and
  session time in the header, a "Now" panel with the RetroAchievements rich
  presence, an "Achievements" panel with a gold progress bar and the latest
  unlock (for 5 minutes) or one still to earn (a different one every 6 s,
  "MASTERED" at the end), and a footer with a DS game card in a colour
  picked by the game code, the code and RA game ID, and the achievements and
  points earned. `core/other_game.py`'s state gained `unlocked`, `recent`
  (`RaGame.session_unlocks`), `ra_note` and `signed_in` for it. The waiting
  view got the same frame: a DSi drawn in code with Wi-Fi arcs, the hub's
  status wrapped (it used to run off the panel), the steps on the console,
  and the last game played. The demo now plays a made-up "Demo Racer DS"
  with a set and an unlock. Platinum's party and battle views are unchanged,
  pixel for pixel. Pokémon Black and White are next in line for views of
  their own (the Pokémon sprites up to #649 are in `Assets/` already). The
  docs pass brought in the hardware results (the lid fix, the LED, the
  in-game menu on the DSi and 3DS, the one-app launch), the CMD53 numbers,
  the new clock and the overlay, and marked this file's old plan sections
  as superseded.
- 2026-10-08: **Unlock times from the console's clock.** The menu worked on
  the DSi, and on the 3DS everything but the LED (TWiLight has no LED
  setting there; the notification LED through TwlBg was judged too much for
  a small feature, and the menu's banner works there). Unlocks were dated
  by the launcher's `time=` plus the VBlanks counted since, a choice made so
  the game's ARM7 never had to read the real-time clock. But the VBlanks
  stop while the console sleeps and while the in-game menu is open, so
  after a nap every unlock looked that much older, and DSiRPC passes that
  age on to RetroAchievements (the `o` field of `awardachievement`). Now
  `probe_ach.c` reads the clock when an achievement unlocks, with
  nds-bootstrap's own `rtcGetTimeAndDate()` (its in-game menu already
  reads the clock from the VBlank interrupt): once a VBlank at most, with
  interrupts off, and only while the game's chip select is low, so it
  never cuts into the game's own clock reads. Readings that can't be right
  are ignored, and each good one becomes the new starting point for the
  VBlank count, which is still the fallback. Playtime needed nothing: the
  playtime DSiRPC shows is the game's own counter. Host-tested (the real
  read path against mapped registers, 200,000 random dates against
  `timegm()`, busy and bad readings, the earlier unlock-saving and menu
  tests); needs a hardware test. ARM7: 61,164 of 62,464 bytes (+216).
- 2026-10-08: **Achievements in nds-bootstrap's in-game menu.** The lid fix
  worked on hardware (DSiRPC logged `Console: its lid closed ...` and the
  DSi slept and woke fine). Sets are now version 3: after the program comes
  a list of every achievement of the game (title, description, points, and
  when it was earned as far as DSiRPC knows; `unlocked.json` now keeps
  RetroAchievements' times from `startsession`, and the time of each sent
  unlock). The console marks its own unlocks in that list (the ones waiting
  in `RPCUNLK.BIN`, then each new one, numbered) once the set's CRC has
  been checked, and keeps notes for the menu (the anchor) in the header's
  spare bytes. The menu's main screen shows the new unlocks since it last
  opened and "Achievements: 12 of 102 earned"; its new Achievements item
  lists them, earned ones first, newest first with date and time, then the
  locked ones, with the highlighted one's description. The menu only reads,
  and only an anchor the ARM7 marked open. Version 2 sets are still
  checked, without the list. Tested on a PC end to end (DSiRPC's set,
  `probe_ach.c`, the drawn screens with keys, under AddressSanitizer), plus
  the earlier unlock-saving and lid/LED tests; needs a hardware test. ARM7:
  60,948 of 62,464 bytes; the menu: 33,880 of 39,936.
- 2026-10-08: **Lid fix, second try, and the achievement LED.** The first
  lid fix (disconnect the chip and turn its interrupts off when the lid
  closes) didn't help: the DSi still switched off. It's not known yet
  whether that code ran before the game slept, so now it first sends
  DSiRPC a "DSiRPC lid" packet (logged as `Console: its lid closed ...`),
  then disconnects the chip as before, then cuts the chip's SDIO power
  (BPTWL[30h] bit 4, which DSWiFi sets when it starts the chip; the Wi-Fi LED
  goes off with it). Also new: on a DSi, the LED TWiLight's ROM read LED
  setting picks pulses while achievements unlocked this game haven't been
  seen, until nds-bootstrap's in-game menu is opened (the power LED pulses
  purple); that LED no longer flashes for ROM reads in our build. Tested on
  a PC (the state machine's cases, and the LED against a fake BPTWL chip:
  pulse timing, each LED's values, the SDIO bit never coming back, no I2C
  on a 3DS or with broken I2C); needs a hardware test. ARM7: 60,408 of
  62,464 bytes.
- 2026-10-08: **DSi lid fix: the console turns its Wi-Fi off when the lid
  closes.** On a DSi, closing the lid in a game started connected switched
  the console off, while the same thing was fine started offline (B in
  the launcher) or from TWiLight Menu++, and on a 3DS. The difference is
  the chip still being associated when the game sleeps (likely its power
  draw: DSWiFi sets it to maximum performance, no power saving). Now the
  first VBlank that sees the lid closed does what the launcher does when it
  goes offline: a `WMI_DISCONNECT_CMD`, then the chip's and the
  controller's interrupts off (`TwlWifi_Shutdown()`), and rpcprobe stays
  off the Wi-Fi for the rest of the game (status byte stage 5); the checker
  and its saves carry on. The in-game menu's own sleep calls it too. DSi
  only. Tested on a PC against a fake chip (the exact SDIO commands, and a
  chip that doesn't answer) and through the state machine's cases; needs a
  hardware test. ARM7: 60,180 of 62,464 bytes.
- 2026-10-08: **Offline play works end to end; console unlocks count live;
  a faster checker.** On hardware, Tetris DS's "Infinite Rotating" (230052)
  unlocked with the console offline, was saved to `RPCUNLK.BIN`, and went to
  RetroAchievements at the next sync with the time it happened. Since the
  console checks about twice a second and DSiRPC about once, DSiRPC now
  counts the console's unlocks as soon as its report arrives (sent,
  notified, no longer checked on the PC); the same unlock coming back at
  the next sync is already known. For testing: `--blank-ra` (act as if
  nothing were unlocked: whole sets for the console, every achievement
  checked, everything sent), `--clear-ra` (throw away the console's waiting
  unlocks at its first sync and send every set again), and `--dry-run` now
  also acts as if nothing were unlocked and leaves the console's unlocks on
  it; they combine. The checker got a speed pass, measured on a model of
  the ARM7 (now `tools/arm7_model`: its Thumb build in an emulator,
  counting instructions, branches and memory accesses; it agrees with the
  1.4 passes a second seen on hardware within about 15%). Main RAM wasn't the cost, instructions were: switch tables
  (`__gnu_thumb1_case_*` calls), operand values passed through memory,
  recounting where each condset phase starts. Now operand value and type
  come back in registers, sizes and comparisons are table lookups, AddSource
  and AddAddress chains have a direct path, and the commonest condition
  types skip the switch: Platinum's pass went from about 1.83 to 1.25
  million cycles, other sets 17-24% less, with slightly smaller code. It
  checks the time every 8 conditions instead of 32, so a turn rarely goes
  more than a scanline or two over (it reached 26 on a 16-line budget), and
  the budget is 20 lines. Same results as rcheevos: six real sets, and about
  77,000 random achievements, with and without stopping at random points.
  ARM7: 59,956 of 62,464 bytes.
- 2026-10-08: **Offline play, phase 3 (saving unlocks in game).** Phase 2
  ran on hardware: Platinum's 101 achievements at about 1.4 passes a second,
  25-27 scanlines at most per VBlank. A test unlock (96047, all eight badges
  at full shine) didn't trigger on the console, but DSiRPC's own rcheevos,
  watching the same session, didn't unlock it either, so the two agreed.
  Now each unlock is written into its own `RPCUNLK.BIN` slot. The SD card
  can't be touched from the VBlank interrupt after the first one (the white
  screen), so the writes happen in nds-bootstrap's swiHalt hook, outside
  interrupts, where it already serves the ARM9's ROM reads under
  `saveMutex`: `Probe_HaltTick()` takes that lock with `tryLockMutex()` and
  writes one 16-byte slot. A game whose swiHalt couldn't be hooked gets them
  written from the VBlank after two seconds, under the same lock and only
  while no ROM read is in flight. The unlock's time is the launcher's clock
  (`time=` in `RPCHAND.TXT`) plus the VBlanks since, so the game's ARM7
  never has to read the real-time clock (time asleep isn't counted).
  `RPCUNLK.BIN` is read on the first VBlank into the last 4 KB of the
  checker's memory, which sets now leave free: unlocks go after the last
  slot in use, and the game's achievements already waiting there aren't
  checked again. Since the console saves online unlocks too, DSiRPC leaves
  out the ones it already knows about when they come back. The report
  gained `s=` (saved), `x=` (couldn't be saved) and `w=` (waiting from
  before). Tested on a PC: the console side (probe_ach.c with the file
  calls in memory) against DSiRPC's reader, and the whole loop through the
  launcher's sync code and DSiRPC's `ConsoleSync`. ARM7: 60,012 of 62,464
  bytes. Needs a hardware test.
- 2026-10-08: **Offline play, phase 2 (the in-game checker).** Phase 1
  worked on hardware: the launcher found DSiRPC and took five sets. Now the
  console runs the game's achievements itself. To keep the console's part
  small and exact, DSiRPC has rcheevos parse the set (as it does for itself)
  and a small addition to the library (`third_party/rcheevos/dsirpc_offline.c`)
  writes out what rcheevos parsed: the memory values, including the
  AddSource/AddAddress/Remember chains rcheevos 12 keeps as "modified
  memrefs", and every condition in rcheevos' evaluation order. Sets became
  version 2 (that program instead of the MemAddr text). In nds-bootstrap,
  `rpcprobe/probe_ach_vm.c` is a port of rcheevos 12.5's evaluation without
  floating point (3.5 KB of ARM7 code), and `probe_ach.c` loads
  `RPCSET.BIN` on the first VBlank into 256 KB the bootloader now keeps the
  ROM cache out of, checks its CRC, and runs it about 1 ms per VBlank,
  stopping after any 32 conditions and carrying on next time. Tested on a
  PC side by side with rcheevos: five real sets and tens of thousands of
  random achievements, every achievement state and hit count equal after
  every frame. Along the way: rcheevos treats a value compared with its own
  delta as unchanged by the operator alone, even when the two sides read
  different bits (copied), and a Remember used by an earlier PauseIf reads
  last frame's value (copied). With Wi-Fi, a "DSiRPC ach" packet after each
  hello reports what the checker unlocked and how fast it runs, and DSiRPC
  logs it. Next: phase 3, saving its unlocks into `RPCUNLK.BIN`.
- 2026-10-07: **Offline play, phase 1 (the launcher and DSiRPC).** The goal:
  take the console anywhere, unlock achievements without DSiRPC around, and
  have them reach RetroAchievements the next time the launcher finds DSiRPC.
  The console does as little as possible: DSiRPC does all the parsing and
  everything RetroAchievements, the console only carries files. Phase 1:
  the launcher can skip Wi-Fi (**B** while connecting, or **START** when it
  can't connect) and still start games; when it's connected it syncs with
  DSiRPC over port 4245 (UDP broadcast to find it, then TCP), handing over
  `sd:/RPCUNLK.BIN` (fixed-size slots the in-game side will write into) and
  taking per-game sets (`sets/CODE.DRS`: the achievements left to unlock, as
  MemAddr strings) that it copies to `sd:/RPCSET.BIN` for the game it
  starts. DSiRPC sends the unlocks with the console's unlock times (`o`),
  logs them and shows one notification. `RPCHAND.TXT` gained `time=` and a
  `mode=offline` form. Both sides were tested against each other on a PC
  (`launcher/source/sync.c` builds for Linux too). Next: phase 2, an
  achievement checker in the in-game side that reads the set; phase 3,
  writing its unlocks into `RPCUNLK.BIN`.
- 2026-10-05 (evening): **A download for everyone.** Releases now come with
  `DSiRPC-<version>-windows.zip` (`packaging/build_release.py`, run by the
  GitHub Action on a Windows runner): DSiRPC with Python's embeddable package
  and its packages, both `.nds` files in an `SD card/DSiRPC` folder, and a
  plain `README.txt`, so nothing needs installing. `Setup.bat` and
  `DSiRPC.bat` use that bundled Python when it's there. Release builds can
  come with a Discord application (repository variables, written to
  `defaults.cfg`), so setup's Discord step is just Enter. The overlay
  downloads its sprites from GitHub Pages when a download doesn't have them
  (the full set is over 500 MB). The README was rewritten for people who just
  want to use DSiRPC; building and running from the source code moved to
  `docs/DEVELOPMENT.md`. Also: the achievement count was one too high,
  because RetroAchievements adds a "Warning: Unknown Emulator" entry to sets
  for clients it doesn't know; DSiRPC now leaves it out like rcheevos' own
  client does. The bundled Python was tested under Wine (packages, rcheevos,
  the tray backend, a full setup run).
- 2026-10-05 (morning): **One-app launch, and RA finds Platinum.** On
  hardware, RetroAchievements worked for Mario Kart DS (its set was already
  in `ra/`) but not for Platinum: "no game called this game there". The
  header title is read from `0x023FFE00`, which holds the header under
  emulators but not under nds-bootstrap on a DSi or 3DS, and with no game
  files folder set there was nothing else to go by. DSiRPC now looks the
  game code up in GameTDB's title list (`core/game_titles.py`, `CPUE` is
  "Pokemon: Platinum Version") when the header can't be read, for
  RetroAchievements and RALibretro's cache alike, and setup's set picker
  does the same. A deadlock waiting in `RALink.update()` (signing in again
  while running) was fixed too. The launcher got three changes: it retries
  the connection up to 3 times, and counts a try as failed when no IPv4
  address arrives (DSWiFi reports "Associated" once an IPv6 address is
  ready, which is how the first try ended with `0.0.0.0`); START opens a
  file browser to pick the game; and the launcher then points
  `nds-bootstrap.ini` at it (its existing save, the last game's per-game
  values reset, its cheat files removed) and starts our nds-bootstrap
  directly with hbmenu's bootstub and nds-bootloader, now in
  `launcher/loader/` and built by the same BlocksDS command. The ini and
  save-path logic was tested on a PC; the chainload still needs hardware.
- 2026-10-05 (late night): **RetroAchievements, for real.** The tray app
  worked on hardware. Games without their own presence now show a picture
  of the console as Discord's small image (`Assets/Consoles`, picked in the
  tray's new Console icon menu), with the RetroAchievements line moved to
  the box art's hover text. Then the RA side: every game, Platinum too, gets
  a `RaGame` (`core/ra_game.py`) that checks the set's achievements with
  rcheevos about once a second, reading only the values the set needs
  (`SparseRam`, one request for Mario Kart DS's 100-odd values). Signing in
  (setup; only the login token is kept) lets DSiRPC download sets by itself
  (`core/ra_link.py`): by the RA hash of a matching game file on the PC
  (`core/ra_hash.py`, a port of rcheevos' DS hash, identical on every test
  file), else by title against RetroAchievements' DS/DSi game list. It also
  starts sessions and pings every 2 minutes with the rich presence, which
  shows on the RA profile, and, only when chosen in setup, sends unlocks as
  softcore, with a pending file and retries. The requests (`core/ra_api.py`)
  are encoded byte for byte like rcheevos' and carry an honest User-Agent
  (`DSiRPC/0.3.0 ... rcheevos/12.5`). Because the game is read once a second
  rather than every frame, achievements about split-second moments can
  unlock late, not at all or by mistake, which setup says before offering to
  send unlocks. Setup.bat and the setup wizard were reworded to be less
  cryptic. Tested against a stand-in RA server (signature checks, an outage
  mid-unlock, a ROM hash, title matching) and the fake DSi; not yet against
  retroachievements.org or on hardware.
- 2026-10-05 (night): **One program, a tray icon and a setup.** The
  generic presence worked on hardware (Mario Kart DS, RA game 12711, with
  its rich presence and the game's name in Discord). Then the PC side was
  cleaned up for everyday use. `dsirpc.py` is now the one program, built on
  the state hub for every game (`app/engine.py`): the hub follows the DSi
  from game to game (`core/other_game.py` for anything but Platinum), the
  Discord connector handles every game, and the overlay window opens next to
  it (`--overlay`) instead of being a separate program. `dsirpc.py tray`
  (`DSiRPC.bat`) puts it in the tray with Discord and overlay switches, Start
  with Windows, the log and setup; `dsirpc.py setup` (`Setup.bat`) installs
  the packages and asks for the Discord application IDs and RALibretro's
  folder, from whose `RACache` it copies the set for the game the DSi runs,
  matched by the title in the game's header at `0x023FFE00`
  (`core/ra_cache.py`; DSiRPC can also do this on its own when exactly one
  set clearly matches). Settings moved to `dsirpc.cfg` (the old
  `PokemonPlatinumRPC.cfg` is still read until then), the log to
  `logs/dsirpc.log`, and the testing tools (`dsi_status.py`, `ra_tool.py`,
  `frame_check.py`, `hello_listener.py`, `dsirpc_overlay.py`) to `tools/`.
  Tested with a fake DSi switching between Platinum, Mario Kart DS and an
  unknown game, a stand-in tray backend and scripted setup answers; not yet
  on Windows. Next: softcore achievements and rich presence on the RA site.
- 2026-10-05 (evening): **Any game in Discord; RetroAchievements rich presence
  from local set files.** v2 of the capture passed on hardware: no late
  reads in menus, overworld, battle, boot or across a soft reset (the ARM7
  only filled in on each run's first frame and during the reset itself, and
  `a9` stayed at 2, so the reset freed the hook). Then, with Discord as the
  goal and RetroAchievements as a source of game data: every game other than
  Platinum now gets a presence (`rpc/generic_presence.py`) with its title and
  GameTDB box art, plus, when `ra/` has its RA set file, the set's icon and
  its rich presence text, evaluated against the live memory with rcheevos
  (v12.5.0, prebuilt in `third_party/rcheevos/`, called through ctypes in
  `core/rcheevos.py`). `ra_tool.py` adds and checks set files (RALibretro's
  `RACache\Data\<id>.json`). Discord applications can be set per game
  (`[discord_apps]`), and the game's name is sent too (pypresence 4.6+).
  Nothing is sent to RetroAchievements. Research on RA's rules: only
  hardcore-compliant emulators may earn hardcore unlocks, and using anything
  else in hardcore gets an account Untracked; unknown clients are held to
  softcore by the server, and the published rules don't forbid softcore with
  them, but RA calls original hardware an unsupported platform. MiSTer is the
  precedent for hardware: a community integration RA's team is working with
  on hardcore verification. Tested against the RAM dump and a fake DSi
  (switching games both ways, live updates); not yet with Discord or on
  hardware.
- 2026-10-05 (later): **v2: the ARM9 snapshots at the very start of VBlank.**
  The hardware runs below left a few one-frame blips, all on the VBlank
  counter Platinum bumps right after its VBlank wait (`src/main.c` in
  pret/pokeplatinum): the ARM9's read, in its IPC interrupt just after VBlank
  started, sometimes landed after that bump. Now a hook in front of the
  game's VBlank interrupt handler (entry 0 of its interrupt table, like
  nds-bootstrap's IPC sync hook) takes the snapshot before the game's VBlank
  code runs, into four numbered slots; rpcprobe records them in order, one
  per VBlank, and reads by itself when there's none. The doorbell now
  only asks the ARM9 to put the hook in (when a capture starts, or when
  snapshots stop because the game replaced its handler: a fresh hook each
  time, up to four, each calling the handler it replaced; a soft reset frees
  them again, through one call in nds-bootstrap's `reset()`). `a9=` is 1 +
  hooks put in. `frame_check.py --save NAME` writes `logs/NAME.csv` and
  `logs/NAME.txt`; `logs/` is git-ignored, and the earlier CSVs are in
  `logs/v1/`. Tested on the host (both halves, a fake interrupt table,
  jitter, stalls, missed ticks, handler swaps, list changes; 200,000-frame
  fuzz runs: one record per tick, never a value twice or out of order) and
  against a fake DSi, and reviewed (stack and register handling of the ARM
  hooks checked against the built ELF); not yet on hardware. Sizes: ARM9
  cardengine 952 bytes over stock (888 free), ARM7 +192 bytes.
- 2026-10-05: **The ARM9 hand-over works on hardware.** Same screens as
  before, on Platinum. Menu: 0 late reads in 1,195 frames (the same screen
  with `--arm7-only`: 574 late, 48%, two by 3 frames). Overworld: 6 in 1,194;
  battle: 9 in 2,390; boot: 154 in 2,390 (was 27%, up to 17 frames late),
  every one by exactly one frame. The ARM9 answered every frame (only each
  run's first record was the ARM7's). The overworld blips all look like one
  read seeing the counter one count early (+1, +2, 0), which a stale cache
  can't do, and sit where the ARM9's 192/193 scanline rhythm skips: a race
  with the game's own update at the start of VBlank, not the cache.
- 2026-10-04 (night): **The ARM9 reads the captured values now.** New
  `cardenginei/arm9/source/dsirpc_watch.c`: on any IPC sync interrupt, if
  rpcprobe asked, the ARM9 copies the watched values (through its cache, so
  never late) into a 128-byte block in its cardengine and writes them back to
  RAM; rpcprobe finds the block by its magic, asks once per VBlank (IPC sync
  value 3, and only when its last value was 0 or 3, so nds-bootstrap's own
  commands are never replaced) and uses the answer the next VBlank, reading
  main RAM itself and marking the record when there's none. Hellos say `a9=1`
  when the ARM9 half was found. `frame_check.py` reports ARM9 and ARM7 records
  separately and `--arm7-only` gives the old behaviour for comparison. Tested
  on the host (both halves together, every fallback) and against a fake DSi;
  not yet on hardware. Sizes: ARM9 cardengine +452 bytes (1,388 free), ARM7
  +400 bytes. The other ARM9 cardengine variants only differ in the order of
  the linker's interworking veneers.
- 2026-10-04 (evening): **The ARM9 cache is real; the race isn't.** Four
  `frame_check.py --save` runs on Platinum. Overworld (standing and talking):
  clean, 30 counts a second, not one late read. Menus and battles: mostly a
  steady +2, 0, +2, 0, meaning the counter really goes up every frame there but
  the ARM7 only sees it every other frame (about 30% of frames read a frame
  late; 3 battle reads late by 3). Boot: the same plus catch-ups of 4 to 18
  after stalls, late by several frames. Every late read was taken at scanline
  192, the same as the read that caught up, so it isn't a timing race at the
  start of VBlank: the game's writes sit in the ARM9's data cache until the
  busy half of its 30 fps loop pushes them out to main RAM. Long stalls
  followed by +1 are the game itself pausing and are fine. Plan: have the
  ARM9 copy the watched values at VBlank (it reads through its own cache) and
  hand them to the ARM7.
- 2026-10-04 (later): **First hardware runs of `frame_check.py`** (Platinum,
  per-frame capture build). In the overworld the VBlank counter went up every
  other frame (Platinum's overworld runs at 30 fps) with not one late read in
  1,195 frames. During boot (intro and title, 60 fps) about a third of the
  steps were late: mostly by one frame, with the sample scanline varying
  192-199 in that run, plus a few late by 3, 5 or 7 frames, which only the
  ARM9 cache can explain. The first version of the tool counted the 30 fps
  pattern as lag and still said "on time"; it now judges by the rule that the
  counter can't go up by more than one per frame, and `--save` keeps the raw
  records. Next: runs on other screens (battle, menus, idle) to see whether
  late reads happen in play.
- 2026-10-04: **Step 1 of RetroAchievements support: per-frame capture.**
  rpcprobe can read a short watch list (up to 8 values) at the start of every
  VBlank into a 2 KB ring that the PC drains (`'W'` and `'F'` requests, same
  transport and reply header as memory reads), and the hellos now say which
  game is running (`gc=`, `v=`, `hc=` from the game's header).
  `frame_check.py` measures whether the ARM7 sees the game's memory frame by
  frame, using Platinum's own VBlank counter (`gSystem.vblankCounter` at
  `0x021BF6A8`, found in a RAM dump with the decomp's `System` layout). The
  Platinum parser, presence, overlay and `dsi_status.py` now only run on
  Platinum (`core/games.py`); on another game they say which one instead of
  reading garbage. ARM7 cardengine: 52,856 of 62,464 bytes. Tested on the PC
  side against a fake DSi and the capture logic on the host; not yet on
  hardware.
- 2026-09-27 (late): **Stat changes, conditions and type hints in the overlay.**
  The parser now decodes each battler's types, stat stages, and a few
  volatile conditions (confusion, infatuation, Substitute, Nightmare, Curse,
  Foresight, Leech Seed) from the BattleMon, using the decomp's layout (not
  yet checked on hardware), and `dsi_status.py` prints them. The overlay
  shows stat changes and those conditions as chips under the HP boxes,
  loops a marker on each Pokémon for its status or condition, tints a
  frozen one blue, and tags each of your damaging moves with its type
  multiplier against the foe (type chart from the decomp). The quick battle
  read grew to 108 bytes a battler (two requests in a single battle). The
  demo shows a few of these. The link check now reports `vb=` without the
  CMD52 heartbeat hellos as well.
- 2026-09-27 (night): **CMD53 sending works on hardware; double battles
  fixed.** Link check with the CMD53 send build: `txm=53 t53=0 rep=0`, 227
  of 228 answered (the one lost never reached the DSi), median reply 15 ms.
  Overlay and presence fixes: foes now face left (the overworld GIFs face
  right and are mirrored for the foe), the foe's first Pokémon in a double
  battle is on the right as in the game, and your second Pokémon is shown
  too (on the right, with two smaller HP boxes; the presence says "X and Y
  are fighting ..." and lists both on hover). Moves in doubles land on
  whichever Pokémon on the other side lost HP, and a spread move lands on
  both.
- 2026-09-27 (evening): **CMD53 receiving works on hardware; CMD53 sending
  added.** Link check with the CMD53 receive build: `rxm=53 e53=0`, 231 of
  231 requests answered, median reply 16 ms (90% under 22 ms, worst 39 ms),
  about 32 frames a second of other traffic drained. Sending now uses CMD53
  block writes as well (replies, ARP replies, and 9 hellos in 10), which
  should take the reply tick from about 76 scanlines to a few. Every 10th
  hello still goes out with CMD52 as a heartbeat, and if the PC has to
  re-send the same request twice, sending falls back to CMD52 for the
  session (the chip gives no delivery report, so that's the only sign of a
  CMD53 send that silently went nowhere). New hello fields `txm=`, `t53=`,
  `rep=`, also shown by `dsirpc_client.py --stats`. Checked against the
  simulated controller and chip (normal, never-asks-for-data and
  swallowed-frame cases), built with devkitARM (cardenginei ARM7 49,196 of
  62,464 bytes). Needs a hardware test.
- 2026-09-27 (later): **Faster DSi reads: CMD53 receiving.** The in-game
  side now reads each received frame with one CMD53 block transfer (the
  CPU emptying the controller's 32-bit FIFO, no NDMA) instead of one CMD52
  per byte, and drains up to 8 frames or 2 KB a VBlank, stopping after
  anything that sends a reply. That should take roughly a fiftieth of the
  SDIO time per frame, so the chip no longer overflows on a busy network.
  If CMD53 fails three times (an error, a timeout, or data that doesn't
  match the frame's lookahead), it switches back to CMD52 for the session;
  the hellos report `rxm=53/52` and `e53=`, and `dsirpc_client.py --stats`
  prints them. Switch: `RPCPROBE_RX_CMD53` in `rpcprobe_build.h`. Checked
  against a simulated controller and chip (normal, never-delivers and
  scrambled-data cases) and built with devkitARM (cardenginei ARM7 48,436
  of 62,464 bytes). Needs a hardware test.
- 2026-09-27: **Wild battles and move order.** Wild encounters could be
  called trainer battles: in battle the trainer class value is never empty
  on hardware, and at the very start the music can still be the encounter
  jingle. The parser now sets `battle.wild` when a foe has the player's own
  trainer ID (how the game makes wild Pokémon, per the decomp), and the
  overlay, the presence and `dsi_status.py` use it. The overlay's intro
  line also keeps following the data while it's shown. Moves could play
  out of order, a foe attacking after its own "fainted!": with several
  things in one read, the hit on the foe was matched first and its faint
  queued before the foe's own move. Moves now play in the order they
  happened (by read, then a fainted Pokémon first, then priority and
  speed), faints follow the hit that caused them, and a replacement is
  only shown once its "sent out" message plays. Checked with scripted
  reads that reproduce the bug on the old code.
- 2026-09-26 (link check): **Why reads got slow, and quick battle reads.** Full reads in
  the Maylene fight took 1 to 15 s, against about 0.7 s before the stutter
  fix. The likely cause is that fix itself: draining at most one frame and
  128 bytes per VBlank tops out around 7.7 KB/s, below what the home
  network's broadcast traffic can reach, so the DSi's wifi chip drops frames,
  memory requests included, and each lost request costs the PC a one-second
  timeout (a full read is about 20 requests). Nothing about battles
  specifically. New: `core/dsirpc_client.py --stats` (a link check that
  compares what the PC sent with the DSi's `req`/`rx` counters), and the
  hub's `DsiSource` reads only the battlers during a battle, one request
  every 0.3 s, falling back to a full read when the battle changes shape.
  The client now also records hellos that arrive while it waits for a reply
  (they used to be dropped unseen). The `vb=` docs now say what's normal
  (about 76, a reply or hello tick). Next: CMD53 block reads on the DSi
  side, once the link check confirms the drops.
- 2026-09-26 (night): **Moves in step with the damage.** The overlay showed
  a move as soon as its PP dropped, but the game only takes the HP after
  the animation, so the damage often came a read or more later. Damaging
  moves are now held until the target's HP drops and play together with
  the hit (misses play after 5 s of reads, status moves right away).
- 2026-09-26 (evening): **Last-move record checked, steadier trainer names.**
  A Maylene fight with `dsi_status.py --watch 2` showed `B+0x527C` working
  for your side (0 until the first move, then Fire Blast right after its PP
  dropped). The foes never moved, so their entry is still unchecked. The
  trainer name now stays put for the whole battle (`TrainerMemory`, the
  name read most often), the class falls back to its low byte if the u16
  isn't a known class, and `dsi_status.py` prints the raw class in hex.
  Also seen: reads in battle sometimes took 10 to 15 s for 3.5 KB, with
  "no reply" timeouts, which is slower than usual and needs a look.
- 2026-09-26 (later): **Moves in the overlay.** The overlay now shows which
  move each side used ("The foe's MACHOKE used KARATE CHOP!") with a
  pixel animation in the move type's style (`overlay/effects.py`), a lunge
  for physical moves, and the last move you used highlighted in the move
  panel. Moves are worked out from PP drops between reads, which the parser
  already had. The parser also reads the game's last-move record
  (`B+0x527C`, from the decomp's `BattleContext` layout, not yet checked on
  hardware) as `last_move`, and `dsi_status.py` prints it with each move's
  PP; the overlay uses it only as a backup once it has agreed with the PP.
  Wild vs trainer in the battle messages now follows the music, and the
  demo battles play out move by move.
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
