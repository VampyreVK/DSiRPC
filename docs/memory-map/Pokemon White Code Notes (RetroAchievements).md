---
title: "Code Notes - Pokémon White Version"
source: "https://retroachievements.org/codenotes.php?g=16211"
author:
published:
created: 2026-10-08
description: "Adding achievements to retro games since 2012"
tags:
 - "clippings"
---
### Code Notes

![Pokémon White Version (Nintendo DS)](https://media.retroachievements.org/Images/104481.png)

Pokémon White Version (Nintendo DS)

The RetroAchievements addressing scheme for most systems is to access the system memory at address $00000000, immediately followed by the cartridge memory. As such, the addresses displayed below may not directly correspond to the addresses on the real hardware.

There are currently 325 code notes for this game.

| Mem | Note | Author |
| --- | --- | --- |
| 0x000000 | \=== Pokémon Data Layout for Battle Pointers === \--- +0x0C \| Pokémon ID \[16bit\] \--- +0x0E \| Max HP \[16bit\] \--- +0x10 \| Current HP \[16bit\] \--- +0x12 \| Held Item ID \[16bit\] \--- +0x18 \| Level \[8bit\] \--- +0xEE \| Stat - Attack \[16bit\] \--- +0xF0 \| Stat - Defense \[16bit\] \--- +0xF2 \| Stat - Special Attack \[16bit\] \--- +0xF4 \| Stat - Special Defense \[16bit\] \--- +0xF6 \| Stat - Speed \[16bit\] \--- +0xF8 \| Types \[2 Bytes\] \--- 00 \| Normal \--- 01 \| Fight \--- 02 \| Flying \--- 03 \| Poison \--- 04 \| Ground \--- 05 \| Rock \--- 06 \| Bug \--- 07 \| Ghost \--- 08 \| Steel \--- 09 \| Fire \--- 0A \| Water \--- 0B \| Grass \--- 0C \| Electric \--- 0D \| Psychic \--- 0E \| Ice \--- 0F \| Dragon \--- 10 \| Dark \--- +0xFC \| Stat Modifier - Attack \[8bit\] \--- +0xFD \| Stat Modifier - Defense \[8bit\] \--- +0xFE \| Stat Modifier - Special Attack \[8bit\] \--- +0xFF \| Stat Modifier - Special Defense \[8bit\] \--- +0x100 \| Stat Modifier - Speed \[8bit\] \--- +0x101 \| Stat Modifier - Accuracy \[8bit\] \--- +0x102 \| Stat Modifier - Evasiveness \[8bit\] \--- +0x10A \| Move 1 - Move ID \[16bit\] \--- +0x10C \| Move 1 - PP Left \[8bit\] \--- +0x10D \| Move 1 - PP Max \[8bit\] \--- +0x118 \| Move 2 - Move ID \[16bit\] \--- +0x11A \| Move 2 - PP Left \[8bit\] \--- +0x11C \| Move 2 - PP Max \[8bit\] \--- +0x126 \| Move 3 - Move ID \[16bit\] \--- +0x128 \| Move 3 - PP Left \[8bit\] \--- +0x129 \| Move 3 - PP Max \[8bit\] \--- +0x134 \| Move 4 - Move ID \[16bit\] \--- +0x136 \| Move 4 - PP Left \[8bit\] \--- +0x137 \| Move 4 - PP Max \[8bit\] \--- +0x13C \| Ability ID \[16bit\] \--- +0x143 \| Pokémon Attacks this Turn \[8bit\] \--- +0x146 \| Active Turns in a Row \[16bit\] | |
| 0x000034 | 0x01 = In-game (why? don't ask me, every gen 5 set used this) | |
| 0x0000df | \=2 lid closed (if cgear is on) | |
| 0x0aa1d0 | \=1 when the got item fanfare is playing? | |
| 0x0aa2b4 | sound effect? (16 bits) quizz correct = 069a quizz incorrect = 069b vending machine = 0677 | |
| 0x146a3c | Hour | |
| 0x146a40 | Minutes | |
| 0x146a44 | Seconds | |
| 0x146a48 | Year | |
| 0x146a4c | Month | |
| 0x146a50 | Day | |
| 0x146a64 | useful for clean badges? | |
| 0x153028 | \=1 -> =0 lid closed (cgear off) | |
| 0x1f63bc | \[32-bit\] Battle Pointer +0x04 \| Pointer to Data of Player's Pokémon currently in Slot 1 (Graphics) \[32bit\] +0x08 \| Pointer to Data of Player's Pokémon currently in Slot 2 (Graphics) \[32bit\] +0x0C \| Pointer to Data of Player's Pokémon currently in Slot 3 (Graphics) \[32bit\] +0x10 \| Pointer to Data of Player's Pokémon currently in Slot 4 (Graphics) \[32bit\] +0x14 \| Pointer to Data of Player's Pokémon currently in Slot 5 (Graphics) \[32bit\] +0x18 \| Pointer to Data of Player's Pokémon currently in Slot 6 (Graphics) \[32bit\] +0x1C \| Player's Total Pokémon in Party (Graphics) \[32bit\] +0x20 \| Pointer to Data of Opponent's Pokémon currently in Slot 1 (Graphics) \[32bit\] +0x24 \| Pointer to Data of Opponent's Pokémon currently in Slot 2 (Graphics) \[32bit\] +0x28 \| Pointer to Data of Opponent's Pokémon currently in Slot 3 (Graphics) \[32bit\] +0x2C \| Pointer to Data of Opponent's Pokémon currently in Slot 4 (Graphics) \[32bit\] +0x30 \| Pointer to Data of Opponent's Pokémon currently in Slot 5 (Graphics) \[32bit\] +0x34 \| Pointer to Data of Opponent's Pokémon currently in Slot 6 (Graphics) \[32bit\] +0x38 \| Opponent's Total Pokémon in Party (Graphics) \[32bit\] +0x84 \| Pointer to Data of Player's Pokémon initially in Slot 1 (Graphics) \[32bit\] +0x88 \| Pointer to Data of Player's Pokémon initially in Slot 2 (Graphics) \[32bit\] +0x8C \| Pointer to Data of Player's Pokémon initially in Slot 3 (Graphics) \[32bit\] +0x90 \| Pointer to Data of Player's Pokémon initially in Slot 4 (Graphics) \[32bit\] +0x94 \| Pointer to Data of Player's Pokémon initially in Slot 5 (Graphics) \[32bit\] +0x98 \| Pointer to Data of Player's Pokémon initially in Slot 6 (Graphics) \[32bit\] +0xB4 \| Pointer to Data of Opponent's Pokémon initially in Slot 1 (Graphics) \[32bit\] +0xB8 \| Pointer to Data of Opponent's Pokémon initially in Slot 2 (Graphics) \[32bit\] +0xBC \| Pointer to Data of Opponent's Pokémon initially in Slot 3 (Graphics) \[32bit\] +0xC0 \| Pointer to Data of Opponent's Pokémon initially in Slot 4 (Graphics) \[32bit\] +0xC4 \| Pointer to Data of Opponent's Pokémon initially in Slot 5 (Graphics) \[32bit\] +0xC8 \| Pointer to Data of Opponent's Pokémon initially in Slot 6 (Graphics) \[32bit\] +0xEC \| Pointer to Data of Player's Pokémon currently in Slot 1 (real) \[32bit\] +0xF0 \| Pointer to Data of Player's Pokémon currently in Slot 2 (real) \[32bit\] +0xF4 \| Pointer to Data of Player's Pokémon currently in Slot 3 (real) \[32bit\] +0xF8 \| Pointer to Data of Player's Pokémon currently in Slot 4 (real) \[32bit\] +0xFC \| Pointer to Data of Player's Pokémon currently in Slot 5 (real) \[32bit\] +0x100 \| Pointer to Data of Player's Pokémon currently in Slot 6 (real) \[32bit\] +0x104 \| Player's Total Pokémon in Party (real) \[32bit\] +0x108 \| Pointer to Data of Opponent's Pokémon currently in Slot 1 (real) \[32bit\] +0x10C \| Pointer to Data of Opponent's Pokémon currently in Slot 2 (real) \[32bit\] +0x110 \| Pointer to Data of Opponent's Pokémon currently in Slot 3 (real) \[32bit\] +0x114 \| Pointer to Data of Opponent's Pokémon currently in Slot 4 (real) \[32bit\] +0x118 \| Pointer to Data of Opponent's Pokémon currently in Slot 5 (real) \[32bit\] +0x11C \| Pointer to Data of Opponent's Pokémon currently in Slot 6 (real) \[32bit\] +0x120 \| Opponent's Total Pokémon in Party (real) \[32bit\] +0x16C \| Pointer to Data of Player's Pokémon initially in Slot 1 (real) \[32bit\] +0x170 \| Pointer to Data of Player's Pokémon initially in Slot 2 (real) \[32bit\] +0x174 \| Pointer to Data of Player's Pokémon initially in Slot 3 (real) \[32bit\] +0x178 \| Pointer to Data of Player's Pokémon initially in Slot 4 (real) \[32bit\] +0x17C \| Pointer to Data of Player's Pokémon initially in Slot 5 (real) \[32bit\] +0x180 \| Pointer to Data of Player's Pokémon initially in Slot 6 (real) \[32bit\] +0x19C \| Pointer to Data of Opponent's Pokémon initially in Slot 1 (real) \[32bit\] +0x1A0 \| Pointer to Data of Opponent's Pokémon initially in Slot 2 (real) \[32bit\] +0x1A4 \| Pointer to Data of Opponent's Pokémon initially in Slot 3 (real) \[32bit\] +0x1A8 \| Pointer to Data of Opponent's Pokémon initially in Slot 4 (real) \[32bit\] +0x1AC \| Pointer to Data of Opponent's Pokémon initially in Slot 5 (real) \[32bit\] +0x1B0 \| Pointer to Data of Opponent's Pokémon initially in Slot 6 (real) \[32bit\] | |
| 0x233fcc | Bag - Items \[1240 Bytes; 32bit per Item\] +00 \| Item ID (16bit) +02 \| Amount (16bit) | |
| 0x2344a4 | Bag - Key Items \[332 Bytes; 32bit per Item\] +00 \| Item ID (16bit) +02 \| Amount (16bit) | |
| 0x2345f0 | Bag - TMs & HMs \[436 Bytes; 32bit per Item\] +00 \| Item ID (16bit) +02 \| Amount (16bit) | |
| 0x2347a4 | Bag - Medicine \[192 Bytes; 32bit per Item\] +00 \| Item ID (16bit) +02 \| Amount (16bit) | |
| 0x234864 | Bag - Berries \[296 Bytes; 32bit per Item\] +00 \| Item ID (16bit) +02 \| Amount (16bit) | |
| 0x2349d0 | number of pokemon in the party | |
| 0x234fcc | b4=sound mono b6=battle style set | |
| 0x238304 | badge 1 shine (static) (16 bit) | |
| 0x2394ec | day of the week: 00=sunday 01=monday 06=saturday | |
| 0x23b2d0 | first poke id (musical photo) | |
| 0x23b328 | 2nd poke id (musical photo) | |
| 0x23b380 | 3rd poke id (musical photo) | |
| 0x23b3d8 | 4th poke id (musical photo) | |
| 0x23b520 | number of times you have won in the musical | |
| 0x23b524 | Props: b0, b1 b4=crimson scarf b6=big barrette b7=headband | |
| 0x23b525 | b0,b2 | |
| 0x23b526 | b0 | |
| 0x23b527 | b0=toy cake b4 | |
| 0x23b52a | b0 | |
| 0x23b52b | b3,b7 | |
| 0x23b52c | b2,b6 b3=tiara (unobtainable without multiplayer) | |
| 0x23b52d | b3,b4 b1=tambourine b2=fedora | |
| 0x23b52e | b3 b4=electric guitar | |
| 0x23b52f | b1 b7=scarlet hat | |
| 0x23b530 | b0=big bag b2=fluffy beard b3=gift box | |
| 0x23bcd0 | b2=deerling winter form showed in the lab | |
| 0x23bdcc | \=3 after the first step on route 1 | |
| 0x23bdd2 | \=1 elemental monkey not obtained \=2 elemental monkey obtained | |
| 0x23bdea | b0=bianca after 5th gym gives hm02 | |
| 0x23be48 | b0=TM70 | |
| 0x23be4a | casteliacone is sold out | |
| 0x23be58 | b0=TM56 | |
| 0x23be64 | looker side quest (changes from 5 to 6 at the end) | |
| 0x23be80 | b0=munchlax in game trade | |
| 0x23be86 | b0=abyssal ruins floor 2 unlocked | |
| 0x23be88 | b0=abyssal ruins floor 3 unlocked | |
| 0x23be8a | b0=abyssal ruins floor 4 unlocked | |
| 0x23be92 | 1->2: charles defeated | |
| 0x23be94 | 0 -> 2 = cynthia talks to you and battles (you win) 1 -> 2 = 1 happens if you lost or if you refused to battle, 2 when you win | |
| 0x23be98 | \=1 ghost in marvelous bridge \=2 disappears | |
| 0x23bf58 | b5=TM57 b6=ragecandybar (icirrus city) b7=TM31 | |
| 0x23bf5a | b0=sharp beak (mistralton city) b1=obtain cover or plume fossil b4=cottonee in game trade | |
| 0x23bf5c | b3=janitor geoff (exp share) | |
| 0x23bf5d | b6=tm10 b7=tm54 | |
| 0x23bf5e | b0=tm17 | |
| 0x23bf66 | b0=Details about People b1=Pokemon Favorites b2=Ideals and Values b3=Likable People b4=Preferences b5=Entertainment b6=School Life b7=Sports and Pastimes | |
| 0x23bf67 | b0=More about Pokemon b3=exp share (pokemon fan club) b4=cleanse tag (pokemon fan club) b5=kings rock (pokemon fan club) | |
| 0x23bf68 | b2=TM42 b4=TM43 | |
| 0x23bf69 | b1=TM44 b3=TM49 b6=TM45 b7=TM94 | |
| 0x23bf6a | b0=TM28 b4=soft sand (desert) | |
| 0x23bf6b | b0=basculin in game trade b6=game in progress (stadium or course) | |
| 0x23bf6c | b2=HM04 | |
| 0x23bf6d | b5=miracle seed, mystic water or charcoal in nacrene city | |
| 0x23bf6f | b3=obtain larvesta egg b7=gram 3 | |
| 0x23bf70 | b0=gram 1 | |
| 0x23bf71 | b3=wallpapers1 unlocked b4=wallpapers2 unlocked b7=white forest triple battle | |
| 0x23bf72 | b0=white forest triple battle b3=buy magikarp | |
| 0x23bf73 | b2=HM06 b3=emolga in game trade b6=season lab side quest | |
| 0x23bf74 | b1=cheren (victory road) b4=splash and draco plates b7=prism scale (undella town) | |
| 0x23bf75 | b0=rotom in game trade b5=expert belt (driftveil) b7=macho brace (nimbasa gate) | |
| 0x23bf90 | b6=TM78 | |
| 0x23bf9a | b2=HM03 b4=defeat N at N's Castle b7=zen darmanitan (middle left) | |
| 0x23bf9b | b0=zen darmanitan (down left) b1=zen darmanitan (top left) b2=zen darmanitan (down right) b3=zen darmanitan (top right) b4 1->0=TM40, 0->1=event ends | |
| 0x23bfa0 | b1=TM08 and sage Giallo b2=TM69 and sage Bronius b3=TM75 and sage Gorm b4=TM21 and sage Rood | |
| 0x23bfa1 | b4=TM01 and sage Zinzolin | |
| 0x23bfa7 | b2=TM89 b3=gram 2 | |
| 0x23bfad | b1=TM04 and sage ryoky b3=0: show deerling spring form b4=0: show deerling summer form b5=0: show deerling autumn form b6=0: show deerling winter form in the lab b7=cheren goes to victory road | |
| 0x23bfb0 | b3=0, b4=1, b5=0: girl in village bridge runs away | |
| 0x23bfd4 | b3=TM12 b5=TM93 | |
| 0x23bfd5 | b0=silverpowder (pinwheel forest) b3=TM86 b4=TM22 | |
| 0x23bfd6 | b4=magnet (chargestone cave) | |
| 0x23bfd9 | b4=TM30 b7=TM55 | |
| 0x23bfda | b2=silk scarf (route 6) b5=TM26 | |
| 0x23bfdb | b0=TM81 b6=metal coat (twist mountain) b7=TM91 | |
| 0x23bfdc | b0=TM63 b1=poison barb (route 8) b5=TM05 | |
| 0x23bfdd | b6=TM02 | |
| 0x23bfde | b0=prism scale (route 13) b2=TM50 b3=protector (route 11) b5=TM53 | |
| 0x23bfdf | b0=deepseascale (route 13) b1=razor claw (route 13) b2=TM29 b5=reaper cloth (route 14) b7=up-grade (route 15) | |
| 0x23bfe0 | b0=TM09 b2=TM66 b4=TM06 b5=deepseatooth (route 17) b6=TM24 b7=TM19 | |
| 0x23bfe1 | b0=dragon scale (route 18) b2=HM05 b3=TM61 b5=spell tag (celestial tower) | |
| 0x23bfe2 | b2=TM84 b6=TM46 | |
| 0x23bfe3 | b1=TM52 b3=mystic water (wellspring cave) b5=TM47 b7=miracle seed (pinwheel forest) | |
| 0x23bfe4 | b2=TM41 b3=black glasses (desert) b4=TM39 | |
| 0x23bfe5 | b1=TM80 b3=hard stone (mistral cave) b7=TM58 | |
| 0x23bfe6 | b0=TM65 b2=TM90 b4=TM36 | |
| 0x23bfe7 | b1=TM71 b2=oval stone (challenger cave) b4=black belt (challenger cave) | |
| 0x23bfe8 | b6=flame plate b7=zap plate | |
| 0x23bfe9 | b0=meadow plate b1=relic silver b2=fist plate b3=toxic plate b4=relic vase b5=sky plate b6=mind plate b7=insect plate | |
| 0x23bfea | b0=stone plate b1=icicle plate b2=dread plate b3=iron plate b4=relic copper b5=relic copper b6=relic copper | |
| 0x23bfeb | b0=relic copper b1=relic silver b2=relic silver b4=earth plate b5=spooky plate b6=relic gold | |
| 0x23bfec | b0=relic gold b1=relic gold b4=relic statue b6=relic copper (2f) b7=relic copper (2f) | |
| 0x23bfed | b0=relic silver (2f) b1=relic silver (2f) b3=relic gold (2f) b4=relic gold (2f) b5=relic gold (2f) b7=relic vase (2f) | |
| 0x23bfee | b1=relic band (2f) b2=relic band (2f) | |
| 0x23bff2 | b1=relic statue (2f) b3=relic silver (3f) b4=relic gold (3f) b5=relic vase (3f) b7=relic vase (3f) | |
| 0x23bff3 | b0=relic band (3f) b1=relic band (3f) b2=relic band (3f) b3=relic statue (3f) b4=relic crown (4f) b7=TM13 | |
| 0x23bff4 | b2=TM03 b5=electirizer (route 13) b6=TM92 | |
| 0x23bff5 | b2=razor fang (abundant shrine) b3=TM35 | |
| 0x23bff6 | b0=dubious disc (p2 labo) b1=charcoal (route 16) | |
| 0x23bff7 | b0=nevermeltice (cold storage) b6=TM85 b7=twistedspoon (dreamyard) | |
| 0x23bff8 | b3=dragon fang (dracospiral tower) | |
| 0x23c039 | b6=ace trainer lou | |
| 0x23c045 | b0=ace trainer elleen b2=ace trainer elmer b5=ace trainer glinda (rematch daily?) | |
| 0x23c075 | b4-b1=elite four defeated | |
| 0x23c09d | b5=harlequin in castelia gives a berry daily | |
| 0x23c09e | b3=move lover asks for a move b4=reward obtained b5=quiz in icirrus city b6=treasure hunter (route 13) b7=defeat morimoto | |
| 0x23c09f | b5=joined the fishing club in village bridge | |
| 0x23c0a0 | b3=hired on the village bridge restaurant b4=cheren in victory road b6=defeated bianca in nuvema town b7=defeated cynthia in spring (comes with b3 of the next address) | |
| 0x23c0a1 | b1=daily patrat minigame b2=daily fossil collected b3=talk to cynthia in spring (rematch) | |
| 0x23cdcc | money (24 bits) | |
| 0x23cdd0 | \- Badges Bit 0 = Trio Badge Bit 1 = Basic Badge Bit 2 = Insect Badge Bit 3 = Bolt Badge Bit 4 = Quake Badge Bit 5 = Jet Badge Bit 6 = Freeze Badge Bit 7 = Legend Badge | |
| 0x23ce11 | b6=relocator unlocked | |
| 0x23d1d0 | \[8-bit\] Pokedex Bit 0 = National Upgrade Bit 1 = Forms Update | |
| 0x23d1d4 | Bit 0 = Bulbasaur Bit 1 = Ivysaur Bit 2 = Venusaur Bit 3 = Charmander Bit 4 = Charmeleon Bit 5 = Charizard Bit 6 = Squirtle Bit 7 = Wartortle | |
| 0x23d1d5 | Bit 0 = Blastoise Bit 1 = Caterpie Bit 2 = Metapod Bit 3 = Butterfree Bit 4 = Weedle Bit 5 = Kakuna Bit 6 = Beedrill Bit 7 = Pidgey | |
| 0x23d1d6 | Bit 0 = Pidgeotto Bit 1 = Pidgeot Bit 2 = Rattata Bit 3 = Raticate Bit 4 = Spearow Bit 5 = Fearow Bit 6 = Ekans Bit 7 = Arbok | |
| 0x23d1d7 | Bit 0 = Pikachu Bit 1 = Raichu Bit 2 = Sandshrew Bit 3 = Sandslash Bit 4 = Nidoran♀ Bit 5 = Nidorina Bit 6 = Nidoqueen Bit 7 = Nidoran♂ | |
| 0x23d1d8 | Bit 0 = Nidorino Bit 1 = Nidoking Bit 2 = Clefairy Bit 3 = Clefable Bit 4 = Vulpix Bit 5 = Ninetales Bit 6 = Jigglypuff Bit 7 = Wigglytuff | |
| 0x23d1d9 | Bit 0 = Zubat Bit 1 = Golbat Bit 2 = Oddish Bit 3 = Gloom Bit 4 = Vileplume Bit 5 = Paras Bit 6 = Parasect Bit 7 = Venonat | |
| 0x23d1da | Bit 0 = Venomoth Bit 1 = Diglett Bit 2 = Dugtrio Bit 3 = Meowth Bit 4 = Persian Bit 5 = Psyduck Bit 6 = Golduck Bit 7 = Mankey | |
| 0x23d1db | Bit 0 = Primeape Bit 1 = Growlithe Bit 2 = Arcanine Bit 3 = Poliwag Bit 4 = Poliwhirl Bit 5 = Poliwrath Bit 6 = Abra Bit 7 = Kadabra | |
| 0x23d1dc | Bit 0 = Alakazam Bit 1 = Machop Bit 2 = Machoke Bit 3 = Machamp Bit 4 = Bellsprout Bit 5 = Weepinbell Bit 6 = Victreebel Bit 7 = Tentacool | |
| 0x23d1dd | Bit 0 = Tentacruel Bit 1 = Geodude Bit 2 = Graveler Bit 3 = Golem Bit 4 = Ponyta Bit 5 = Rapidash Bit 6 = Slowpoke Bit 7 = Slowbro | |
| 0x23d1de | Bit 0 = Magnemite Bit 1 = Magneton Bit 2 = Farfetch'd Bit 3 = Doduo Bit 4 = Dodrio Bit 5 = Seel Bit 6 = Dewgong Bit 7 = Grimer | |
| 0x23d1df | Bit 0 = Muk Bit 1 = Shellder Bit 2 = Cloyster Bit 3 = Gastly Bit 4 = Haunter Bit 5 = Gengar Bit 6 = Onix Bit 7 = Drowzee | |
| 0x23d1e0 | Bit 0 = Hypno Bit 1 = Krabby Bit 2 = Kingler Bit 3 = Voltorb Bit 4 = Electrode Bit 5 = Exeggcute Bit 6 = Exeggutor Bit 7 = Cubone | |
| 0x23d1e1 | Bit 0 = Marowak Bit 1 = Hitmonlee Bit 2 = Hitmonchan Bit 3 = Lickitung Bit 4 = Koffing Bit 5 = Weezing Bit 6 = Rhyhorn Bit 7 = Rhydon | |
| 0x23d1e2 | Bit 0 = Chansey Bit 1 = Tangela Bit 2 = Kangaskhan Bit 3 = Horsea Bit 4 = Seadra Bit 5 = Goldeen Bit 6 = Seaking Bit 7 = Staryu | |
| 0x23d1e3 | Bit 0 = Starmie Bit 1 = Mr. Mime Bit 2 = Scyther Bit 3 = Jynx Bit 4 = Electabuzz Bit 5 = Magmar Bit 6 = Pinsir Bit 7 = Tauros | |
| 0x23d1e4 | Bit 0 = Magikarp Bit 1 = Gyarados Bit 2 = Lapras Bit 3 = Ditto Bit 4 = Eevee Bit 5 = Vaporeon Bit 6 = Jolteon Bit 7 = Flareon | |
| 0x23d1e5 | Bit 0 = Porygon Bit 1 = Omanyte Bit 2 = Omastar Bit 3 = Kabuto Bit 4 = Kabutops Bit 5 = Aerodactyl Bit 6 = Snorlax Bit 7 = Articuno | |
| 0x23d1e6 | Bit 0 = Zapdos Bit 1 = Moltres Bit 2 = Dratini Bit 3 = Dragonair Bit 4 = Dragonite Bit 5 = Mewtwo Bit 6 = Mew Bit 7 = Chikorita | |
| 0x23d1e7 | Bit 0 = Bayleef Bit 1 = Meganium Bit 2 = Cyndaquil Bit 3 = Quilava Bit 4 = Typhlosion Bit 5 = Totodile Bit 6 = Croconaw Bit 7 = Feraligatr | |
| 0x23d1e8 | Bit 0 = Sentret Bit 1 = Furret Bit 2 = Hoothoot Bit 3 = Noctowl Bit 4 = Ledyba Bit 5 = Ledian Bit 6 = Spinarak Bit 7 = Ariados | |
| 0x23d1e9 | Bit 0 = Crobat Bit 1 = Chinchou Bit 2 = Lanturn Bit 3 = Pichu Bit 4 = Cleffa Bit 5 = Igglybuff Bit 6 = Togepi Bit 7 = Togetic | |
| 0x23d1ea | Bit 0 = Natu Bit 1 = Xatu Bit 2 = Mareep Bit 3 = Flaaffy Bit 4 = Ampharos Bit 5 = Bellossom Bit 6 = Marill Bit 7 = Azumarill | |
| 0x23d1eb | Bit 0 = Sudowoodo Bit 1 = Politoed Bit 2 = Hoppip Bit 3 = Skiploom Bit 4 = Jumpluff Bit 5 = Aipom Bit 6 = Sunkern Bit 7 = Sunflora | |
| 0x23d1ec | Bit 0 = Yanma Bit 1 = Wooper Bit 2 = Quagsire Bit 3 = Espeon Bit 4 = Umbreon Bit 5 = Murkrow Bit 6 = Slowking Bit 7 = Misdreavus | |
| 0x23d1ed | Bit 0 = Unown Bit 1 = Wobbuffet Bit 2 = Girafarig Bit 3 = Pineco Bit 4 = Forretress Bit 5 = Dunsparce Bit 6 = Gligar Bit 7 = Steelix | |
| 0x23d1ee | Bit 0 = Snubbull Bit 1 = Granbull Bit 2 = Qwilfish Bit 3 = Scizor Bit 4 = Shuckle Bit 5 = Heracross Bit 6 = Sneasel Bit 7 = Teddiursa | |
| 0x23d1ef | Bit 0 = Ursaring Bit 1 = Slugma Bit 2 = Magcargo Bit 3 = Swinub Bit 4 = Piloswine Bit 5 = Corsola Bit 6 = Remoraid Bit 7 = Octillery | |
| 0x23d1f0 | Bit 0 = Delibird Bit 1 = Mantine Bit 2 = Skarmory Bit 3 = Houndour Bit 4 = Houndoom Bit 5 = Kingdra Bit 6 = Phanpy Bit 7 = Donphan | |
| 0x23d1f1 | Bit 0 = Porygon2 Bit 1 = Stantler Bit 2 = Smeargle Bit 3 = Tyrogue Bit 4 = Hitmontop Bit 5 = Smoochum Bit 6 = Elekid Bit 7 = Magby | |
| 0x23d1f2 | Bit 0 = Miltank Bit 1 = Blissey Bit 2 = Raikou Bit 3 = Entei Bit 4 = Suicune Bit 5 = Larvitar Bit 6 = Pupitar Bit 7 = Tyranitar | |
| 0x23d1f3 | Bit 0 = Lugia Bit 1 = Ho-oh Bit 2 = Celebi Bit 3 = Treecko Bit 4 = Grovyle Bit 5 = Sceptile Bit 6 = Torchic Bit 7 = Combusken | |
| 0x23d1f4 | Bit 0 = Blaziken Bit 1 = Mudkip Bit 2 = Marshtomp Bit 3 = Swampert Bit 4 = Poochyena Bit 5 = Mightyena Bit 6 = Zigzagoon Bit 7 = Linoone | |
| 0x23d1f5 | Bit 0 = Wurmple Bit 1 = Silcoon Bit 2 = Beautifly Bit 3 = Cascoon Bit 4 = Dustox Bit 5 = Lotad Bit 6 = Lombre Bit 7 = Ludicolo | |
| 0x23d1f6 | Bit 0 = Seedot Bit 1 = Nuzleaf Bit 2 = Shiftry Bit 3 = Taillow Bit 4 = Swellow Bit 5 = Wingull Bit 6 = Pelipper Bit 7 = Ralts | |
| 0x23d1f7 | Bit 0 = Kirlia Bit 1 = Gardevoir Bit 2 = Surskit Bit 3 = Masquerain Bit 4 = Shroomish Bit 5 = Breloom Bit 6 = Slakoth Bit 7 = Vigoroth | |
| 0x23d1f8 | Bit 0 = Slaking Bit 1 = Nincada Bit 2 = Ninjask Bit 3 = Shedinja Bit 4 = Whismur Bit 5 = Loudred Bit 6 = Exploud Bit 7 = Makuhita | |
| 0x23d1f9 | Bit 0 = Hariyama Bit 1 = Azurill Bit 2 = Nosepass Bit 3 = Skitty Bit 4 = Delcatty Bit 5 = Sableye Bit 6 = Mawile Bit 7 = Aron | |
| 0x23d1fa | Bit 0 = Lairon Bit 1 = Aggron Bit 2 = Meditite Bit 3 = Medicham Bit 4 = Electrike Bit 5 = Manectric Bit 6 = Plusle Bit 7 = Minun | |
| 0x23d1fb | Bit 0 = Volbeat Bit 1 = Illumise Bit 2 = Roselia Bit 3 = Gulpin Bit 4 = Swalot Bit 5 = Carvanha Bit 6 = Sharpedo Bit 7 = Wailmer | |
| 0x23d1fc | Bit 0 = Wailord Bit 1 = Numel Bit 2 = Camerupt Bit 3 = Torkoal Bit 4 = Spoink Bit 5 = Grumpig Bit 6 = Spinda Bit 7 = Trapinch | |
| 0x23d1fd | Bit 0 = Vibrava Bit 1 = Flygon Bit 2 = Cacnea Bit 3 = Cacturne Bit 4 = Swablu Bit 5 = Altaria Bit 6 = Zangoose Bit 7 = Seviper | |
| 0x23d1fe | Bit 0 = Lunatone Bit 1 = Solrock Bit 2 = Barboach Bit 3 = Whiscash Bit 4 = Corphish Bit 5 = Crawdaunt Bit 6 = Baltoy Bit 7 = Claydol | |
| 0x23d1ff | Bit 0 = Lileep Bit 1 = Cradily Bit 2 = Anorith Bit 3 = Armaldo Bit 4 = Feebas Bit 5 = Milotic Bit 6 = Castform Bit 7 = Kecleon | |
| 0x23d200 | Bit 0 = Shuppet Bit 1 = Banette Bit 2 = Duskull Bit 3 = Dusclops Bit 4 = Tropius Bit 5 = Chimecho Bit 6 = Absol Bit 7 = Wynaut | |
| 0x23d201 | Bit 0 = Snorunt Bit 1 = Glalie Bit 2 = Spheal Bit 3 = Sealeo Bit 4 = Walrein Bit 5 = Clamperl Bit 6 = Huntail Bit 7 = Gorebyss | |
| 0x23d202 | Bit 0 = Relicanth Bit 1 = Luvdisc Bit 2 = Bagon Bit 3 = Shelgon Bit 4 = Salamence Bit 5 = Beldum Bit 6 = Metang Bit 7 = Metagross | |
| 0x23d203 | Bit 0 = Regirock Bit 1 = Regice Bit 2 = Registeel Bit 3 = Latias Bit 4 = Latios Bit 5 = Kyogre Bit 6 = Groudon Bit 7 = Rayquaza | |
| 0x23d204 | Bit 0 = Jirachi Bit 1 = Deoxys Bit 2 = Turtwig Bit 3 = Grotle Bit 4 = Torterra Bit 5 = Chimchar Bit 6 = Monferno Bit 7 = Infernape | |
| 0x23d205 | Bit 0 = Piplup Bit 1 = Prinplup Bit 2 = Empoleon Bit 3 = Starly Bit 4 = Staravia Bit 5 = Staraptor Bit 6 = Bidoof Bit 7 = Bibarel | |
| 0x23d206 | Bit 0 = Kricketot Bit 1 = Kricketune Bit 2 = Shinx Bit 3 = Luxio Bit 4 = Luxray Bit 5 = Budew Bit 6 = Roserade Bit 7 = Cranidos | |
| 0x23d207 | Bit 0 = Rampardos Bit 1 = Shieldon Bit 2 = Bastiodon Bit 3 = Burmy Bit 4 = Wormadam Bit 5 = Mothim Bit 6 = Combee Bit 7 = Vespiquen | |
| 0x23d208 | Bit 0 = Pachirisu Bit 1 = Buizel Bit 2 = Floatzel Bit 3 = Cherubi Bit 4 = Cherrim Bit 5 = Shellos Bit 6 = Gastrodon Bit 7 = Ambipom | |
| 0x23d209 | Bit 0 = Drifloon Bit 1 = Drifblim Bit 2 = Buneary Bit 3 = Lopunny Bit 4 = Mismagius Bit 5 = Honchkrow Bit 6 = Glameow Bit 7 = Purugly | |
| 0x23d20a | Bit 0 = Chingling Bit 1 = Stunky Bit 2 = Skuntank Bit 3 = Bronzor Bit 4 = Bronzong Bit 5 = Bonsly Bit 6 = Mime Jr. Bit 7 = Happiny | |
| 0x23d20b | Bit 0 = Chatot Bit 1 = Spiritomb Bit 2 = Gible Bit 3 = Gabite Bit 4 = Garchomp Bit 5 = Munchlax Bit 6 = Riolu Bit 7 = Lucario | |
| 0x23d20c | Bit 0 = Hippopotas Bit 1 = Hippowdon Bit 2 = Skorupi Bit 3 = Drapion Bit 4 = Croagunk Bit 5 = Toxicroak Bit 6 = Carnivine Bit 7 = Finneon | |
| 0x23d20d | Bit 0 = Lumineon Bit 1 = Mantyke Bit 2 = Snover Bit 3 = Abomasnow Bit 4 = Weavile Bit 5 = Magnezone Bit 6 = Lickilicky Bit 7 = Rhyperior | |
| 0x23d20e | Bit 0 = Tangrowth Bit 1 = Electivire Bit 2 = Magmortar Bit 3 = Togekiss Bit 4 = Yanmega Bit 5 = Leafeon Bit 6 = Glaceon Bit 7 = Gliscor | |
| 0x23d20f | Bit 0 = Mamoswine Bit 1 = Porygon-Z Bit 2 = Gallade Bit 3 = Probopass Bit 4 = Dusknoir Bit 5 = Froslass Bit 6 = Rotom Bit 7 = Uxie | |
| 0x23d210 | Bit 0 = Mesprit Bit 1 = Azelf Bit 2 = Dialga Bit 3 = Palkia Bit 4 = Heatran Bit 5 = Regigigas Bit 6 = Giratina Bit 7 = Cresselia | |
| 0x23d211 | Bit 0 = Phione Bit 1 = Manaphy Bit 2 = Darkrai Bit 3 = Shaymin Bit 4 = Arceus Bit 5 = Victini Bit 6 = Snivy Bit 7 = Servine | |
| 0x23d212 | Bit 0 = Serperior Bit 1 = Tepig Bit 2 = Pignite Bit 3 = Emboar Bit 4 = Oshawott Bit 5 = Dewott Bit 6 = Samurott Bit 7 = Patrat | |
| 0x23d213 | Bit 0 = Watchog Bit 1 = Lillipup Bit 2 = Herdier Bit 3 = Stoutland Bit 4 = Purrloin Bit 5 = Liepard Bit 6 = Pansage Bit 7 = Simisage | |
| 0x23d214 | Bit 0 = Pansear Bit 1 = Simisear Bit 2 = Panpour Bit 3 = Simipour Bit 4 = Munna Bit 5 = Musharna Bit 6 = Pidove Bit 7 = Tranquill | |
| 0x23d215 | Bit 0 = Unfezant Bit 1 = Blitzle Bit 2 = Zebstrika Bit 3 = Roggenrola Bit 4 = Boldore Bit 5 = Gigalith Bit 6 = Woobat Bit 7 = Swoobat | |
| 0x23d216 | Bit 0 = Drilbur Bit 1 = Excadrill Bit 2 = Audino Bit 3 = Timburr Bit 4 = Gurdurr Bit 5 = Conkeldurr Bit 6 = Tympole Bit 7 = Palpitoad | |
| 0x23d217 | Bit 0 = Seismitoad Bit 1 = Throh Bit 2 = Sawk Bit 3 = Sewaddle Bit 4 = Swadloon Bit 5 = Leavanny Bit 6 = Venipede Bit 7 = Whirlipede | |
| 0x23d218 | Bit 0 = Scolipede Bit 1 = Cottonee Bit 2 = Whimsicott Bit 3 = Petilil Bit 4 = Lilligant Bit 5 = Basculin Bit 6 = Sandile Bit 7 = Krokorok | |
| 0x23d219 | Bit 0 = Krookodile Bit 1 = Darumaka Bit 2 = Darmanitan Bit 3 = Maractus Bit 4 = Dwebble Bit 5 = Crustle Bit 6 = Scraggy Bit 7 = Scrafty | |
| 0x23d21a | Bit 0 = Sigilyph Bit 1 = Yamask Bit 2 = Cofagrigus Bit 3 = Tirtouga Bit 4 = Carracosta Bit 5 = Archen Bit 6 = Archeops Bit 7 = Trubbish | |
| 0x23d21b | Bit 0 = Garbodor Bit 1 = Zorua Bit 2 = Zoroark Bit 3 = Minccino Bit 4 = Cinccino Bit 5 = Gothita Bit 6 = Gothorita Bit 7 = Gothitelle | |
| 0x23d21c | Bit 0 = Solosis Bit 1 = Duosion Bit 2 = Reuniclus Bit 3 = Ducklett Bit 4 = Swanna Bit 5 = Vanillite Bit 6 = Vanillish Bit 7 = Vanilluxe | |
| 0x23d21d | Bit 0 = Deerling Bit 1 = Sawsbuck Bit 2 = Emolga Bit 3 = Karrablast Bit 4 = Escavalier Bit 5 = Foongus Bit 6 = Amoonguss Bit 7 = Frillish | |
| 0x23d21e | Bit 0 = Jellicent Bit 1 = Alomomola Bit 2 = Joltik Bit 3 = Galvantula Bit 4 = Ferroseed Bit 5 = Ferrothorn Bit 6 = Klink Bit 7 = Klang | |
| 0x23d21f | Bit 0 = Klinklang Bit 1 = Tynamo Bit 2 = Eelektrik Bit 3 = Eelektross Bit 4 = Elgyem Bit 5 = Beheeyem Bit 6 = Litwick Bit 7 = Lampent | |
| 0x23d220 | Bit 0 = Chandelure Bit 1 = Axew Bit 2 = Fraxure Bit 3 = Haxorus Bit 4 = Cubchoo Bit 5 = Beartic Bit 6 = Cryogonal Bit 7 = Shelmet | |
| 0x23d221 | Bit 0 = Accelgor Bit 1 = Stunfisk Bit 2 = Mienfoo Bit 3 = Mienshao Bit 4 = Druddigon Bit 5 = Golett Bit 6 = Golurk Bit 7 = Pawniard | |
| 0x23d222 | Bit 0 = Bisharp Bit 1 = Bouffalant Bit 2 = Rufflet Bit 3 = Braviary Bit 4 = Vullaby Bit 5 = Mandibuzz Bit 6 = Heatmor Bit 7 = Durant | |
| 0x23d223 | Bit 0 = Deino Bit 1 = Zweilous Bit 2 = Hydreigon Bit 3 = Larvesta Bit 4 = Volcarona Bit 5 = Cobalion Bit 6 = Terrakion Bit 7 = Virizion | |
| 0x23d224 | Bit 0 = Tornadus Bit 1 = Thundurus Bit 2 = Reshiram Bit 3 = Zekrom Bit 4 = Landorus Bit 5 = Kyurem Bit 6 = Keldeo Bit 7 = Meloetta | |
| 0x23d225 | Bit 0 = Genesect Bit 1 = Bit 2 = Bit 3 = Bit 4 = Bit 5 = Bit 6 = Bit 7 = | |
| 0x23d26f | b1=zorua seen | |
| 0x23d6fd | repel steps | |
| 0x23d8cc | number of BP (16 bit) | |
| 0x23d8d4 | single train current streak | |
| 0x23d8d6 | double train current streak | |
| 0x23d8d8 | multi train with trainer current streak | |
| 0x23d8da | multi train with friend current streak | |
| 0x23d8de | super single train current streak | |
| 0x23d8e0 | super double train current streak | |
| 0x23d8e2 | super multi train with trainer current streak | |
| 0x23d8e6 | single train record streak | |
| 0x23d8e8 | double train record streak | |
| 0x23d8ea | multi train with trainer record streak | |
| 0x23d8ec | multi train with friend record streak | |
| 0x23d8f0 | super single train record streak | |
| 0x23d8f2 | super double train record streak | |
| 0x23d8f4 | super multi train with trainer record streak | |
| 0x23d8f8 | Current streak of 7 battles (single) \=1 for battles 1-7 \=2 for battles 8-14 \=3 for battles 15-21 | |
| 0x23d8fa | Current streak of 7 battles (double) | |
| 0x23d8fc | current streak of 7 battles (multi) | |
| 0x23d902 | Current streak of 7 battles (super single) | |
| 0x23d904 | Current streak of 7 battles (super double) | |
| 0x23d906 | Current streak of 7 battles (super multi) | |
| 0x23f5ce | result of the last test (points) (16 bit) | |
| 0x23f5d0 | last result pokemon 1 | |
| 0x23f5d4 | last result pokemon 2 | |
| 0x23f5d8 | last result pokemon 3 | |
| 0x23f5dc | last result pokemon 4 | |
| 0x24f92c | \[16-bit\] Map ID \[On the save file\] | |
| 0x24f932 | x coordinate (16 bit) | |
| 0x24f93a | y coordinate (16 bit) | |
| 0x24f94c | Name letter 1 (16bit) | |
| 0x24f958 | Name letter 7 (16bit) | |
| 0x24f95c | TID (16bit) | |
| 0x24f95e | SID (16bit) | |
| 0x24f964 | registered location (16 bit) | |
| 0x24f969 | gender 00=boy 01=girl | |
| 0x24f9dc | Season 00=spring 01=summer 02=autumn 03=winter | |
| 0x24f9dd | Weather 00=clear 01=snow 02=rain 03=sandstorm 04=heavy snow 05=hail 06=torrential rain 07=heavy rain 08=diamond dust 09=fog | |
| 0x24fc1c | white forest resident id (16 bit) | |
| 0x24fc34 | white forest resident id (16 bit) | |
| 0x24fc4c | white forest resident id (16 bit) | |
| 0x24fc64 | white forest resident id (16 bit) | |
| 0x24fc7c | white forest resident id (16 bit) | |
| 0x24fc94 | white forest resident id (16 bit) | |
| 0x24fcac | white forest resident id (16 bit) | |
| 0x24fcc4 | white forest resident id (16 bit) | |
| 0x24fcdc | white forest resident id (16 bit) | |
| 0x24fcde | value | |
| 0x24fcdf | \=5 if you haven't talked yet | |
| 0x24fcf4 | white forest resident id (16 bit) (last active slot) | |
| 0x24fd0c | white forest resident id (16 bit) | |
| 0x24fd0e | \=0 when this is 0 theyre gone | |
| 0x24fd0f | residents who left have =7 here? | |
| 0x24fd24 | white forest resident id (16 bit) | |
| 0x24fd3c | white forest resident id (16 bit) | |
| 0x24fd54 | white forest resident id (16 bit) | |
| 0x2567a4 | currently used item in battle | |
| 0x2569c4 | first letter of the first friend on the pal pad (16 bit) | |
| 0x256f94 | first letter of the last friend on the pal pad | |
| 0x258250 | \[16-bit\] Music ID | |
| 0x258bc4 | b0 set to 0=village bridge whistle | |
| 0x258bfc | b0 set to 0=village bridge voice+percussion | |
| 0x258c34 | b0 set to 0=village city guitar | |
| 0x258c6c | b0 set to 0=village bridge vocals | |
| 0x258e24 | b0 set to 0=Accumula town girl playing the piano | |
| 0x258e5c | b0 set to 0=Accumula town guy playing the drums | |
| 0x2592d2 | Map ID (works in white forest too) | |
| 0x2592d6 | Location ID | |
| 0x259906 | battle institute battle format 14=single 15=double | |
| 0x25990e | battle institute rank (dynamic) 6=Master | |
| 0x259912 | battle institute points (16 bit) (dynamic) | |
| 0x26d6d0 | Battle - Player - active Pokémon 1 - ID (16bit) | |
| 0x26d6d4 | Battle - Player - active Pokémon 1 - HP left (16bit) | |
| 0x26d6da | Battle - Player - active Pokémon 1 - Ability ID (16bit) | |
| 0x26d6df | b0=1: if the pokemon has been sent to battle at least once | |
| 0x26d7d0 | Battle - Player - active Pokémon 1 - Move 1 - PP left | |
| 0x26d7d1 | Battle - Player - active Pokémon 1 - Move 1 - max PP | |
| 0x26d7de | Battle - Player - active Pokémon 1 - Move 2 - PP left | |
| 0x26d7df | Battle - Player - active Pokémon 1 - Move 2 - max PP | |
| 0x26d7ec | Battle - Player - active Pokémon 1 - Move 3 - PP left | |
| 0x26d7ed | Battle - Player - active Pokémon 1 - Move 3 - max PP | |
| 0x26d7fa | Battle - Player - active Pokémon 1 - Move 4 - PP left | |
| 0x26d7fb | Battle - Player - active Pokémon 1 - Move 4 - max PP | |
| 0x26d8f4 | pokemon id (2nd slot, in battle) | |
| 0x26d8fa | hold item (2nd slot, in battle) | |
| 0x26d903 | b0=1: if the pokemon has been sent to battle at least once | |
| 0x26db18 | pokemon id (3rd slot, in battle) | |
| 0x26dd3c | pokemon id (4th slot, in battle) | |
| 0x26df60 | pokemon id (5th slot, in battle) | |
| 0x26e184 | pokemon id (6th slot, in battle) | |
| 0x26e3a8 | Battle - Opponent - active Pokémon 1 - ID (16bit) | |
| 0x26e3ac | Battle - Opponent - active Pokémon 1 - HP left (16bit) | |
| 0x26e3b2 | Battle - Opponent - active Pokémon 1 - Ability ID (16bit) | |
| 0x26e3b4 | Battle - Opponent - active Pokémon 1 - Level | |
| 0x26e4e2 | current turn? | |
| 0x26e5cc | 2nd slot enemy pokemon id | |
| 0x26e70a | attack id (16 bit) | |
| 0x26e7f0 | 3rd slot enemy pokemon id | |
| 0x270f28 | enemy attack id | |
| 0x2758c2 | x coordinate (allows teleportation with 0x24f932) | |
| 0x2758ca | y coordinate (dynamic) | |
| 0x281924 | Badge 1 shine (023F max) (216 when you can notice in game) | |
| 0x281928 | Badge 2 shine (023f max) | |
| 0x28192c | Badge 3 shine (023f max) | |
| 0x281930 | Badge 4 shine (023f max) | |
| 0x281934 | Badge 5 shine (023f max) | |
| 0x281938 | Badge 6 shine (023f max) | |
| 0x28193c | Badge 7 shine (023f max) | |
| 0x281940 | Badge 8 shine (023f max) | |
| 0x2a6a83 | Battle - Pokéball used - Shakes it will make | |
| 0x2a6a84 | Battle - Pokéball used - Captureanimation will play | |
| 0x2a6a8c | Battle - Pokéball used (16bit) 0x01=Master Ball 0x02=Ultra Ball 0x03=Great Ball 0x04=Poké Ball 0x05=Safari Ball 0x06=Net Ball 0x07=Dive Ball 0x08=Nest Ball 0x09=Repeat Ball 0x0A=Timer Ball 0x0B=Luxury Ball 0x0C=Premier Ball 0x0D=Dusk Ball 0x0E=Heal Ball 0x0F=Quick Ball 0x10=Cherish Ball | |
| 0x3440ac | \[24-bit\] Pointer to character data +0x46 = X-Position | |
| 0x3ffc83 | Birthday month | |
| 0x3ffc84 | Birthday day | |
| 0x3fffa9 | b7=lid closed (works with cgear on and off) | |
