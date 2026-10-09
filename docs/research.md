# DSiRPC research notes

This file distills the older research notes that used to live in `ContextDocs/` (removed in the cleanup; they're still in the git history). Several of those notes were AI-generated (Gemini/Claude) before anything was checked, and many of their claims turned out wrong. Only content that still holds up against the melonDS RAM dump (`ram_dump.bin`: Platinum USA Rev 1, trainer "Vivia" in Jubilife City), the pret/pokeplatinum decompilation and the RetroAchievements (RA) code notes is kept here. The melonDS/TCP/web-server architecture is dropped. **[DOCUMENTATION.md](DOCUMENTATION.md) section 9 is the authoritative memory map.** This file does not repeat it and only adds to it. Addresses are hardware addresses (the dump's index 0 = `0x02000000`), and `S` = the save block pointer `[0x02101D40]` (`0x0227E140` in the dump).

## 1. What was kept from each old note

| Old note | Kept |
|---|---|
| Values to Obtain | Viv's design goals (section 2). Links in section 9. |
| GEN IV Character Encoding | Encoding facts and byte examples (section 3) |
| Why 'Vivia' Appears Multiple Times | The question, re-answered from the dump (section 4) |
| Resources | All links, with notes (section 9) |
| PokeAPI Docs | Relevant endpoints and sprite URLs (section 8) |
| Gemini "RAM and Save Analysis" | Save offsets, which are correct once converted from `.sav` offsets (section 5). Some Pokémon struct fields (section 6.2). |
| Gemini "Technical Architecture" | Same `.sav`-offset insight. Dex bit arrays. The idea of using image URLs. |
| Claude "Complete Build Guide" | Sprite URL patterns, prior-art list (unverified), a few presence ideas |
| RAM Structure (Basic) | Nothing new. Its offsets and the "unencrypted stats" claim are wrong. |

## 2. Design goals for the presence

These are Viv's goals from "Values to Obtain", with their status in the current repo.

| Goal | Status | Notes |
|---|---|---|
| Line 1 = current action, e.g. "Exploring Mt. Coronet" | Done | `Exploring <location>` |
| Line 1 in battle, e.g. "Battling Gym Leader Fantina" | Done | Battle kind from the music ID. Name from the table for battle `+0x3C6`. |
| Line 1 for menus, e.g. "Browsing the PC in Jubilife City" | Open | Lead in section 7 |
| Line 2 = stats, e.g. "Badges: 4 \| Pokédex: 87" | Done | |
| Discord party fraction = Pokémon still standing / party size | Done | Eggs are excluded. Discord hides the fraction while the type is Competing. |
| Activity type that changes with what you are doing | Done | Playing in the overworld, Competing in battle |
| Dawn/Lucas sprite facing the way you face | Done | Large image, one walking GIF per direction |
| Running and biking sprite variants (4 directions each) | Open | Leads in section 7 |
| Area icon or art per location as the main image | Open | Section 7 |
| "Little battle": foe's front sprite large, your Pokémon's back sprite small | Done | Shiny-aware, like the overworld sprites |
| Playtime | Done | The timer counts up from the save's playtime |
| The rival's real name in rival battles | Done | Read from `S+0x27FC` when the trainer class is `0x3F` |
| Names beyond the fixed trainer table (all gym leaders, trainer classes) | Open | Section 7 |
| Upload the party and trainers' Pokémon as Discord assets (300-slot budget) | Superseded | Images are URLs on GitHub Pages, so there is no asset budget |

Other ideas from the old notes, not committed to: special-case Pokémon Centers, caves and gyms by map name; show the gym's badge as the small image in gym battles; add a link button (Discord allows up to two), e.g. to the location's Bulbapedia page.

## 3. Gen IV text encoding

Strings are arrays of 16-bit little-endian code units. Checked against the decomp's `enum CharCode` (`include/constants/charcode.h`), the repo charmap and the dump.

