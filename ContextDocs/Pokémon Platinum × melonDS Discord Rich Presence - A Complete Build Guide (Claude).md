# Pokémon Platinum × melonDS Discord Rich Presence: A Complete Build Guide

## TL;DR

- **Fork melonDS directly** and add a `DiscordRPC` module under `src/frontend/qt_sdl/`. Use the still-functional `discord/discord-rpc` C++ library (vendored as a submodule the way mGBA does), pinned to a specific commit so it doesn't matter that it's officially deprecated; switch to the Discord Social SDK only if you want join-game and account-linking features later.
- **Read live RAM, not the .sav file.** All Gen 4 in-RAM party data, badge/Pokédex stats, and map IDs hang off a single SaveData pointer in EWRAM (Platinum US: poll the pointer at `0x02101D40`/`0x02111D10` family — the same anchor the entire AR cheat ecosystem uses). Use melonDS's existing `NDS::ARM9Read8/16/32` or read `MainRAM` directly from a 5-second timer in `EmuInstance` on the main Qt thread (the EmuThread fires the signal, the Qt thread does the syscalls — the Discord IPC is not threadsafe with the JIT).
- **Phase the work**: MVP = location name + badges + party HP fraction + playtime timestamp, all from RAM, on a generic "Playing Pokémon Platinum" application. Then layer on assets (locations first, ~120 keys), then battle detection + "little battle" mode (front/back sprites), then movement-direction sprites for Dawn last. Budget your 300-asset Discord allowance carefully — see the asset table below.

---

## Key Findings

### 1. melonDS architecture is friendly to a fork; the codebase has clear seams

- **Repo layout**: `src/` contains the platform-agnostic emulator core (NDS.cpp/h, DSi.cpp/h, ARMJIT.cpp, GPU.cpp, SPI.cpp, NDSCart.cpp, etc.). `src/frontend/qt_sdl/` is the Qt-based desktop frontend, where you'll do _all_ of your work — `main.cpp`, `EmuInstance.cpp`, `EmuThread.cpp`, `MainWindow.cpp`, `Config.cpp`, etc. The CMake structure is `CMakeLists.txt` (root) → `src/CMakeLists.txt` (core) → `src/frontend/qt_sdl/CMakeLists.txt` (Qt app). Add your code only to the Qt frontend CMakeLists; never touch the core.
- **Memory access**: melonDS exposes `u8 NDS::ARM9Read8(u32 addr)`, `u16 NDS::ARM9Read16(u32 addr)`, `u32 NDS::ARM9Read32(u32 addr)`, plus 7-suffixed equivalents. There's also a `MainRAM` pointer with a `MainRAMMask`; for `0x02000000`-region addresses (where Pokémon games live) you can do `*(u32*)&MainRAM[addr & MainRAMMask]` directly, which is slightly faster but bypasses the JIT's memory routing. Use `ARM9Read*` in the fork — it's the safe, supported abstraction and survives upstream refactors.
- **Frame loop**: The core runs on `EmuThread` (a `QThread` subclass). Each emulated frame, the thread loops `NDS::RunFrame()`. The Qt UI lives on the main thread. The cleanest hook is _not_ to poll inside `EmuThread` — instead, have a `QTimer` (5 seconds, matching Discord's rate limit) on the main thread that calls `emuInstance->getNDS()->ARM9Read32(...)` while the EmuThread is between frames. melonDS already has thread-safety mechanisms (the EmuThread takes a lock during `RunFrame()`); piggyback on those by emitting a Qt signal from EmuThread when frames are paused, or simply read while the EmuThread runs (RAM reads are inherently atomic for u8/u16/u32 reads from MainRAM since it's just a backing array). For simplicity in Phase 1, **don't use a QTimer; use a frame counter in EmuThread that emits a `void rpcStateUpdate(...)` signal every 300 frames**, connected to a slot on the main thread.
- **Existing scripting hooks**: PR #1671 added experimental Lua scripting (`src/frontend/qt_sdl/LuaMain.cpp/.h`), but it's not merged as of the current master and is rocky. **Don't depend on it**. There's no AR cheat engine exposing memory in a clean callback API either, but cheat code support does exist (`src/AREngine.cpp`) and that's a useful read-only reference for how memory is poked safely. melonDS has a GDB stub but it's overkill for read-only polling.
- **Best place to add your module**: Create `src/frontend/qt_sdl/DiscordRPC/` with:
    - `DiscordRPCManager.h/.cpp` — singleton-ish, owns the discord-rpc connection and state
    - `Gen4Reader.h/.cpp` — game-agnostic memory walker (takes an `NDS&` ref, returns a `Gen4State` struct)
    - `Gen4Maps.h` — all the static lookup tables (location-id → name, trainer-id → name+title, species-id → name)
    - `DiscordRPCDialog.h/.cpp/.ui` — Qt settings dialog (a checkbox + an "Application ID" text field + an "Enable battle mode" checkbox + a test button)
