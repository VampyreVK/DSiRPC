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