| Code | Meaning | Code | Meaning |
|---|---|---|---|
| `0x0121`-`0x012A` | `0`-`9` | `0x01DE` | space |
| `0x012B`-`0x0144` | `A`-`Z` | `0x0001` | full-width space |
| `0x0145`-`0x015E` | `a`-`z` | `0xE000` | line break |
| `0x01AB` `0x01AC` `0x01AD` `0x01AE` | `!` `?` `,` `.` | `0x25BC` / `0x25BD` | text box clear / scroll |
| `0x01BB` `0x01BC` `0x01BE` | `♂` `♀` `-` | `0xFFFE` | start of a format argument (a placeholder like `{STRVAR}`) |
| `0x01AF` | `…` | `0xFFFF` | end of string |

- Buffer sizes: trainer and rival names are 8 units (7 characters + end), Pokémon nicknames are 11 (10 + end), PC box names are 20.
- Examples: "Vivia" = `40 01 4D 01 5A 01 4D 01 45 01`, "Flippy" = `30 01 50 01 4D 01 54 01 54 01 5D 01`. When hex-searching, search for the characters only, without the terminator.
- Party nicknames have no plain copy in the save block, because the party data is encrypted. "Flippy" does not occur in plain anywhere in the dump. During a battle the nickname is in plain in the BattleMon at `+0x36`.
- `PokeGen4Charmap.txt` is pret/pokediamond's charmap. The codes for letters, digits and punctuation match Platinum. Its "Function codes" block at the end reuses `0x0100` and `0x0400`, which are `○` and `가` in the character table. `charmap.py` keeps the last definition, so those two codes decode as `{STRVAR_1}`/`{STRVAR_4}`. This doesn't affect English names.
- ImHex: import the charmap as a custom encoding. The Data Inspector's "Custom Encoding" row then decodes the selected bytes (Viv confirmed this with "Vivia").

## 4. Why "Vivia" appears several times in RAM

The old answer ("dual save blocks mirrored in RAM, plus caches") was mostly speculation. Here is what the four copies in the dump actually are:

| Address | What it is | Evidence |
|---|---|---|
| `0x0227E1BC` = `S+0x7C` | The live `TrainerInfo.name`. This is the only copy to read. | Followed by TID `0x3E9B`, SID `0x629E`, money 744, gender 1, language 2. The `12 34 00 00` before it, which the old notes flagged, is the Options u16 `0x3412` at `S+0x78` plus padding. |
| `0x0238C760` | Inside an older image of the whole normal save block, in flash layout (block starts at `0x0238C6F8`, name at `+0x68`) | Its footer at `0x02399610` has signature `0x20060623`, size `0xCF2C` and block counter 16. The live block's counter is 17, so this image is from the previous save. |
| `0x023A7A80` | Another flash-layout copy (same bytes after the name), mostly overwritten | No intact footer. Only fragments still match the live block. |
| `0x022A6D38` | A freed heap `String` | The 8-byte header before it reads max length 6, length 5, integrity `0xB6F8D2ED`. That is `STRING_MAGIC_NUMBER` (`0xB6F8D2EC`) + 1, which `String_Free` writes. The screenshots had a string copy at `0x022A66B0`, so heap objects move between sessions. |

In the decomp, `SaveData_LoadCheck` (`src/savedata.c`) reads both flash slots into 0x20000-byte heap buffers and frees them without clearing. That is the likely origin of the stale images, but it isn't proven. Takeaway: always read through the pointer. Never search RAM for values.

## 5. Save data: `.sav` offsets vs RAM offsets

The RAM save block is a 0x14-byte `SaveData` header (`[1,1,0,0,0]` in the dump) followed by a body laid out exactly like flash. So **RAM offset from S = `.sav` offset + 0x14**. Most offsets in the Gemini notes (and in Bulbapedia/PKHeX) are `.sav` offsets. They become correct after this conversion:

| `.sav` | RAM | Field | | `.sav` | RAM | Field |
|---|---|---|---|---|---|---|
| `0x68` | `S+0x7C` | trainer name | | `0xA0` | `S+0xB4` | party Pokémon |
| `0x78`/`0x7A` | `S+0x8C`/`0x8E` | TID/SID | | `0x630` | `S+0x644` | bag, items pocket |
| `0x82` | `S+0x96` | badges | | `0x1280` | `S+0x1294` | location |
| `0x8A` | `S+0x9E` | playtime | | `0x1642`/`0x1643` | `S+0x1656`/`0x1657` | Pokédex / National Dex |
| `0x9C` | `S+0xB0` | party count | | `0x27E8` | `S+0x27FC` | rival name |

**Flash layout** (from the decomp; block sizes confirmed by the footers in the dump): the primary slot is at `0x00000` and the backup slot at `0x40000`. In each slot, the normal block (`0xCF2C` bytes, footer included) comes first, followed by the boxes block (`0x121E4` bytes). Extra data such as the Hall of Fame and battle recordings starts at `0x20000`. In RAM, the normal block's footer is at `S+0xCF2C` and the boxes block starts at `S+0xCF40`.

| Footer offset | Field |
|---|---|
| `+0x00` / `+0x04` | save counter u32 / block counter u32 |
| `+0x08` | block size u32, footer included |
| `+0x0C` | signature `0x20060623` |
| `+0x10` / `+0x12` | block ID u8 (0 normal, 1 boxes) / checksum u16 |

**Computing any offset from the decomp:** the pages follow the order of `gSaveTable` (`src/savedata/save_table.c`). Each page takes `size + (4 - size % 4) + 4` bytes (`SaveTableEntry_BodySize`), and a 0x14-byte footer ends each block. Examples: PlayerSave `0x2C` becomes `0x34`, Party `0x590` becomes `0x598`, and FieldOverworldState `0xA0` becomes `0xA8`. That last one puts the Pokédex page at `S+0x133C`, matching the magic `0xBEEFCAFE` seen there. The same walk lands the rival name at `S+0x27FC`.

## 6. Additional verified RAM facts (not in DOCUMENTATION.md)

### 6.1 Save block

The source for each row is the decomp struct layout. The dump values match.

| Offset | Field | Dump |
|---|---|---|
| `S+0x78` | Options u16: text speed bits 0-3, sound 4-5, battle style 6, battle scene 7, button mode 8-9, frame 10-14 | `0x3412` |
| `S+0x95` | language u8 (2 = English) | 2 |
| `S+0x97` | Union Room appearance u8 | `0x0E` |
| `S+0x98` | game code u8 (12 = Platinum) | 12 |
| `S+0x99` | bit 0 = game cleared (set in `clear_game.c`), bit 1 = National Dex | 0 |
| `S+0x644` | Bag. Each slot is u16 item ID + u16 count. Pockets: Items `+0x644` (165 slots), Key Items `+0x8D8` (50), TMs/HMs `+0x9A0` (100), Mail `+0xB30` (12), Medicine `+0xB60` (40), Berries `+0xC00` (64), Poké Balls `+0xD00` (15), Battle Items `+0xD3C` (30). Matches the RA notes. | Journal, Vs. Recorder, Town Map, TM27, 3 Potions, 10 Poké Balls... |
| `S+0xDB4` | item registered to SELECT, u32 | 442 (Town Map) |
| `S+0xDC0` | script vars (u16 each), then event flags. `S+0xE20` = starter species (RA). | `S+0xE20` = 393 (Piplup) |
| `S+0x12BC` / `S+0x12E4` | previous / exit location (same 5 x s32 layout as `S+0x1294`) | |
| `S+0x1320` | cycling gear u16 | 0 |
| `S+0x1322` | Running Shoes obtained u16 | 1 |
| `S+0x1324` | avatar state u32: 0 walking, 1 cycling, 2 surfing (see 6.3: this is live) | 0 |
| `S+0x1328` / `+0x132A` / `+0x132C` | poison step counter, Safari steps, Safari Balls (u16 each) | 2 / 0 / 0 |
| `S+0x1657` | National Dex obtained u8 | 0 |
| `S+0x27FC` | rival name, 8 x u16 (chosen in the intro) | a player-chosen name, not "Barry" |
| `S+0xCF40` | PC boxes: u32 current box, then 18 x 30 box Pokémon of 136 bytes each from `S+0xCF44`, encrypted like the first 136 bytes of a party Pokémon | boxes empty |