- **Build system**: melonDS uses CMake with vcpkg integration on Windows. Vendor `discord-rpc` as a git submodule under `src/frontend/qt_sdl/3rdparty/discord-rpc`, then in your CMakeLists add `add_subdirectory(3rdparty/discord-rpc EXCLUDE_FROM_ALL)` and link `target_link_libraries(melonDS PRIVATE discord-rpc)`. This is exactly the pattern mGBA uses (see `src/third-party/discord-rpc` in the mgba-emu/mgba repo). Gate the whole thing behind a `-DENABLE_DISCORD_RPC=ON` CMake option so other contributors / your CI can disable it.

### 2. Pokémon Platinum memory map: there's a single pointer to rule them all

- **The save-block-in-RAM anchor** for Platinum US is at EWRAM address `0x02101D40` (this is the well-known constant used by every Action Replay code: `B2101D40 00000000` is the AR opcode "load pointer at 0x02101D40 as base"). At that address is a 32-bit pointer into another EWRAM region containing a working copy of the save data. The Wild Pokémon Modifier code combo `B2101D40 00000000 / D9000000 00111D10` reads from `[ptr+0x00111D10]`, confirming the offset for the encounter slot. You will use the same pointer chain.
- **Save data layout in RAM** mirrors the small block of the .sav (Bulbapedia "Save data structure (Generation IV)"). For Platinum the small block runs `0x00000–0x0CF2B`. Within it, relative to the small-block base:
    - **Party Pokémon**: starts at offset `0x00A0`, 6 × 236-byte party slots (battle Pokémon use the 236-byte form; 100 extra bytes vs the 136-byte boxed form)
    - **Party count**: 4-byte int just before party data (`0x009C`)
    - **Trainer card** (name, ID, secret ID, money, badges bitfield, playtime hours/minutes/seconds): in the early part of the small block. The "All 8 Badges" cheat writes `0xFF` to base+`0x96`, which means _the badge byte lives at relative offset `0x0096`_ inside the small block in RAM. Confirm with PKHeX's Gen 4 SAV reader source — PKHeX's `SAV4Platinum.cs` is the single best ground truth and you should literally diff your runtime reads against PKHeX reading the .sav.
    - **Pokédex (seen/caught)**: bitfields, also early in the small block — Bulbapedia documents the layout
    - **Playtime**: 4-byte struct (hours u16, minutes u8, seconds u8, frames u8) — pull this and use it as your `timestamps.start = currentEpoch - secondsPlayed` so Discord shows total elapsed playtime ticking up.