### 6.2 Pokémon and BattleMon fields not read yet

The offsets below are within the unshuffled 32-byte blocks (`include/struct_defs/pokemon.h`, `include/battle/battle_mon.h`). The BattleMon offsets that DOCUMENTATION already uses all match this struct.

| Where | Fields |
|---|---|
| Block A | `+0x08` EXP u32, `+0x0C` friendship, `+0x0D` ability, `+0x0E` markings, `+0x0F` language, `+0x10`-`+0x15` EVs (HP, Atk, Def, Spe, SpA, SpD), `+0x16`-`+0x1B` contest stats |
| Block B | `+0x08` current PP x4, `+0x0C` PP Ups x4, `+0x10` IVs (5 bits each in the order HP, Atk, Def, Spe, SpA, SpD; bit 30 egg, bit 31 nicknamed), `+0x18` bit 0 fateful encounter, bits 3-7 **form**, `+0x1C`/`+0x1E` Platinum egg/met location |
| Block C | `+0x17` origin game |
| Block D | `+0x00` OT name, `+0x10` egg date, `+0x13` met date (Y, M, D), `+0x16`/`+0x18` Diamond/Pearl egg/met location, `+0x1A` Pokérus, `+0x1B` ball, `+0x1C` met level (bits 0-6) + OT gender (bit 7), `+0x1D` encounter terrain |
| Party `0x88` | status u32: bits 0-2 sleep turns, 3 poison, 4 burn, 5 freeze, 6 paralysis, 7 toxic, 8-11 toxic counter |
| Party | `0x8D` ball capsule ID, `0x92`/`0x94`/`0x96`/`0x98`/`0x9A` Atk/Def/Spe/SpA/SpD, `0x9C` held mail (0x38 bytes), `0xD4` ball capsule (0x18 bytes) |
| BattleMon | `+0x02`/`+0x04`/`+0x08`/`+0x0A` Atk/Def/SpA/SpD (Spe at `+0x06`, the stat stages at `+0x18`, the types at `+0x24`/`+0x25` and the OT ID at `+0x74` are read now), `+0x26` bits 0-4 **form** (bit 5 = shiny), `+0x27` ability, `+0x35` friendship, `+0x54` OT name, `+0x68` PID, `+0x7F` ball |

Game form numbers (`include/constants/forms.h`): Deoxys 1-3 = Attack/Defense/Speed; Wormadam and Burmy 1-2 = Sandy/Trash; Rotom 1-5 = Heat/Wash/Frost/Fan/Mow; Giratina 1 = Origin; Shaymin 1 = Sky; Castform 1-3 = Sunny/Rainy/Snowy; Shellos and Gastrodon 1 = East; Cherrim 1 = Sunshine; Unown 0-27 = A-Z, !, ?. See section 8 for the matching sprites.

### 6.3 FieldSystem pointer chain

This chain was checked in the dump against the decomp structs. It has not been read on hardware yet.

`FS = [0x021C07DC]` (RA calls it "Version Pointer Region"). In the dump, `FS+0x0C` equals `[0x02101D40]` and `FS+0x1C` equals `S+0x1294`.

| Pointer | Field |
|---|---|
| `FS+0x00` | FieldProcessManager*: `+0x00` parent app, `+0x04` **child app** (NULL in the overworld dump) |
| `FS+0x0C` / `FS+0x1C` | SaveData* / Location*. The latter points at `S+0x1294`, so the saved location is the live one. |
| `FS+0x38` / `FS+0x3C` | MapObjectManager* / **PlayerAvatar*** |
| PlayerAvatar `+0x08` / `+0x0C` | movement action / movement action speed |
| PlayerAvatar `+0x1C` / `+0x20` | avatar state (0 walk, 1 bike, 2 surf) / gender |
| PlayerAvatar `+0x30` / `+0x38` | player MapObject* / PlayerData*. The PlayerData* is `S+0x1320`, which is why `S+0x1324` is live. |
| MapObject `+0x28` / `+0x2C` | facing / moving direction (int, 0-3) |
| MapObject `+0x64`/`+0x68`/`+0x6C`, `+0x70` | tile x/y/z (dump: 175/4/780), position as 3 x fx32 |
| MapObject `+0xA4` | movement action |

The RA "Player Direction and Action" address (see DOCUMENTATION) is exactly `MapObject+0x28`, the low half of the facing int. It contains no action bits. The PlayerAvatar is freed and recreated on every map change (`field_map_change.c`), so re-walk the chain on each poll and range-check every pointer.

## 7. Leads for the open goals

- **Biking/surfing:** read `S+0x1324`. `PlayerAvatar_SetPlayerState` writes it when you mount the bike or start surfing (`ov5_021DFB54.c`), and a warp resets cycling to walking where bikes aren't allowed, and resets surfing to walking. Still needs a live check.
- **Running:** there is no saved state for running. `S+0x1322` only says you own the shoes. Watch PlayerAvatar `+0x08`/`+0x0C` and MapObject `+0xA4` while walking versus running. The MovementAction enum is generated at build time, so its values aren't in the sparse checkout.
- **PC and menus:** while an application (bag, party, summary, PC...) runs, `[[FS]+0x04]` (the child app) should be non-NULL. Its first 16 bytes are the app template (init/main/exit function pointers and the overlay ID), which identifies the app. This needs captures with each menu open. The map name narrows it down: 54 of the 593 map headers in `platinum_data.MAPS` are Pokémon Center floors.
- **Area art:** `platinum_data.MAPS` has 593 map headers but only 125 distinct in-game location names, so at most about 125 images are needed. Spriters Resource is a source (section 9). A PokéAPI location's generation-iv `game_index` is not the map ID (Jubilife City: map 3, PokéAPI `game_index` 6).
- **Trainer names:** the IDs at battle `+0x3C6` that RA lists as "sprite IDs" line up exactly with the decomp's trainer class order (`include/data/trainer_class_genders.h`: `PLAYER_MALE` = 0, `LEADER_ROARK` = `0x3E`, `RIVAL` = `0x3F`, `CHAMPION_CYNTHIA` = `0x45`, `COMMANDER_MARS` = `0x48`, `TRAINER_MIRA` = `0x5E`). That array names every class, including generic ones. The decomp's `BattleSystem` also holds `trainerIDs[4]` and `Trainer trainers[4]`, each with a header (class, sprite) and an 8-unit name. Their offset from `[0x021BFB0C]` hasn't been worked out. For rival battles, the parser shows the name at `S+0x27FC`.
- **Held-item icons:** PokéAPI item sprites (section 8). Map the game's item ID through `game_indices`: Town Map is PokéAPI item 419 but game item 442.
- **Box Pokémon:** `S+0xCF44` (section 6.1). **Story progress:** the vars/flags page at `S+0xDC0`. The flag IDs are in the decomp's generated `vars_flags.h`.

## 8. PokéAPI: what the project can use

The base URL is `https://pokeapi.co/api/v2/`. The API is GET only, needs no authentication and has no rate limit. Its fair-use policy asks you to cache locally (abusers get IP-banned). Use it in the asset pipeline, not on every presence update.

| Endpoint | Use |
|---|---|
| `pokemon/{id or name}/` | `sprites.versions["generation-iv"]["platinum"]`: front, back, shiny and female URLs. Forms with different stats (Deoxys, Rotom...) have their own Pokémon IDs. |
| `pokemon-form/{id or name}/` | Cosmetic forms (Unown, Burmy, Shellos/Gastrodon, Cherrim, Arceus) |
| `pokemon-species/{id}/` | Names and the list of varieties |
| `item/{id or name}/` | `sprites.default` icon. `game_indices` gives the generation-iv game item ID. |
| `location/{id or name}/`, `location-area/{id}/` | Location names and encounters (not map IDs, see section 7) |
| `version/platinum/`, `version-group/platinum/` | Filtering version-specific data (Platinum is version group 9) |