- **Player overworld state** (current map ID, X/Y/Z, facing direction, movement state — walking/running/biking) is _not_ in the save block; it's tracked elsewhere in EWRAM in the field-system overlay. The pret decompilation source file `src/field_system.c` and the field-overlays under `src/overlay005/` (Diamond/Pearl/Pt share a lot) define `FieldSystem` with members for `playerData`, `location`, etc. **You will have to find the live address yourself with Cheat Engine** — start by walking on the map, scan for changing X coordinate u32, narrow down by walking opposite direction, then map back from instruction breakpoints in DeSmuME (which has better debug tools than melonDS) and translate the address to Platinum US. There's a known Lua script (`PokeStats Gen 4 and 5.lua` in the `dude22072/PokeStats` repo) that has these for Platinum already — it has `local game = 3 -- Platinum` and uses `memory.readwordunsigned` against specific offsets relative to a pointer at `0x02101D40`. Read that script line-by-line; it's the closest prior art to what you need.
- **Battle detection**: There's a battle flag/state byte that flips when a battle starts. Two approaches:
    1. Watch for the in-battle Pokémon struct at the address `Poke J` documented on Project Pokémon (around `0x002C0BC2`-ish region for the enemy Pokémon's RAM struct, with the recognizable `06 06 06 06 06 06 06 06` stat-stage signature) — when that struct is non-zero / changing, you're in battle.
    2. Better: find the `BattleSystem` struct's allocation (visible in pret source). Its mere existence is the battle flag. The struct includes `BattleType` (wild / trainer / gym / Frontier) and a pointer to enemy party.
- **Map ID → location name**: Each location has a numeric ID (Bulbapedia's "List of locations by index number (Generation IV)" has the full table — 658 entries). Pret's `pokeplatinum/include/constants/map.h` (or similar) has the C enum. Convert that to a JSON file in `src/frontend/qt_sdl/DiscordRPC/data/locations.json` or, even simpler, a generated `Gen4Maps_Locations.cpp` with a `static const char* kLocationNames[] = { ... }`.
- **Trainer ID → name/class**: Pret's `trdata.narc` extraction in `pokeplatinum/res/pokemon/trainers/` and `src/trainer_data.c` is the source of truth. There are ~700 trainers in Platinum. You won't show all of them by name — only the _interesting_ ones (gym leaders 0x10D-0x114-ish, Elite Four, Cynthia, Cyrus, Mars, Jupiter, Saturn, your rival Barry, the Frontier Brains). Hand-curate a `kKnownTrainers` map keyed by trainer ID; for unknown trainers, fall back to "Battling a Trainer".
- **Species ID → name**: Use the National Dex order (1=Bulbasaur … 493=Arceus). Trivial 494-entry array. Gen 4 species IDs in the PK4 struct are National Dex IDs already (unlike Gen 1/2's regional indexing).
- **Save vs RAM gotcha**: The PK4 structure is **encrypted** in the save file (XORed by the checksum-seeded PRNG, with shuffled blocks). In RAM, when read through the live pointer chain, **party Pokémon data is decrypted** in the working buffer the game uses for combat/HUD display. This is a huge win: you don't have to implement Gen 4 PRNG decryption to read species/HP/level. Verify by reading party slot 0 species at `[base_ptr] + 0xA0 + 0x08` (the species offset within Block A) and confirming it matches what's in your party. The 136-byte boxed-form layout in RAM is identical to the Bulbapedia "Pokémon data structure (Generation IV)" doc when stored in the working "decrypted" buffer.

### 3. Discord library: use `discord/discord-rpc` (vendored), not Social SDK — for now

- Discord officially deprecated `discord-rpc` in 2018 in favor of GameSDK, then deprecated GameSDK in 2024 in favor of the **Discord Social SDK** (current as of GDC 2026). However:
    - `discord-rpc` **still works in 2026** because the underlying IPC protocol is the same; it's just frozen. Every emulator (mGBA, Citra, RPCS3) still uses it.
    - Social SDK requires registering as a "Discord Official" partner for full features and has a heavier integration footprint (account linking, lobbies, voice — none of which you need).
    - **Recommendation**: vendor `discord-rpc` master pinned to a known-good commit. If Discord ever turns off the protocol, switch to Social SDK at that point.
- **Alternative C++ libs** (open-source community rewrites worth knowing about):
    - `EclipseMenu/discord-presence` — modern C++23, builder pattern, supports new features like activity types and buttons that the original `discord-rpc` doesn't expose. Worth considering if you want clean code and don't mind it being a smaller community library.
    - Roll-your-own — Discord's "Hard Mode" docs describe the IPC protocol (named pipe `\\?\pipe\discord-ipc-0` on Windows, JSON messages). ~200 lines of code. Avoid; not worth the maintenance.
- **Application ID**: Register at https://discord.com/developers/applications. Pick a name like "Pokémon Platinum (melonDS)". The app ID is a 64-bit number — store it in a `Config` setting, default-bake it to your own app ID, but expose it in the dialog so other users can use their own (they want their own asset uploads).
- **Rate limit**: 5 seconds between updates (the user already knew this; Discord enforces it server-side and silently drops faster updates). Match it: `QTimer` at 5000ms interval, or every 300 emulated frames at 60 fps.
- **Payload fields you'll use** (mapping to your spec):
    - `details` (str, 128 char) → "Exploring Mt. Coronet" / "Battling Gym Leader Fantina"
    - `state` (str, 128 char) → "Badges: 4 | Pokédex: 87"
    - `partySize` / `partyMax` → live party HP fraction (alive / total) — yes Discord renders this as "(3 of 5)"
    - `startTimestamp` (UNIX time) → `time(NULL) - playtimeSeconds` so Discord ticks up "Playtime: 23:14:08"
    - `largeImageKey` / `largeImageText` → location asset key + tooltip
    - `smallImageKey` / `smallImageText` → Dawn-direction asset key + tooltip ("Dawn (running west)")
    - `buttons[]` → optional, e.g., a "Bulbapedia" link to current location
- **Activity type** is supported in Social SDK / new RPC fields (Playing/Watching/Listening/Competing) but **NOT exposed in the legacy `discord-rpc` C struct**. To set "Competing" during gym battles, you either: (a) bypass `discord-rpc` and write the IPC packet yourself with the `type: 5` field, (b) use `EclipseMenu/discord-presence` which exposes it, or (c) accept "Playing" everywhere for MVP. **Recommendation: ship MVP with "Playing" only; add activity type in Phase 4 by switching libs.**
- **Graceful Discord-not-running**: `Discord_Initialize()` is non-blocking and just queues. `Discord_UpdatePresence()` is a no-op if no IPC connection. Call `Discord_RunCallbacks()` periodically (every poll cycle is fine) to drain replies. The lib reconnects automatically when Discord later starts. No special handling needed.

### 4. Asset strategy: prioritize ruthlessly within the 300-key limit

Discord allows **up to 300 uploaded asset keys per application**, each 1024×1024 PNG ideal. Asset keys are **lowercase, 2-256 chars, immutable once set** (you can delete and re-upload but caches linger). Use external URLs (CDN) only as overflow — they support GIF/WebP and don't count against the 300, but they're slower and Discord requires a public HTTPS URL.

**Proposed budget (~280 of 300):**

|Category|Count|Naming convention|Source|
|---|---|---|---|
|Sinnoh location backgrounds|~80|`loc_<snake_case>` (`loc_jubilife_city`, `loc_mt_coronet`, `loc_route_209`, `loc_distortion_world`)|Spriters Resource → Pokémon Platinum → Backgrounds + Area Images; you may need to composite from screenshots. ~80 covers all named towns + numbered routes + major dungeons (Mt. Coronet floors collapse to one key)|
|Player back sprites (battle)|4|`dawn_back_walk`, `dawn_back_run` — or just one `dawn_back`|Spriters Resource → Dawn|
|Player overworld direction × movement|12|`dawn_<dir>_<mode>` where dir∈{up,down,left,right} mode∈{walk,run,bike}|Spriters Resource → Dawn overworld sheet|
|Pokémon front sprites (Sinnoh dex 210)|0 (defer)|—|Use external CDN → PokéAPI sprites: `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/<id>.png`|
|Pokémon back sprites (lead Pokémon, top ~50 used)|50|`pkmn_b_<natdex>`|Spriters Resource → Pokémon (4th Gen) → Back|
|Gym leaders + Elite Four + Cynthia + Cyrus + Barry portraits|18|`trainer_<name>` (`trainer_fantina`, `trainer_cynthia`, `trainer_barry`)|Spriters Resource → Elite Four and Gym Leaders + Trainer Vs. Faces|
|Generic fallback icons|10|`loc_unknown`, `state_battle`, `state_pc`, `state_shop`, `state_gym`, `state_pokecenter`, `state_cave`, `state_water`, `app_icon`, `pkmn_unknown`|hand-make / Bulbapedia|
|Reserved|50|future expansion|—|
|**Used**|**~174 hard-uploaded**|||

**Strong recommendation: use external URLs (PokéAPI sprite CDN) for ALL Pokémon sprites in the "little battle" mode** — 493 species × 2 (front+back) is 986, far over budget. PokéAPI CDN is reliable, free, and Discord supports it. Reserve the 300-asset budget for _unique_ assets (locations, Dawn) where there's no good external source.

**Asset key naming convention** (final recommendation):

- Prefix by category: `loc_`, `pkmn_`, `trainer_`, `dawn_`, `state_`, `app_`
- Snake_case, no special chars
- For Pokémon: `pkmn_392` is enough (no name needed; key just has to be unique). If you want to be cute: `pkmn_392_infernape_front`, but that wastes characters and locks you in.
- Keep a `assets.h` const map in code: `enum class LocationAsset { JubilifeCity, ... }` with a `const char* assetKey` field.

### 5. Prior art: what to study, what to skip

- **kiwi515/Gen4RPC** — Python + Lua, save-file-based, Diamond/Pearl only, ~5 stars, last commit years ago, "support Platinum" is on the TODO. The Lua script (`export.lua`) writes RAM dumps to disk; the Python (`rpc.py`) reads them and pushes to Discord via `pypresence`. **Read the Lua to learn the Diamond/Pearl pointer offsets** (they're sibling games to Platinum, often the same struct layout shifted by a few bytes), but don't model your architecture on it — the file-shuffling intermediary is exactly what you're trying to avoid.
- **dude22072/PokeStats** Lua scripts — has working Platinum offsets for party Pokémon decryption in DeSmuME. **This is your best concrete code reference for the RAM offsets.**
- **EverOddish/PokeStreamer-Tools** `auto_layout_gen4_gen5.lua` — has the master pointer table for Diamond/Pearl/Platinum/HG/SS and BW1/2 in one file.
- **pret/pokeplatinum** — the gold standard. The `src/trainer_data.c`, `src/save/`, `src/pokemon/` files give you the exact C struct layouts. To find a specific field's RAM offset, find the struct in pret, count bytes, then find the struct's allocation site (look for `SaveData_New` or `FieldSystem_New`).
- **JimB16/PokePlat** — older Pokémon Platinum _disassembly_ (ASM), less maintained than pret's decomp. Useful for cross-reference.
- **PKHeX** (kwsch/PKHeX) — the SAV4 reader code (`SAV4Platinum.cs`, `PK4.cs`) is the most battle-tested ground-truth implementation of Gen 4 save parsing. Port the relevant fields' offsets to C++.
- **mGBA's DiscordCoordinator.cpp** (`src/platform/qt/DiscordCoordinator.cpp`) — almost exactly the integration shape you want. Read this code; it's how a Qt-based emulator wires `discord-rpc` into a Qt frontend with a settings dialog. Steal the structure outright (it's MPL-2.0; melonDS is GPL-3, compatible).
- **MechaDragonX/Bheithir** — separate-process Discord RPC for emulators, including melonDS. Reads the window title to detect the loaded game. **Don't use this approach** — it can't read game state, only ROM titles.
- **LogicismDev/LogRPC** — uses Gen4RPC's Lua bridge, also limited.
- **PR #1671 (NPO-197 Lua scripting)** — if this gets merged before you ship, you could prototype Phase 1 entirely in Lua before doing the C++ port. Probably not worth waiting for.
- **Project Pokémon docs** — "Notable Breakpoints", "Platinum Save Structure", and "Structure of Pokémon in RAM from Generation 4 Games" (by Poke J) are the three essential reference threads.

### 6. Architecture decision: **fork melonDS, don't side-channel**

I'm going to push back gently on the "fork to avoid breakage" framing and then agree with the conclusion anyway.

**The argument for fork (the user's instinct):**

- Single binary, single config, no IPC layer to fail
- Native access to NDS state (no JSON serialization round-trip)
- One Qt settings dialog, one toggle
- Can hook into emulator events (ROM load, pause, save state) cleanly via Qt signals
- The user is comfortable with C++

**The argument against fork (and for side-channel):**

- Maintaining a fork in sync with upstream melonDS is real work — Arisotura's repo has frequent core refactors
- A side-channel companion (melonDS dumps `state.json` to disk every 5s; a separate process reads it) decouples your update cadence from melonDS's
- The user has stronger C# / TypeScript / Python skills than C++

**My opinionated take: fork it.** Here's why:

1. Your fork only touches `src/frontend/qt_sdl/`. The core (`src/`) is where Arisotura does most refactoring; the Qt frontend is more stable. You're adding ~6 files in a new subdirectory, never modifying existing files except `src/frontend/qt_sdl/CMakeLists.txt` (one `add_subdirectory()` call) and `MainWindow.cpp` (one menu-item registration). Merge conflicts will be near-zero.
2. The side-channel approach has a serious problem: **the emulator has to know enough about Pokémon Platinum to dump useful state**. So you've already paid the cost of implementing the Gen4Reader in C++ — you might as well keep it in-process. A "dumb" state file (raw memory dump) just shifts the parsing into the companion app, doesn't reduce work.
3. Discord RPC IPC is already a side-channel (named pipe to Discord). Adding another side-channel between the emulator and the RPC client creates two things to debug.
4. The user says she wants this — and her instinct is correct. The "C# companion app" path optimizes for her language comfort but pessimizes for the system.

**Hedged recommendation**: structure the C++ code so the `Gen4Reader` exposes a `Gen4State` struct via a stable interface. If you later regret the fork, you can extract `Gen4Reader` + `Gen4Maps` + `DiscordRPCManager` into a tiny shim that reads from a memory-mapped file the emulator dumps. The interface becomes the seam.

### 7. The "little battle" feature: feasible, but Phase 3

- **Visual layout in Discord**: when both `largeImage` and `smallImage` are set, the small image renders as a **circular badge in the bottom-right corner** of the large image, ~30% of the large image's diameter. So your "little battle" is large=enemy front sprite, small=player back sprite — Discord will overlay them like the actual DS battle screen view from behind the player. This is genuinely cute and worth doing.
- **Battle entry/exit detection**: poll the BattleSystem allocation pointer (or watch a known battle-state byte). On entering battle, switch the RPC payload from "exploring" mode to "battle" mode:
    - `details` = "Wild Bidoof appeared!" or "Battling Gym Leader Fantina"
    - `state` = "Lv.32 Infernape vs Lv.30 Drifblim"
    - `largeImageKey` = `pkmn_<enemyDex>` (front) — pull from PokéAPI CDN as external URL
    - `smallImageKey` = `pkmn_b_<playerLeadDex>` (back) — uploaded asset
    - `partySize` = your alive count, `partyMax` = total — same as overworld
- **Which player Pokémon to show**: the _first non-fainted_ party slot (the lead, except when fainted). Walk party slots 0..5, find the first with `currentHP > 0`. Use that species' back sprite.
- **Which enemy Pokémon to show**: in trainer battles, the currently-active opponent (read from the BattleSystem's "active mon" slot 0 of the enemy team). For wild battles, the only wild Pokémon. For doubles, just show slot 0.
- **Sprite source**:
    - Player back sprites for the ~50 most common Pokémon: upload to Discord as `pkmn_b_<dex>`
    - Enemy front sprites: external URL `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/<dex>.png` (Gen 8 style — for Gen 4 era look use `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-iv/platinum/<dex>.png`)
    - Spriters Resource has the _exact_ in-game Platinum sprites under "Pokémon (4th Generation)" — rip these for the highest-fidelity look if you have the budget. The PokéAPI Platinum-folder URLs above are derived from these rips and easier than re-uploading.

---

## Details

### Concrete file/folder structure

```
melonDS/                                    (your fork)
├── CMakeLists.txt                          (add option ENABLE_DISCORD_RPC)
└── src/
    └── frontend/
        └── qt_sdl/
            ├── CMakeLists.txt              (modified: add_subdirectory + sources)
            ├── MainWindow.cpp              (modified: 1 menu item, 1 signal hookup)
            ├── EmuInstance.cpp             (modified: emit rpcStateUpdate signal)
            ├── Config.cpp                  (modified: add DiscordRPC.* keys)
            ├── 3rdparty/
            │   └── discord-rpc/            (git submodule, pinned commit)
            └── DiscordRPC/
                ├── DiscordRPCManager.h
                ├── DiscordRPCManager.cpp   (~200 lines: init, update, shutdown)
                ├── Gen4Reader.h
                ├── Gen4Reader.cpp          (~400 lines: pointer-walk, struct parse)
                ├── Gen4State.h             (POD struct: location_id, party[6], badges, etc.)
                ├── Gen4Maps.h
                ├── Gen4Maps_Locations.cpp  (generated from pret, ~660 entries)
                ├── Gen4Maps_Trainers.cpp   (~100 hand-curated entries)
                ├── Gen4Maps_Species.cpp    (494 entries, generated)
                ├── DiscordRPCDialog.h
                ├── DiscordRPCDialog.cpp
                ├── DiscordRPCDialog.ui     (Qt Designer)
                └── data/
                    └── (optional: JSON tables loaded at runtime instead of compiled)
```

### Memory access pattern (Phase 1 pseudocode)

```cpp
// Gen4Reader.cpp
namespace melonDS::DiscordRPC {

constexpr u32 PLAT_US_SAVE_PTR_ADDR = 0x02101D40;
constexpr u32 PLAT_US_SMALL_BLOCK_OFFSET = 0x00000;  // small block starts at base
constexpr u32 PLAT_PARTY_OFFSET = 0xA0;
constexpr u32 PLAT_BADGES_OFFSET = 0x96;     // single byte, 8 bits = 8 badges
constexpr u32 PLAT_PLAYTIME_HOURS_OFFSET = 0xA4;  // verify against PKHeX

struct Gen4PartyMon {  // 236 bytes
    // 0x00..0x07 = personality, checksum, pid
    u32 pid;
    u16 _pad;
    u16 checksum;
    // Block A (32 bytes after decrypt - in RAM, already decrypt)
    u16 species;        // 0x08
    u16 heldItem;       // 0x0A
    u16 otId, otSid;    // 0x0C, 0x0E
    u32 exp;            // 0x10
    u8  friendship;     // 0x14
    u8  ability;        // 0x15
    // ... etc
    // Battle stats (party-only, offsets 0x88..0xEB)
    u8  status;         // 0x88
    u8  level;          // 0x8C
    u16 currentHP;      // 0x8E
    u16 maxHP;          // 0x90
    // ...
};

bool readGen4State(NDS& nds, Gen4State& out) {
    // 1. Read the working save pointer
    u32 saveBase = nds.ARM9Read32(PLAT_US_SAVE_PTR_ADDR);
    if (saveBase < 0x02000000 || saveBase >= 0x02400000) return false;  // sanity

    // 2. Read trainer card stats
    out.badges = __builtin_popcount(nds.ARM9Read8(saveBase + 0x96));
    out.playtimeSec =
        nds.ARM9Read16(saveBase + 0xA4) * 3600 +
        nds.ARM9Read8(saveBase + 0xA6)  * 60 +
        nds.ARM9Read8(saveBase + 0xA7);

    // 3. Party
    out.partyCount = nds.ARM9Read32(saveBase + PLAT_PARTY_OFFSET - 4);
    for (int i = 0; i < out.partyCount && i < 6; i++) {
        u32 monBase = saveBase + PLAT_PARTY_OFFSET + i * 236;
        out.party[i].species   = nds.ARM9Read16(monBase + 0x08);
        out.party[i].level     = nds.ARM9Read8 (monBase + 0x8C);
        out.party[i].currentHP = nds.ARM9Read16(monBase + 0x8E);
        out.party[i].maxHP     = nds.ARM9Read16(monBase + 0x90);
    }

    // 4. Pokédex caught count: walk the dex bitfield
    out.dexCaught = 0;
    for (int byte = 0; byte < 64; byte++) {
        u8 b = nds.ARM9Read8(saveBase + PLAT_DEX_CAUGHT_OFFSET + byte);
        out.dexCaught += __builtin_popcount(b);
    }

    // 5. Map ID — *separate* pointer chain (FieldSystem), TBD
    out.locationId = readFieldLocationId(nds);

    // 6. Battle state — *separate* pointer chain (BattleSystem), TBD
    out.battleState = readBattleState(nds);

    return true;
}

}  // namespace
```

### Discord RPC manager (Phase 1 pseudocode)

```cpp
// DiscordRPCManager.cpp
#include "discord_rpc.h"

void DiscordRPCManager::init(const std::string& appId) {
    DiscordEventHandlers h{};
    h.ready = [](const DiscordUser*) { /* log */ };
    h.errored = [](int code, const char* msg) { /* log */ };
    Discord_Initialize(appId.c_str(), &h, /*autoRegister=*/0, nullptr);
    startTimestamp = time(nullptr);
}

void DiscordRPCManager::update(const Gen4State& s) {
    DiscordRichPresence p{};
    auto details = formatDetails(s);   // "Exploring Mt. Coronet"
    auto state = formatState(s);        // "Badges: 4 | Pokédex: 87"
    p.details = details.c_str();
    p.state = state.c_str();
    p.partySize = countAlive(s);
    p.partyMax = s.partyCount;
    p.startTimestamp = time(nullptr) - s.playtimeSec;
    auto largeKey = locationAssetKey(s.locationId);
    auto largeText = locationName(s.locationId);
    p.largeImageKey = largeKey.c_str();
    p.largeImageText = largeText.c_str();
    if (s.battleState.inBattle) {
        // override with little-battle layout
        p.largeImageKey = enemyFrontUrl(s.battleState.enemySpecies).c_str();
        p.smallImageKey = ("pkmn_b_" + std::to_string(s.battleState.playerLead)).c_str();
    } else {
        auto smallKey = dawnDirectionKey(s.dawnDirection, s.dawnMode);
        p.smallImageKey = smallKey.c_str();
    }
    Discord_UpdatePresence(&p);
}

void DiscordRPCManager::tick() { Discord_RunCallbacks(); }
void DiscordRPCManager::shutdown() { Discord_ClearPresence(); Discord_Shutdown(); }
```

### Phased implementation plan

**Phase 0 — Setup (1 evening)**

- Fork melonDS-emu/melonDS
- Build it locally on Windows 11 (vcpkg + CMake + Qt 6 + MSVC). Verify Pokémon Platinum runs.
- Register a Discord application; copy the App ID
- Vendor `discord/discord-rpc` as a submodule
- Add `ENABLE_DISCORD_RPC` CMake option; gate everything behind it
- Smoke test: hard-coded `details = "Hello world"`, see it appear in Discord profile

**Phase 1 — MVP (1-2 weekends)**

- Implement `Gen4Reader::readGen4State` for: location ID, badges (popcount), Pokédex caught count, party species/HP, playtime
- Implement `Gen4Maps_Locations.cpp` (extract from pret's `include/constants/map.h` or Bulbapedia's table — a Python script can do this in 20 minutes)
- Implement `formatDetails` with simple location → "Exploring Jubilife City" template; special-case "Pokémon Center" / "Cave" / "Route X"
- 5-second QTimer in EmuInstance polls `Gen4Reader`, pushes to `DiscordRPCManager::update`
- Settings dialog: enable/disable checkbox, app ID field
- **Stop here and play through a few hours.** Validate every reading. The hardest bug here will be wrong offsets in the SaveData struct vs Bulbapedia's table — diff against PKHeX reading the same .sav file.

**Phase 2 — Locations + Trainers (1 weekend)**

- Upload ~80 location backgrounds to Discord
- Hand-curate the gym leader / E4 / Cynthia / Cyrus / Barry trainer ID list (~20 names)
- Find BattleSystem pointer & trainer ID via Cheat Engine + DeSmuME
- "Battling Gym Leader Fantina" detail strings work

**Phase 3 — Little Battle Mode (1-2 weekends)**

- Battle entry/exit detection
- Read player lead and enemy active Pokémon from BattleSystem
- Upload ~50 most common back sprites to Discord
- Wire up external URL for enemy front sprites (PokéAPI CDN)
- Dynamic state line: "Lv.X Infernape vs Lv.Y Drifblim"

**Phase 4 — Polish (ongoing)**

- Player overworld direction + movement state via FieldSystem; upload Dawn sprites
- "Browsing the PC", "In a Pokémon Center" special detection (location-based)
- Activity type "Competing" during gym/E4 battles (requires switching to `EclipseMenu/discord-presence` or hand-rolled IPC)
- Gym leader logos as small image during gym battles (replaces Dawn back-sprite)

### Build dependency wiring (CMake)

In `src/frontend/qt_sdl/CMakeLists.txt`, add:

```cmake
option(ENABLE_DISCORD_RPC "Enable Discord Rich Presence" ON)
if(ENABLE_DISCORD_RPC)
    set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(USE_STATIC_CRT OFF CACHE BOOL "" FORCE)  # match melonDS's CRT
    add_subdirectory(3rdparty/discord-rpc EXCLUDE_FROM_ALL)
    target_compile_definitions(melonDS PRIVATE ENABLE_DISCORD_RPC=1)
    target_link_libraries(melonDS PRIVATE discord-rpc)
    target_sources(melonDS PRIVATE
        DiscordRPC/DiscordRPCManager.cpp
        DiscordRPC/Gen4Reader.cpp
        DiscordRPC/Gen4Maps_Locations.cpp
        DiscordRPC/Gen4Maps_Trainers.cpp
        DiscordRPC/Gen4Maps_Species.cpp
        DiscordRPC/DiscordRPCDialog.cpp
    )
    target_include_directories(melonDS PRIVATE DiscordRPC)
endif()
```

### Things to verify by hand once the build works

1. The `0x02101D40` save pointer is correct for **Platinum US (Rev 1)** specifically. Pret builds two ROM revisions; offsets differ slightly between them. Detect ROM by reading the cart header (`NDSCart` exposes `GetHeader()`) and check the game code "CPUE" + a SHA-1 / version byte. Branch your offsets per revision (Rev 0 vs Rev 1 vs EU/JP).
2. The badges byte is at the offset you expect — write `0xFF` via the in-game (after dumping save) and confirm the cheat works against your popcount.
3. RAM party-Pokémon data really is decrypted, not encrypted. If you see species values like `0x4F23` instead of `0..493`, you're reading encrypted data; you've found the wrong buffer.
4. Don't read RAM during the first few frames after boot — the SaveData pointer at `0x02101D40` is `NULL`/garbage until the title screen finishes. Gate your polling on `saveBase >= 0x02000000` (the sanity check above).

---

## Caveats

- **All "live" RAM offsets in this report come from public reverse-engineering** (cheat code databases, Lua scripts, Bulbapedia). Some are universally agreed (the `0x02101D40` save pointer is in literally every Platinum AR cheat ever published, ~17 years of consistent usage); others (the badges byte at `+0x96`, party at `+0xA0`) are inferred from cheat behavior and may need a one-byte adjustment when you implement. **Always cross-validate by writing a known value through PKHeX, saving, loading in melonDS, and reading at your offset.**
- **The save data structure for Platinum has small layout differences from Diamond/Pearl** — Bulbapedia notes the small block is `0x0CF2C` long in Pt vs `0x0C100` in DP, with extra fields slotted in. Some offsets within the small block shift. The Gen4RPC project specifically calls out "Support Platinum, combine Pt headers with D/P if possible" as an unfinished TODO — implying it's not a trivial sed-and-replace.
- **The FieldSystem (overworld map ID, player coords, facing direction, movement mode) is _not_ in the SaveData struct.** It's an overlay-loaded struct in EWRAM with a runtime-allocated address. You will need to find this yourself by Cheat Engine scanning, and the address may shift between melonDS save states (though not within a session). Plan for ~1 day of reverse engineering for this.
- **Battle detection via the BattleSystem pointer is similarly unmapped publicly for Platinum** — pret has the C struct but no one has published the live runtime address. Phase 3 will require you to do this RE work yourself.
- **The Discord deprecation status of `discord-rpc`** means there's nonzero risk that Discord turns off the legacy IPC protocol someday. As of GDC 2026 they're actively pushing the Social SDK but still supporting the IPC; mGBA, Citra, and Dolphin all still use it. If you want zero risk, use `EclipseMenu/discord-presence` (which speaks the same IPC but is actively maintained as a community fork).
- **Activity types (Competing/Watching) are not in the legacy `discord-rpc` C API** — only "Playing". You can't set "Competing" via the standard library. If this matters to you, you'll need a different lib in Phase 4.
- **Multiple ROM revisions of Platinum exist** (US Rev 0, US Rev 1, EU, JP). Your offset table needs a per-revision branch, detected from the NDS cart header. The pret project builds exactly Rev 0 and Rev 1; they have different SHA-1s and _some_ internal offsets shift.
- **The Discord application has a 5-second update cadence enforced server-side**; emitting more often is silently dropped, not an error. Don't try to "race" the limit by sending 4.5s updates — Discord's server clock isn't synced to yours and you'll lose updates.
- **Threading**: melonDS's EmuThread runs the JIT and emulation; Qt's main thread runs the UI. The `discord-rpc` library is _not_ explicitly thread-safe. Do all `Discord_*` calls from a single thread (recommend: Qt main thread, via signals from EmuThread). RAM reads via `NDS::ARM9Read*` from the main thread _while EmuThread is running_ are an undocumented mutex situation — they're probably safe (MainRAM is just a u8 array, reads of u8/u16/u32 are atomic on x86), but if you see flicker, gate the read on a frame-completion signal from EmuThread.
- **The 300-asset limit is per-application-ID**, not per-game. If you want different content for D/P/Pt/HG/SS in the same fork, register one app ID per game or share the assets across games (most are unique anyway: location backgrounds differ; Pokémon sprites are shared).
- **GPL-3 license**: melonDS is GPL-3, `discord-rpc` is MIT. Compatible. Your fork must remain GPL-3 if distributed. If you upload screenshots/sprite rips of a Nintendo game to Discord, that's a copyright gray area Nintendo could in theory complain about; the convention in the emulation community is that this is fine for personal/community projects but don't publicize the asset bucket as a content distribution.