Sprite URLs. All of these returned HTTP 200 on 2026-09-23. Base: `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/`

| Path | Content |
|---|---|
| `pokemon/versions/generation-iv/platinum/{id}.png` | Platinum front sprite |
| `.../platinum/shiny/{id}.png`, `.../platinum/back/{id}.png`, `.../platinum/back/shiny/{id}.png`, `.../platinum/female/{id}.png` | Variants |
| `pokemon/{id}.png`, `pokemon/versions/generation-v/black-white/animated/{id}.gif` | Modern default sprite, animated BW sprite |
| `items/{item-name}.png` | Item icon, e.g. `items/potion.png` |

Mapping a game form number `f` to a PokéAPI Pokémon ID: Deoxys `10000+f`, Wormadam `10003+f`, Shaymin Sky `10006`, Giratina Origin `10007`, Rotom `10007+f`, Castform `10012+f`. Cosmetic forms are file names instead (`201-b`, `412-sandy`, `421-sunshine`, `422-east`, `493-fire`), and these also exist under `platinum/`. Gotcha: pokemon-form IDs use a separate numbering, so Unown B's form ID is also 10001.

Discord side: the image fields accept HTTPS URLs. The project serves its GIFs from GitHub Pages (DOCUMENTATION section 10), which sidesteps the Developer Portal asset limit (300 per application according to the old notes).

## 9. Resources

| Link | Use |
|---|---|
| https://pokeapi.co/?ref=public-apis, https://pokeapi.co/docs/v2 | PokéAPI home and docs (section 8) |
| https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_data_structure_(Generation_IV) | Pokémon struct reference (blocks, shuffle, encryption) |
| https://bulbapedia.bulbagarden.net/wiki/Character_encoding_(Generation_IV) | Text encoding table |
| https://projectpokemon.org/home/files/file/1-pkhex/ | PKHeX save editor. Cross-check save fields (`.sav` offset + 0x14 = RAM offset). |
| https://github.com/turtleisaac/PokEditor | Gen IV ROM data editor (trainers, encounters, etc.) |
| http://www.gamebank.jp/dumper/dl/gbatek.htm | GBATEK, the GBA/DS hardware reference (memory map, I/O) |
| https://frds.github.io/DS-NITRO-SDK | Nintendo DS NITRO SDK docs (RetroReversing), for SDK structures such as the RTC |
| https://pokehacking.com/tutorials/ramexpansion/ | Tutorial on expanding usable ARM9 memory in Gen IV games. Background on how code and overlays sit in RAM. |
| https://deepwiki.com/melonDS-emu/melonDS/2.3-memory-management | melonDS memory internals. Only matters for making offline dumps now. |
| https://www.hexadecimalcalculator.com/calculator/hexadecimal-converter-pokemon | Online Pokémon hex/text converter (not checked; the site is unreachable from here) |
| https://www.spriters-resource.com/ds_dsi/pokemonplatinum/ | Platinum sprite and tile rips, a source for area art and trainer sheets |
| https://github.com/kiwi515/Gen4RPC | Earlier Gen IV Discord presence (save-file based, Diamond/Pearl). Ideas only. |
| https://github.com/pret/pokeplatinum | The decompilation: struct layouts, save page order, enums. It builds both Rev 0 and Rev 1. |
| RetroAchievements game 11732 code notes; ProjectPokemon "Notable Breakpoints" | Exports in `docs/memory-map/`. Only the "DPP (U)" section's Platinum column of the breakpoints page applies to this game. |

## 10. Known wrong claims in the old notes (don't reuse)

| Claim | Reality |
|---|---|
| Party battle stats (`+0x88`...) are unencrypted, or party data is decrypted in RAM | Both parts are encrypted. Box part seed = checksum, stats seed = PID (DOCUMENTATION section 9). |
| Decryption seed = `checksum \| (checksum << 16)` | The seed is the checksum itself |
| Name `S+0x64`/`+0x68`, party `+0xD0`/`+0xA0`, playtime `+0x94`/`+0xA4`/`+0xAC`/`+0x8A`, and so on | Guesses or `.sav` offsets. See section 5 and DOCUMENTATION. |
| Save data at `0x0221BBD0`; map/X/Z/Y/facing at `0x0223B484`-`0x0223B49D`; type chart `0x021D7540`; MT table `0x021FED68`; battle RNG `0x021F6388`; damage formula `0x021A5318` | Copied from the BW/B2W2 sections of the ProjectPokemon page. `0x0223B484`... reads all zeros in the dump. |
| `0x0205EABC`/`0x0205EAC8` hold the player's X/Y | These are code addresses: functions that load X/Y |
| Battle combatants are 128-byte structs at `0x022C0BC2`-`0x022D5780` | A BattleMon is 0xC0 bytes at `[0x021BFB0C]+0x4F40` |
| The saved map ID is only a resume log, and position/map must be found with Cheat Engine | `FieldSystem->location` points at `S+0x1294`, so that location is live |
| Block D: Pokérus `0x7E`, ball `0x7F`, met level `0x80`; origin game at `0x5E` | Pokérus `0x82`, ball `0x83`, met level/OT gender `0x84` (`0x7E`/`0x80` are Diamond/Pearl locations). Origin game is at `0x5F`. |
| Platinum storage block at flash `0x0C100` | That's Diamond/Pearl. Platinum's boxes block starts at `0xCF2C`. |
| Name copies = dual save blocks mirrored in RAM | One live copy, stale load buffers and a freed string (section 4) |

## 11. Unverified leads

- ProjectPokemon breakpoints, Platinum column: `0x021BFB14` LCRNG state, `0x021BFB18` Mersenne Twister table; code at `0x02006590` (load overlay), `0x0205EABC`/`0x0205EAC8` (load player X/Y), `0x02068884` (use Bicycle). The code addresses are only useful as emulator breakpoints. In the dump, both X/Y addresses start with a Thumb `push`, consistent with function entries.
- RA sub-notes under `0x021C07DC` (`+0x14` Poké Radar, `+0x3C` "textbox/badge pointer") don't fit the FieldSystem layout found at that pointer (section 6.3). The RA `[0x02101D2C]` note also lists the Pokétch app, step counter, Poké Radar chain and GTS timer, all using the same 16-bit convention.
- DS clock: RA says weekday `01` = Sunday, but the dump (2026-05-07, a Thursday) reads 4, which means 0 = Sunday. Seconds are probably at `0x021BF5F0` (NitroSDK RTCTime is hour, minute, second; the dump reads 27).
- Battle `+0x3C6`: probably not `TrainerHeader.trainerType`: that's a u8 at offset 1 of a 4-byte-aligned struct, and `B+0x3C6` is even. In the 2026-09-26 Maylene fight it read `0x004c` as a u16 on every read, yet an earlier fight briefly lost the name while she sent out Lucario. The parser now falls back to the low byte when the u16 isn't a known class, `TrainerMemory` keeps the most-read name per battle, and `tools/dsi_status.py` prints the raw class in hex to catch the odd value. Related: `BattleSystem.trainers[4]` (header + 8-unit name) would give every trainer's real name, but it's in `BattleSystem`, whose address isn't known (`B` isn't it).
- Battle `+0x527C`, last move used per battler: in the decomp's `BattleContext` (`include/battle/battle_context.h`), `battleMons[4]` sits at `+0x2D40` (the `padding310A` and `padding3154_01` field names pin the layout), which puts the context at `B+0x2200` and `movePrevByBattler[4]` (u16) at `B+0x527C`. Neighbours from the same layout: `moveTemp`/`moveCur`/`movePrev` at `B+0x5240`/`0x5244`/`0x5248`, `attacker` at `B+0x2264`, `defender` at `B+0x226C`. Checked on hardware on 2026-09-26 for your side: in the Maylene fight it read 0 until the first move, then Fire Blast right after Fire Blast's PP dropped, and stayed there. The foes never got a turn, so the foe's entry (`+0x527E`) is still unconfirmed; the neighbours above are unchecked. To check the foe side: run `tools/dsi_status.py --watch 2` in a battle where the foe moves. The overlay only trusts the record after it has matched a PP drop twice.
- Discord reportedly rejects image URLs hosted on Discord's own media CDN (Gemini, untested).
- NPC positions (for an overlay map): the decomp's FieldSystem holds a MapObjectManager, and each MapObject stores its local ID, graphics ID, facing, tile coordinates and a fixed-point 3D position. The offsets from `[0x021C07DC]` haven't been worked out.
- Prior art named by the Claude guide (GitHub isn't reachable from here to check): dude22072/PokeStats (Lua, said to have Platinum party offsets), EverOddish/PokeStreamer-Tools (`auto_layout_gen4_gen5.lua`, a Gen IV/V pointer table), JimB16/PokePlat (older Platinum disassembly), kwsch/PKHeX (SAV4/PK4 code).

## 12. Pokémon Black and White: leads not used yet

What `core/bw_parser.py` reads is in DOCUMENTATION.md, section 9. Black US
addresses (White US: add `0x20`); none checked on a console yet.

- **Opponent trainer.** Only its trainer ID is known (`0x022697BE`, u16, 0
  when wild). The class and name live in the ROM's trainer data (thought to
  be NARC `a/0/9/2`), not in RAM as far as anyone has written down; the
  RetroAchievements notes for game 3887 may know a RAM copy, or the trainer
  IDs of the leaders, Elite Four, N and Ghetsis. `overlay/unova_art.py`
  already maps trainer classes to the battle sprites on the trainer sheet.
- **Other battle data.** The battle copies are also at fixed addresses,
  `0x0226D6A4 + i * 0x224`, valid while the text `btl_pokeparam.c` sits at
  `0x0226D68C`. Stat stages are at `+0xFC` (order unknown) and status at
  `+0x20` (a u32 whose encoding isn't known). The foe's party is at
  `0x0226ACF4` (count at `0x0226ACF0`), a second foe party at `0x0226C274`,
  an ally's at `0x0226B7B4`, a wild Pokémon at `0x02259DD8`. The enemy AI's
  chosen move: `[[[0x02269780] + 0xF0] + 0x20] + 0x46` (u8 index).
- **Another battle flag:** u16 `0x021D0798` is `0x2100`/`0x2101` in battle
  and `0x2800` outside (NDS-Ironmon-Tracker).
- **Zone IDs elsewhere:** `0x022592B2` (child) and `0x022592B4` (parent).
- **Facing, another way:** u8 `0x022521FC` (0 up, 1 down, 2 left, 3 right),
  valid when `0x022521EC` is `0xFF`, else scan `0x022521EC + n * 0x100`.
- **Saved position:** map `0x0223512C`, x `0x02235132`, z `0x02235136`, y
  `0x0223513A` (probably only updated on a save or a warp).
- **The boot clock:** date `0x023FFDE8`, time `0x023FFDEC` (the moment the
  game started, not a running clock), so the overlay's time of day comes
  from the PC's clock.
- **RNG states:** PID RNG (u64) `0x02216224`, battle RNG (u64) `0x021F6368`,
  Mersenne Twister `0x02215354`.
- **The game code** is also at `0x023FFE0C` (u32 `0x4F425249` = `IRBO`).
- **Black 2 and White 2** use a base pointer (`[0x02000024]`, party at
  `+0x19728` per NDS-Ironmon-Tracker) instead of fixed addresses.
- **DSi mode** wasn't tested by any source; things allocated on the heap
  (the battle copies) could move there. rpcprobe only runs in DS mode anyway.
