---
title: "Code Notes - Pokémon Black Version"
source: "https://retroachievements.org/codenotes.php?g=3887"
author:
published:
created: 2026-10-08
description: "Adding achievements to retro games since 2012"
tags:
 - "clippings"
---
### Code Notes

![Pokémon Black Version (Nintendo DS)](https://media.retroachievements.org/Images/104482.png)

Pokémon Black Version (Nintendo DS)

The RetroAchievements addressing scheme for most systems is to access the system memory at address $00000000, immediately followed by the cartridge memory. As such, the addresses displayed below may not directly correspond to the addresses on the real hardware.

There are currently 349 code notes for this game.

| Mem | Note | Author |
| --- | --- | --- |
| 0x000034 | State of the Game: \[8-Bit\] 00 = Not Playing 01 = Playing | |
| 0x0000d2 | \[8bit\] Number of Trainers on the royal unova | |
| 0x0000d4 | \[8bit\] Number of Trainers currently defeated on the royal unova | |
| 0x0000f0 | \[8bit\] Royal Unova trainer 0 | |
| 0x00010c | \[8bit\] Royal Unova trainer 1 | |
| 0x000128 | \[8bit\] Royal Unova trainer 2 | |
| 0x000144 | \[8bit\] Royal Unova trainer 3 | |
| 0x000160 | \[8bit\] Royal Unova trainer 13 | |
| 0x00017c | \[8bit\] Royal Unova trainer 4 | |
| 0x000198 | \[8bit\] Royal Unova trainer 5 | |
| 0x0001b4 | \[8bit\] Royal Unova trainer 6 | |
| 0x0001d0 | \[8bit\] Royal Unova trainer 7 | |
| 0x0001ec | \[8bit\] Royal Unova trainer 12 | |
| 0x000208 | \[8bit\] Royal Unova trainer 8 | |
| 0x000224 | \[8bit\] Royal Unova trainer 11 | |
| 0x000240 | \[8bit\] Royal Unova trainer 10 | |
| 0x00025c | \[8bit\] Royal Unova trainer 13 | |
| 0x000278 | \[8bit\] Royal Unova trainer 9 | |
| 0x000294 | \[8bit\] Royal Unova trainer 15 | |
| 0x0aa294 | Sound Effect: \[16-Bit\] 563 = Super Effective Hit | |
| 0x1404c0 | +0xfdffabb0 = In Battle (Yours, Single): \[8-Bit\] Pokemon's Health \+ 0xfdffabd4 = In Battle (Yours): \[8-Bit\] Pokemon's Level +0xfdffabd8 = In Battle (Yours): \[8-Bit\] 00 = Faint 08 = Idle 09 = Damaged \+ 0xfdffac58 = In Battle (Their) \[8-Bit\] 00 = Faint 08 = Idle 09 = Damaged | |
| 0x2345d2 | \[8bit\] Start of HM / TM's in backpack | |
| 0x23477e | \[8bit\] End of HM / TM's in backpack | |
| 0x234784 | Medecine Bag: \[32-Bit\] 0200 0032 = Rare Candy (512pcs) | |
| 0x234846 | \[16bit\] Berry Bag Slot 1 total number | |
| 0x23484a | \[16bit\] Berry Bag Slot 2 total number | |
| 0x23484e | \[16bit\] Berry Bag Slot 3 total number | |
| 0x234856 | \[16bit\] Berry Bag Slot 5 total number | |
| 0x23485a | \[16bit\] Berry Bag Slot 6 total number | |
| 0x23485e | \[16bit\] Berry Bag Slot 7 total number | |
| 0x234862 | \[16bit\] Berry Bag Slot 8 total number | |
| 0x234866 | \[16bit\] Berry Bag Slot 9 total number | |
| 0x23486a | \[16bit\] Berry Bag Slot 10 total number | |
| 0x234fac | Option: \[Bit\] Bit 1, 2 = Text Speed Bit 4 = Sound Bit 6 = Battle Style Bit 7 = Battle Scene | |
| 0x234fad | Option: \[Bit\] Bit 1 = Save Before IR | |
| 0x23bda0 | \[8bit\] Trainers bit0 - defeated N in Accumula Town bit1 is active as the fight starts | |
| 0x23bda6 | \[8bit\] Events bit1 - Defeated Bianca on Route 2 | |
| 0x23bda8 | Trainer: \[Bit\] bit0 - Twins Kumi & Amy (Event, Route 3) | |
| 0x23bdae | Trainer: \[8-Bit\] bit0 - Fefeated Bianca first battle bit1 - Defeated Cheren first battle | |
| 0x23bdb2 | Pokemon (Gift): \[8-Bit\] 01 - 02 = Pansage, Pansear or Panpour (Event, Dreamyard) | |
| 0x23bdb8 | Item: \[8-Bit\] 00 - 01 = HM01 (Event, Striaton City) | |
| 0x23bdbe | Trainer: \[8-Bit\] 00 - 01 = Team Plasma Grunt (Event, Nimbasa City) | |
| 0x23bdc2 | Trainer: \[8-Bit\] 03 - 07 = Team Plasma Grunts (Event,Cold Storage) | |
| 0x23bdc8 | Trainer: \[8-Bit\] 00 - 01 = N (Event, Nimbasa City) | |
| 0x23bdca | Trainer: \[8-Bit\] 04 - 05 = Bianca (Event, Driftveil City) | |
| 0x23bdd0 | Trainer: \[8-Bit\] 00 - 01 = N (Event, Nacrene City) | |
| 0x23bdd2 | Trainer: \[8 -Bit\] 00 - 01 = Cheren/Preschooler Sarah & Billy (Event, Route 5) | |
| 0x23bdd4 | Trainer: \[8-Bit\] 03 - 04 = Team Plasma Grunts (Event, Dreamyard) | |
| 0x23bdd6 | Trainer: \[Bit\] 00 - 01 = Cheren (Event, Route 3) 03 - 04 = Team Plasma Grunts (Event, Wellspring Cave) | |
| 0x23bde0 | Item (Gifted): \[8-Bit\] 01 - 02 = TM78 (Event, Route 6) | |
| 0x23bde2 | Trainer: \[8-Bit\] 04 - 05 = N (Chargestone Cave) | |
| 0x23bde4 | Trainer: \[8-Bit\] 01- 02 = Cheren (Event, Route 4) | |
| 0x23bdfa | Trainer: \[8-Bit\] 07 - 08 = Team Plasma Grunt (Event, Dragonspiral Tower) | |
| 0x23be00 | Trainer: \[8-Bit\] 00 - 01 = Team Plasma Grunt (Event, Pinwheel Forest) 01 - 02 = Team Plasma Grunt (Event, Pinwheel Forest) 02 - 03 = Team Plasma Grunt (Event, Pinwheel Forest) 03 - 04 = Team Plasma Grunt (Event, Pinwheel Forest) | |
| 0x23be04 | Trainer: \[8-Bit\] 01- 02 = Bianca (Event, Castelia City) | |
| 0x23be0a | Trainer: \[8-Bit\] 02 - 03 = Team Plasma Grunt (Event, Castelia City) | |
| 0x23be14 | Trainer: \[8-Bit\] 01 - 02 = Cheren (Event, Twist Mountain) | |
| 0x23be18 | \[8bit\] events bit2 - N's Defeat in N's castle with Zekrom | |
| 0x23be1c | Trainer: \[8-Bit\] 04 - 05 = Cheren (Event, Route 10) | |
| 0x23be28 | Item (Gifted): \[8-Bit\] 00 - 01 = TM70 (Event, Castelia City) | |
| 0x23be34 | Trainer: \[8-Bit\] 00 - 01 = Danser Mickey (Event, Castelia City) 02 - 03 = Danser Edmond (Event, Castelia City) 03 - 04 = Danser Raymond (Event, Castelia City) Item: \[8-Bit\] 04 - 05 = Amulet Coin (Event, Castelia City) | |
| 0x23be38 | Item (Gifted) \[8-Bit\] 00 - 01 = TM56 = (Route 9) | |
| 0x23be42 | Trainer: \[8-Bit\] 00 - 01 = Biance (Event, Route 8) | |
| 0x23be44 | \[8bit\] Looker sidequest | |
| 0x23be4e | Item (Gifted): \[8-Bit\] 01 - 02 = Gram 3 (Event, Route 13) | |
| 0x23be6e | Trainer: \[8-Bit\] 00 - 01 = Team Plasma Grunt (Event, Relic Castle) | |
| 0x23bf28 | \[8bit\] events 77fe - Sandwich orders - 1 wrong 7ffe - Sandwich Orders - all correct | |
| 0x23bf36 | Trainer: \[Bit\] Bit 4 = Rich Boy Rolan (Nimbasa Gym) Bit 5 = Lady Colette (Nimbasa Gym) | |
| 0x23bf38 | Trainer: \[Bit\] Bit 0 = Scientist Satomi (Nacrene City Gym) Bit 1 = School Kid Lydia (Nacrene City Gym) Bit 2 = Harlequin Kerry (Castelia City Gym) Bit 3 = Harlequin Rick (Castelia City Gym) | |
| 0x23bf3c | Trainer: \[Bit\] bit3 - battle company chairman Bit 5 = Musician Preston (Electric Guitar, Route 5) | |
| 0x23bf3d | Item (Gift): \[Bit\] Bit 6 = TM54 (Juniper's Lab) Bit 7 = TM17 (Juniper's Lab) | |
| 0x23bf3e | Item (Gift): \[Bit\] Bit 0 = TM10 (Juniper's Lab) | |
| 0x23bf3f | \[8bit\] Items bit5 - Dusk ball given by old man in Striation City | |
| 0x23bf40 | Trainer: \[8-Bit\] bit0 = Cheren (Event, Accumula Town) | |
| 0x23bf48 | Item (Gift): \[8 Bit\] Bit 7 = Dusk Stone (Route 10) | |
| 0x23bf49 | Item (Gifted): \[Bit\] Bit 7 = TM94 (Pinwheel Forest) | |
| 0x23bf4a | Item (Gifted): \[Bit\] Bit 0 = TM28 (Route 4) | |
| 0x23bf4f | Pokemon (Gift): \[Bit\] Bit 3 = Egg (Route 18, Larvesta) Bit 6 = Gram 1 (Route 13) | |
| 0x23bf52 | Pokemon (Gift): \[Bit\] Bit 3 = Magikarp (Marvelous Bridge) | |
| 0x23bf53 | \[8bit\] Events bit6 - Deerling leaf stone | |
| 0x23bf54 | Trainer: \[Bit\] Bit 0 = Naoki (Aftertrade) Bit 1 = Cheren (Victory Road) Bit 3 = Aya (Aftertrade) | |
| 0x23bf55 | Item (Gift): \[Bit\] Bit 2 = Ultra Ball (N's Castle) | |
| 0x23bf7b | \[8bit\] events Darmantian awakened bit 7, 3, 2, 1, 0 | |
| 0x23bf80 | Item (Gift): \[Bit\] Bit 1 = TM08 (Route 14) Bit 2 = TM69 (Chargestone Cave) Bit 3 = TM75 (Dreamyard) Bit 4 = TM32 (Route 18) | |
| 0x23bf81 | Item (Gift): \[Bit\] Bit 4 = TM01 (Cold Storage) | |
| 0x23bf87 | Stationary Pokemon: \[Bit\] Bit 2 = TM89 (Route 13) Bit 3 = Gram 2 (Route 13) Bit 7 = Foongus (Route 6) | |
| 0x23bf88 | Stationary Pokemon: \[Bit\] Bit 0 = Foongus (Route 6) Bit 1 = Amoonguss (Route 10) Bit 2 = Amoonguss (Route 10) Bit 3 = Foongus (Route 10) Bit 4 = Foongus (Route 10) | |
| 0x23bf8d | Item (Gift): Bit 1 = TM04 (Relic Castle) bit2 - Volcarona interaction | |
| 0x23bf91 | Item: \[Bit\] Bit 3 = Smoke Ball (Castelia City) | |
| 0x23bf98 | \[8bit\] Items bit4 - Balm Mushroom (Hidden, Striaton City) bit5 - Zinc (Hidden, Striation City) bit6 - max potion (dreamyard) bit7 - Ultra ball hiddden in sand castle (Route 3) | |
| 0x23bf99 | \[8bit\] Item bit0 - Rare Candy (Route 3, hidden) bit1 - Revive (Nacrene City, hidden) bit2 - awakening (dreamyard) bit3 - awakening (dreamyard) bit4 - Ether (Pinwheel Forest, hidden) | |
| 0x23bf9d | \[8bit\] Items bit4 - Ultraball (Nacrene City, hidden) bit5 - Super potion (Nacrene City, hidden) | |
| 0x23bf9e | \[8bit\] Items bit0 - rare candy (Pinwheel forest, hidden) bit1 - Tinymushroom (Pinwheel forest, hidden bit2 - ultra ball (route 4, hidden) bit3 - hyper potion (rotue 4, hidden) bit4 - Ether (Desert resort, hidden) bit5 - stardust (desert resort, hidden) bit6 - hyper potion (desert resort, hidden) bit7 - desert resort PPMAX | |
| 0x23bf9f | \[8bit\] items bit1- dive ball (cold storage, hidden) bit2 - tiny mushroom (route 6, hidden) bit3 - big mushroom (route 6, hidden) bit4 - tiny mushroom (route 6, hidden) bit5 - full restore (route 10, hidden) | |
| 0x23bfa0 | \[8bit\] Items bit0 - HP Up (chargestone cave, hidden) bit1 - max potion (Chargestone cave, hidden) bit2 - Revive (chargestone cave, hidden) bit3 - Star piece (chargestone cave, hidden) bit4 - Paralyz heal (Mistralton City, hidden) bit5 - Repel (Mistralton City, hidden) bit6 - max ether (Mistralton City, hidden) bit7 - ultra ball (Twisted mountain, hidden) | |
| 0x23bfa1 | \[8bit\] Items bit0 - twisted mountain, hidden) bit1 - twisted mountain, hidden) bit2 - rare candy (twist mountain) bit3 - hyper potion (twisted mountain, hidden) bit4 - stardust (twisted mountain, hidden) bit5 - stardust (twisted mountain, hidden) bit7 - Elixir (twisted mountain,hidden) | |
| 0x23bfa2 | \[8bit\] Items bit0 - protein (twist mountain) bit1 - max revive (Icirrus City, hidden) bit4 - max either (route 8, hidden) bit5 - max either (route 9, hidden) bit6 - Lemonade (route 9, hidden) bit7 - opelucid city (max repel, hidden) | |
| 0x23bfa3 | \[8bit\] items bit0 - ultra ball (opeluid city, hidden) bit1 - ether (challengers cave, hidden) bit2 - max potion (challengers cave, hidden) bit3 - full restore (challengers cave, hidden) bit4 - rare candy (challenger's cave, hidden) bit5 - hyper potion (victory road, hidden) bit6 - ultra ball (victory road, hidden) | |
| 0x23bfa4 | \[8bit\] items bit1 - revive (victory road, hidden) bit2 - full heal (victory road, hidden) bit3 - carbos (victory road, hidden) bit4 - hyper potion (route 11) bit5 - tiny mushroom (route 12) bit6 - bit 7 - big mushroom (route 12) | |
| 0x23bfa5 | \[8bit\] items bit0 - tiny mushroom (route 12) bit1 - Elixir (Lacunosa town) bit2 - max repel (Lacunosa town) bit3 - pearl (route 13) bit4 - stardust (route 13) bit5 - stardust (route 13) bit6 - max revive (route 13) bit7 - rare candy (route 13) | |
| 0x23bfa6 | \[8bit\] item bit0 - heart scale (route 13) bit1 - stardust (undella bay) bit2 - pearl (undella bay) bit3 - tiny mushroom abundant shrine bit4 - heart scale (undella bay) bit5 - balm mushroom (abundant shrine) bit6 - big mushroom (abundant shrine) bit7 - Max revive (route 15, hidden) | |
| 0x23bfa7 | \[8bit\] items bit0 - heart scale (route 17) bit1 - heart scale (route 17) bit2 - calcium (rotue 18) bit3 - route18, hidden bit4 - Route 18, hidden bit5 - heart scale (route 17) bit6 - max elixir (wellspring cave) | |
| 0x23bfa8 | \[8bit\] Items bit3 - awakening (dreamyard) bit4 - leftovers (route 11) bit5 - rare candy (desert resort, hidden) bit6 - star piece (challengers cave, hidden) bit7 - max ether (challengers cave, hidden) | |
| 0x23bfa9 | \[8bit\] items bit0 - heart scale (challengers cave, hidden) bit1 - tiny mushroom abundant shrine bit2 - ultra ball (route 15, hidden) bit3 - big pearl (route 17, hidden) bit4 - Hyper Potion (wellspring cave) bit5 - max either (moor of icirrus) bit6 - gold nugget (moor of icirrus) bit7 - big mushroom (moor of icirrus) | |
| 0x23bfaa | \[8bit\] items bit0 - revive (moor of icirrus, hidden bit3 - big mushroom (giant chasm) bit4 - tiny mushroom (giant chasm) bit5 - tiny mushroom (giant chasm) bit6 - max revive (route 11, hidden) | |
| 0x23bfab | \[8bit\] items bit0 - Elixir (Chargestone cave, hidden) bit1 - paralyz heal (chargestone cave, hidden) bit2 - paralyz heal (Chargestone cave, hidden) bit3 - Elixir (Relic Csatle, hidden) bit5 - Elixir (Mistralton Cave) bit6 - Hyper potion (Mistralton Cave) bit7 - Carbos (Mistralton Cave) | |
| 0x23bfac | \[8bit\] Item bit0 - Pearl string (route 13, hidden) bit1 - heart scale (Driftveil, hidden) bit2 - burn heal (route 4, hidden) bit3 - pearl (route 4, hidden) bit4 - tiny mushroom (abundant shrine) bit5 - PPup (Wellspring cave) bit6 - Full Heal (Wellspring cave) bit7 - Revive (wellspring cave) | |
| 0x23bfad | \[8bit\] Item bit0 - Max Potion (Wellspring Cave) bit2 - PPup (Mistralton Cave, hidden) bit3 - full restore (route 8, hidden) bit4 - PP UP (cold storage) bit5 - hyper potion (cold storage, hidden) bit6 - Protein (Lostlorn forest) bit7 - ultra ball (icirrus city, hidden) | |
| 0x23bfae | \[8bit\] Item bit0 - timer ball (icirrus city, hidden) bit1 - HP up (village bridge) bit2 - full restore (vilalge bridge) bit4 - ether (route 4, hidden) | |
| 0x23bfb2 | Item: \[Bit\] Bit 2 = Pokéball (Route 2) Bit 3 = Potion (Route 2) Bit 4 = Rare Candy (Route 2) Bit 5 = Super Potion (Route 2) Bit 6 = Great Ball (Route 2) Bit 7 = Parlyz Heal (Dreamyard) | |
| 0x23bfb3 | Item: \[Bit\] Bit 0 = Potion (Dreamyard) Bit 1 = Repel (Dreamyard) Bit 2 = Potion (Route 2) Bit 3 = Revive (Route 5) Bit 4 = Zinc (Route 5) Bit 5 = Hyper Potion (Route 5) Bit 6 = Repel (Route 3) Bit 7 = Full Heal (Route 3) | |
| 0x23bfb4 | Item: \[Bit\] Bit 0 = Great Ball (Route 3) Bit 1 = Revive (Relic Castle) Bit 2 = Super Potion (Route 4) Bit 3 = TM12 (Victory Road) Bit 4 = Full Restore (Victory Road) Bit 5 = TM93 (Victory Road) Bit 6 = Nugget (Victory Road) Bit 7 = Ultra Ball (Victory Road) | |
| 0x23bfb5 | Item: \[Bit\] Bit 0 = SilverPowder (Pinwhell Forest) Bit 1 = Parlyz Heal (Pinwheel Forest) Bit 2 = Big Root (Pinwheel Forest) Bit 3 = TM86 (Pinwheel Forest) Bit 4 = TM22 (Pinwhell Forest) Bit 5 = Heart Scale (Desert Ressort) Bit 6 = Super Potion (Desert Ressort) Bit 7 = Ice Heal (Cold Storage) | |
| 0x23bfb6 | Item: \[Bit\] Bit 0 = Hyper Potion (Cold Storage) Bit 1 = Heal Ball (Chargestone Cave) Bit 2 = Revive (Chargestone Cave) Bit 3 = Iron (Chargestone Cave) Bit 4 = Magnet (Chargestone Cave) bit5 - thunderstone (chargestone cave) Bit 6 = BrightPowder (Chargestone Cave) bit7 - pearl (Route 1) | |
| 0x23bfb7 | Item: \[Bit\] Bit 0 = Antidote (Route 3) Bit 1 = Super Potion (Route 3) Bit 2 = Revive (Dreamyard) Bit 3 = Poké Ball (Dreamyard) bit4 - hyper potion (dreamyard) Bit 5 = Max Ether (Route 3) Bit 6 = HP Up (Route 3) Bit 7 = Net Ball (Pinwheel Forest) | |
| 0x23bfb8 | Item: \[Bit\] Bit 0 = Antidote (Pinwheel Forest) Bit 1 = Super Potion (Pinwheel Forest) Bit 2 = Ether (Pinwheel Forest) Bit 3 = X Accuracy (Route 4) Bit 4 = Max Potion (Relic Castle) Bit 6 = Great Ball (Route 4) Bit 7 = Ether (Route 4) | |
| 0x23bfb9 | Item: \[Bit\] Bit 0 = Burn Heal (Route 4) Bit 1 = Fresh Water (Desert Ressort) Bit 2 = Fire Stone (Desert Ressort) Bit 3 = Stardust (Desert Ressort) Bit 4 = TM30 (Relic Castle) Bit 5 = PP Up (Relic Castle) Bit 6 = Sun Stone (Relic Castle) bit7 = Scald (cold storage) | |
| 0x23bfba | Item: \[Bit\] Bit 0 = Heart Scale (Cold Storage) Bit 1 = Leaf Stone (Route 6) Bit 2 = Silk Scarf (Route 6) Bit 3 = Hyper Potion (Route 6) Bit 4 = Timer Ball (Chargestone Cave) Bit 5 = TM26 (Relic Castle) bit6 - ulltra ball (route 7) Bit 7 = PP Up (Route 7) | |
| 0x23bfbb | Item: \[Bit\] Bit 0 = TM81 (Route 7) Bit 1 = Max Ether (Route 7) Bit 2 = Full Heal (Twist Mountain) Bit 3 = Moon Stone (Twist Mountain) Bit 4 = PP Up (Twist Mountain) Bit 5 = Max Potion (Twist Mountain) Bit 7 = TM91 (Twist Mountain) | |
| 0x23bfbc | Item: \[Bit\] Bit 0 = TM63 (Dragonspiral Tower) Bit 1 = Poison Barb (Route 8) Bit 2 = Full Heal (Route 8) Bit 3 = HP Up (Route 9) Bit 4 = Full Restore (Route 9) Bit 5 = TM05 (Route 10) Bit 6 = Dawn Stone (Route 10) Bit 7 = Full Heal (Route 10) | |
| 0x23bfbd | Item: \[Bit\] Bit 0 = Max Revive (Relic Castle) Bit 1 = Ether (Cold Storage) Bit 2 = Protein (Cold Storage) Bit 3 = Ether (Twist Mountain) Bit 4 = Max Revive (Victory Road) Bit 5 = Rare Candy (Victory Road) Bit 6 = TM02 (Victory Road) Bit 7 = Calcium (Victory Road) | |
| 0x23bfbe | Item: \[Bit\] Bit 0 = Prism Scale (Route 13) Bit 1 = Hyper Potion (Route 11) Bit 2 = TM50 (Route 11) Bit 3 = Protector (Route 11) Bit 4 = Full Heal (Route 12) Bit 5 = TM35 (Route 12) Bit 6 = Revive (Route 12) Bit 7 = Max Ether (Route 13) | |
| 0x23bfbf | Item: \[Bit\] Bit 0 = DeepSeaScale (Route 13) Bit 1 = Razor Claw (Route 13) Bit 2 = TM29 (Route 13) bit3 - Revive (Battle company) Bit 4 = Ultra Ball (Route 14) Bit 5 = Reaper Cloth (Route 14) Bit 6 = Antidote (Pinwheel Forest) bit7 - upgrade (route 15) | |
| 0x23bfc0 | Item: \[Bit\] Bit 0 = TM09 (Route 15) Bit 1 = Max Elixir (Dragonspiral Tower) Bit 2 = TM66 (Route 16) Bit 3 = Rare Casdy (Route 16) Bit 4 = TM06 (Route 17) Bit 5 = DeepSeaTooth (Route 17) Bit 6 = TM24 (P2 Laboratory) Bit 7 = TM19 (Route 18) | |
| 0x23bfc1 | Item: \[Bit\] Bit 0 = Dragon Scale (Route 18) Bit 1 = Max Elixir (Route 18) Bit 2 = HM05 (Route 18) Bit 3 = TM61 (Celestial Tower) Bit 4 = Hyper Potion (Celestial Tower) Bit 5 = Spell Tag (Celestial Tower) bit6 - max ether (route 1) bit7 - big pearl (driftveil) | |
| 0x23bfc2 | Item: \[Bit\] Bit 0 = Ultra Ball (Driftveil City) bit1 - water stone (driftveil) Bit 2 = TM84 (Route 6) Bit 3 = Elixir (Route 6) Bit 4 = Nugget (Twist Mountain) Bit 5 = Hyper Potion (Dragonspiral Tower) Bit 6 = TM46 (Wellspring Cave) Bit 7 = Escape Rope (Wellspring Cave) | |
| 0x23bfc3 | Item: \[Bit\] Bit 0 = Elixir (Wellspring Cave) Bit 2 = Rare Candy (Lostlorn Forest) bit3 - Mystic Water (Wellspring cave) bit4 - Dive Ball (wellspring cave) bit5 - TM47 Low Sweep Bit 6 = Hyper Potion (Pinwhell Forest) Bit 7 = Miracle Seed (Pinwheel Forest) | |
| 0x23bfc4 | Item: \[Bit\] Bit 0 = Hyper Potion (Route 4) Bit 1 = Great Ball (Route 5) Bit 2 = TM41 (Route 4) Bit 3 = BlackGlasses (Desert Ressort) Bit 4 = TM39 (Desert Ressort) Bit 5 = Net Ball (Cold Storage) bit6 - Max Repel (Mistralton Cave) bit7 - Hyper Potion (Mistralton Cave) | |
| 0x23bfc5 | Item: \[Bit\] Bit 0 = Great Ball (Striaton City) bit2 - Iron (Mistralton Cave)) bit3 - Hard stone (Mistralton Cave) bit5 - Revive (Mistralton Cave) bit4 - Dusk Stone (Mistralton Cave) bit6 - Rare Candy (Mistralton Cave) Bit 7 = TM58 (Mistralton City) | |
| 0x23bfc6 | Item: \[Bit\] Bit 0 = TM65 (Celestial Tower) Bit 1 = Revive (Celestial Tower) Bit 3 = Ultra Ball (Twist Mountain) Bit 4 = TM36 (Route 8) Bit 6 = Stardust (Dragonspiral Tower) | |
| 0x23bfc7 | Item: \[Bit\] bit0 - protein ( challengers cave) bit2 - oval stone (challengers cave) Bit 3 = Star Piece (Dragonspiral Tower) bit4 - black belt (challengers cave) Bit 5 = Shiny Stone (Dragonspiral Tower) bit6 - timer ball (challengers cave) Bit 7 = Revive (Dragonspiral Tower) | |
| 0x23bfc8 | Item: \[Bit\] Bit 0 = Stardust (Dragonspiral Tower) Bit 1 = Full Restore (Route 10) Bit 2 = Star Piece (Giant Chasm) Bit 3 = Star Piece (Giant Chasm) Bit 4 = Comet Shard (Giant Chasm) Bit 5 = Revive (Twist Mountain) | |
| 0x23bfca | \[8bit\] items bit7 - max revive (moor of icirrus) | |
| 0x23bfcb | Item: \[Bit\] bit3 - Carbos (moor of icirrus) Bit 7 = Max Potion (Moor of Icirrus) | |
| 0x23bfcc | Item: \[Bit\] Bit 2 = Max Elixir (Moor of Icirrus) Bit 3 = Ultra Ball (Moor of Icirrus) bit5 - Big Nugget (Undella town) | |
| 0x23bfcd | Item: \[Bit\] Bit 6 = Rare Candy (Icirrus City) | |
| 0x23bfce | Item: \[Bit\] Bit 0 = Great Ball (Pinwheel Forest) | |
| 0x23bfd2 | Item: \[Bit\] Bit 5 = X Speed (Striaton City) Bit 6 = Heart Scale (Route 18) | |
| 0x23bfd3 | Item: \[Bit\] Bit 5 = Revive (Giant Chasm) Bit 6 = Carbos(Giant Chasm) Bit 7 = TM13 (Giant Chasm) | |
| 0x23bfd4 | Item: \[Bit\] Bit 0 = Full Heal (Giant Chasm) Bit 1 = Max Potion (Giant Chasm) Bit 2 = TM03 (Giant Chasm) Bit 3 = Max Elixir (Giant Chasm) Bit 4 = Max Revive (Giant Chasm) Bit 5 = Electrizer (Route 13) Bit 6 = TM92 (Abundant Shrine) bit7 - hyper potion (battle company) | |
| 0x23bfd5 | Item: \[Bit\] Bit 0 = Rare Candy (Abundant Shrine) Bit 1 = Hyper Potion (Route 10) Bit 2 = Razor Fang (Abundant Shrine) Bit 3 = TM35 (Abundant Shrine) Bit 4 = Full Heal (Victory Road) Bit 5 = Hyper Potion (Abundant Shrine) Bit 6 = Full Restore (N's Castle) Bit 7 = Big Mushroom (Lostlorn Forest) | |
| 0x23bfd6 | Item: \[Bit\] Bit 0 = Dubious Disc (P2 Laboratory) Bit 1 = Charcoal (Route 16) Bit 2 = Calcium (Village Bridge) Bit 3 = Max Potion (N's Castle) Bit 4 = Ultra Ball (Village Bridge) Bit 5 = X Defend (Dreamyard) Bit 6 = Awakening (Route 3) Bit 7 = Super Potion (Pinwheel Forest) | |
| 0x23bfd7 | Item: \[Bit\] Bit 0 = NerverMeltIce (Cold Storage) Bit 1 = Parlyz Heal (Chargestone Cave) Bit 2 = Hyper Potion (Chargestone Cave) Bit 3 = Rare Cady (Chargestone Cave) Bit 4 = Hyper Potion (Chargestone Cave) Bit 5 = Max Revive (N's Castle) Bit 7 = TwistedSpoon (Dreamyard) | |
| 0x23bfd8 | Item: \[Bit\] Bit 0 = Ultra Ball (Route 8) Bit 1 = Rare Candy (N's Room) Bit 2 = Nugget (Dragonspiral Tower) Bit 3 = Dragon Fang (Dragonspiral Tower) | |
| 0x23bfd9 | Trainer: \[Bit\] Bit 5 = Youngster Jimmy (Route 2) Bit 6 = Lass Mali (Route 2) Bit 7 = School Kid Al (Route 3) | |
| 0x23bfda | Trainer: \[Bit\] Bit 0 = School Kid Marsha (Route 3) Bit 3 = Youngster Joey (Dreamyard) Bit 4 = Lass Eri (Dreamyard) Bit 5 = Waiter Maxwell (Striaton City Gym) Bit 6 = Waitress Tia (Striaton City Gym) | |
| 0x23bfdb | Trainer: \[Bit\] Bit 2 = Nursery Aide Autumn (Route 3) Bit 3 = Preschooler Wendy (Route 3) Bit 4 = Preschooler Doyle (Route 3) Bit 5 = Preschooler Tully (Route 3) Bit 7 = PKMN Breeder Galen (Route 3) | |
| 0x23bfdc | Trainer: \[Bit\] Bit 0 = PKMN Breeder Adelaide (Route 3) Bit 6 = PKMN Ranger Forrest (Pinwheel Forest) Bit 7 = PKMN Ranger Irene (Pinwheel Forest) | |
| 0x23bfdd | Trainer: \[Bit\] Bit 0 = PKMN Ranger Miguel (Pinwheel Forest) Bit 1 = PKMN Ranger Audra (Pinwheel Forest) Bit 2 = School Kid Sammy (Pinwheel Forest) Bit 3 = School Kid Millie (Pinwheel Forest) Bit 4 = Twins Mayo & May (Pinwheel Forest) Bit 5 = Youngster Nicholas (Pinwheel Forest) Bit 6 = Lass Eva (Pinwheel Forest) Bit 7 = Worker Scott (Route 4) | |
| 0x23bfde | Trainer: \[Bit\] Bit 0 = Worker Shelby (Route 4) Bit 1 = Worker Zack (Route 4) Bit 2 = Worker Cairn (Twist Mountain) Bit 3 = Backpacker Waylon (Route 4) Bit 4 = Backpacker Jill (Route 4) Bit 5 = Fisherman Hubert (Route 4) Bit 6 = Fisherman Andrew (Route 4) | |
| 0x23bfdf | Trainer: \[Bit\] Bit 0 = Backpacker Michael (Route 5) Bit 1 = Backpacker Lois (Route 5) Bit 3 = Dancer Brian (Route 5) Bit 4 = Harlequin Paul (Route 5) Bit 5 = Artist Horton (Route 5) Bit 6 = Baker Jenn (Route 5) Bit 7 = Psychic Perry (Relic Castle) | |
| 0x23bfe0 | Trainer: \[Bit\] Bit 0 = Psychic Dua (Relic Castle) | |
| 0x23bfe1 | Trainer: \[Bit\] Bit 6 = Rich Boy Cody (Nimbasa Gym) | |
| 0x23bfe2 | Trainer: \[Bit\] Bit 0 = Lady Magnolia (Nimbasa Gym) Bit 2 = Pilot Ted (Mistralton Gym) Bit 3 = Pilot Chase (Mistralton Gym) Bit 4 = Worker Victor (Cold Storage) Bit 5 = Worker Filipe (Cold Storage) Bit 6 = Worker Glenn (Cold Storage) Bit 7 = Worker Ryan (Cold Storage) | |
| 0x23bfe3 | Trainer: \[Bit\] Bit 0 = Worker Patton (Cold Storage) Bit 1 = Worker Eddie (Cold Storage) Bit 6 = Hoopster Bobby (Nimbasa City, Bascketball) | |
| 0x23bfe4 | Trainer: \[Bit\] Bit 0 = School Kid Edgar (Route 3) Bit 1 = Youngster Roland (Route 2) Bit 2 = School Kid Carter (Nacrene City Gym) | |
| 0x23bfe5 | Trainer: \[Bit\] bit 1- Clerk Ingrid (Battle Company) bit2 - Clerk alberta (battle company) Bit3 = Clerk F Katie (Driftveil City Gym) bit4 - Clerk Trisha bit5 - Waiter Bert bit6 - Waitress Flo (Route 9 Mall) Bit 7 = Ace Trainer Cheyenne (Route 10) | |
| 0x23bfe6 | Trainer: \[Bit\] Bit 0 = Ace Trainer Stella (Chargestone Cave) Bit 1 = Ace Trainer Allison (Chargestone Cave) Bit 3 = Ace Trainer Johan (Route 10) Bit 4 = Ace Trainer Corky (Chargestone Cave) Bit 5 = Ace Trainer Jared (Chargestone Cave) bit7 - Lady Isabel (Route 9 mall) | |
| 0x23bfe7 | Trainer: \[Bit\] bit0 - Rich Boy Manuel Bit 1 = Black Belt Corey (Route 10) Bit 2 = Black Belt Teppei (Twist Mountain) Bit 3 = Black Belt Kentaro (Pinwheel Forest) Bit 4 = Scientist William (Route 6) bit5 - Scientist randall (battle company) bit6 - Scientist steve (battle company) Bit 7 = Scientist Orville (Chargestone Cave) | |
| 0x23bfe8 | Trainer: \[Bit\] bit0 - Scientist samantha (battle company) Bit 1 = Scientist Naoko (Chargestone Cave) Bit 2 = Psychic Micki (Celestial Tower) Bit 3 = Psychic Bryce (Celestial Tower) Bit 4 = Psychic Doreen (Celestial Tower) Bit 5 = Psychic Lin (Celestial Tower) Bit 6 = Worker Rob (Twist Mountain) Bit 7 = Worker Rich (Twist Mountain) | |
| 0x23bfe9 | Trainer: \[Bit\] Bit 0 = Worker Heath (Twist Mountain) Bit 1 = Worker Cliff (Mistralton Gym) Bit 3 = Worker Brady (Mistralton Gym) Bit 4 = Worker Arnold (Mistralton Gym) | |
| 0x23bfea | Trainer: \[Bit\] Bit 3 = Roughneck Reese (Route 9) bit2 - Rougneck chance (Route 9) Bit 6 = Pokéfan Jude (Celestial Tower) Bit 7 = Pokéfan Georgia (Celestial Tower) | |
| 0x23bfeb | Trainer: \[Bit\] Bit 0 = Youngster Albert (Cold Storage) Bit 1 = Youngster Kenneth (Cold Storage) Bit 2 = Youngster Mikey (Route 7) Bit 3 = Youngster Parker (Route 7) Bit 4 = Youngster Zachary (Pinwheel Forest) Bit 5 = Youngster Keita (Pinwheel Forest) | |
| 0x23bfec | Trainer: \[Bit\] Bit 0 = Fisherman Bruce (Route 8) Bit 2 = Doctor Wayne (Chargestone Cave) Bit 3 = Doctor Hank (Twist Mountain) Bit 4 = Nurse Sachiko (Celestial Tower) Bit 5 = Backpacker Jerome (Route 4) Bit 6 = Backpacker Terrance (Route 7) Bit 7 = Backpacker Ruth (Route 7) | |
| 0x23bfed | Trainer: \[Bit\] Bit 0 = Backpacker Anna (Route 4) bit1 - Jim and Cas (Route 9) Bit 2 = Battle Girl Amy (Route 10) Bit 3 = Battle Girl Sharon (Twist Mountain) Bit 4 = Battle Girl Lee (Pinwheel Forest) Bit 5 = Parasol Lady Nicole (Route 6) Bit 6 = Parasol Ladfy Tihana (Route 6) Bit 7 = Parasol Lady Melita (Route 8) | |
| 0x23bfee | Trainer: \[Bit\] Bit 0 = Parasol Lady Lumi (Route 8) bit1 - Clerk Clemens (battle company) bit2 - Clerk warren (battle company) bit3 - clerk ivan (battle company) Bit 4 = Clerk M Isaac (Driftveil City Gym) bit6 - Clerk Wade (batltle company) | |
| 0x23bfef | Trainer: \[Bit\] Bit 6 = Veteran Chester (Route 10) Bit 7 = Veteran Karla (Route 10) | |
| 0x23bff0 | Trainer: \[Bit\] Bit 0 = Biker Philip (Route 9) Bit 1 = Biker Zeke (Route 9) Bit 2 = PKMN Ranger Richard (Route 6) Bit 3 = PKMN Ranger Pedro (Route 7) Bit 4 = PKMN Ranger Lewis (Route 8) Bit 6 = PKMN Ranger Shanti (Route 6) Bit 7 = PKMN Ranger Mary (Route 7) | |
| 0x23bff1 | Trainer: \[Bit\] Bit 0 = PKMN Ranger Annie (Route 8) Bit 2 = Lass Kara (Celestial Tower) Bit 3 = Infielder Alex (Nimbasa City, Baseball) Bit 5 = Hiker Bret (Route 10) Bit 6 = Hiker Hardy (Chargestone Cave) Bit 7 = Hiker Neil (Twist Mountain) | |
| 0x23bff2 | Trainer: \[Bit\] Bit 0 = Harlequin Jack (Castelia City Gym) Bit 2 = Harlequin Louis (Castelia City Gym) Bit 5 = Worker Felix (Driftveil City Gym) Bit 6 = Worker Streling (Driftveil City Gym) Bit 7 = Worker Don (Driftveil City Gym) | |
| 0x23bff4 | Trainer: \[Bit\] Bit 0 = Battle Girl Miriam (Icirrus Gym) Bit 1 = Battle Girl Mikiko (Icirrus Gym) Bit 2 = Battle Girl Chandra (Icirrus Gym) Bit 3 = Black Belt Grant (Icirrus Gym) Bit 4 = Black Belt Kendrew (Icirrus Gym) Bit 5 = Black Belt Thomas (Icirrus Gym) | |
| 0x23bff5 | Trainer: \[Bit\] Bit 1 = Team Plasma Grunt (Relic Castle) Bit 2 = Team Plasma Grunt (Relic Castle) Bit 3 = Team Plasma Grunt (Relic Castle) Bit 4 = Team Plasma Grunt (Relic Castle) Bit 5 = Team Plasma Grunt (Relic Castle) Bit 6 = Team Plasma Grunt (Relic Castle) Bit 7 = Team Plasma Grunt (Relic Castle) | |
| 0x23bff6 | Trainer: \[Bit\] Bit 5 = Psychic Low (Desert Ressort) Bit 6 = Psychic Gaven (Desert Ressort) Bit 7 = Psychic Cybil (Desert Ressort) | |
| 0x23bff7 | Trainer: \[8-Bit\] Bit 0 = Backpacker Kelsey (Desert Ressort) Bit 1 = Backpacker Nate (Desert Ressort) Bit 2 = Backpacker Liz (Desert Ressort) Bit 3 = Backpacker Elaine (Desert Ressort) Bit 4 = Scientist Ronald (Chargestone Cave) Bit 5 = Worker Brand (Twist Mountain) Bit 6 = Hiker Darrell (Twist Mountain) Bit 7 = Hiker Terrell (Twist Mountain) | |
| 0x23bff8 | Trainer: \[Bit\] Bit 0 = Ace Trainer Shanta (Victory Road) Bit 1 = Ace Trainer Cathy (Victory Road) Bit 2 = Ace Trainer Dwayne (Victory Road) Bit 3 = Ace Trainer David (Victory Road) Bit 4 = Black Belt Tyrone (Victory Road) Bit 5 = Doctor Logan (Victory Road) Bit 6 = Veteran Martell (Victory Road) Bit 7 = Veteran Tiffany (Victory Road) | |
| 0x23bff9 | Trainer: \[Bit\] bit0 - blackbelt edward (wellspring cave) bit1 - battle girl maggie (wellspring cave) bit2 - battle girl xiao (wellspring cave) bit3 - Hiker hugh (mistralton cave) bit4 - Hiker Clarke (mistralton cave) Bit 5 = Scientist Ron (Route 6) Bit 6 = Scientist Maria (Route 6) bit7 - Veteran Shaun (Challengers cave) | |
| 0x23bffa | Trainer: \[Bit\] bit0 - Veteran Julia (challengers cave) bit1 - Ace trainer beverly (challengers cave) bit2 - Ace trainer terry (challengers cave) Bit 3 = Psychic Belle (Celestial Tower) Bit 4 = Psychic Kassandra (Celestial Tower) Bit 5 = Ace Trainer Olwen (Opelucid Gym) Bit 6 = Ace Trainer Clare (Opelucid Gym) Bit 7 = Ace Trainer Dara (Opelucid Gym) | |
| 0x23bffb | Trainer: \[Bit\] Bit 1 = Ace Trainer Beckett (Celestial Tower) Bit 2 = Ace Trainer Webster (Opelucid Gym) Bit 3 = Ace Trainer Jose (Opelucid Gym) Bit 4 = Ace Trainer Tom (Opelucid Gym) Bit 6 = Veteran Hugo (Opelucid Gym) Bit 7 = Veteran Kim (Opelucid Gym) | |
| 0x23bffc | \[8bit\] trainers bit5 - ace trainer austin (girl, ferris wheel) | |
| 0x23bffd | Trainer: \[Bit\] bit 0 - Richboy Martin (girl, Ferris wheel) bit1 - Lass Maya (Boy, ferris wheel) Bit 6 = Backpacker Keane (Route 4) Bit 7 = Worker Gus (Route 4) | |
| 0x23bffe | Trainer: \[Bit\] Bit 0 = School Kid Gina (Route 3) Bit 6 = Team Plasma Grunt (Chargestone Cave) Bit 7 = Team Plasma Grunt (Chargestone Cave) | |
| 0x23bfff | Bit 0 = Team Plasma Grunt (Chargestone Cave) Bit 1 = Team Plasma Grunt (Chargestone Cave) Bit 2 = Team Plasma Grunt (Dragonspiral Tower) Bit 3 = Team Plasma Grunt (Dragonspiral Tower) Bit 4 = Team Plasma Grunt (Dragonspiral Tower) | |
| 0x23c000 | Bit 2 = Team Plasma Grunt (Chargestone Cave) Bit 3 = Team Plasma Grunt (Chargestone Cave) Bit 4 = Team Plasma Grunt (Dragonspiral Tower) Bit 6 = Smasher Mari (Tennis Court) | |
| 0x23c001 | Trainer: \[Bit\] Bit 1 = Smasher Elena (Tennis Court) Bit 2 = Smasher Aspen (Tennis Court) bit3 - Infielder Todd bit6 - Infielder Alex bit7 - Infeidler Connor | |
| 0x23c002 | Trainer: \[Bit\] Bit 5 = Linebacker Jonah (Football Stadium) | |
| 0x23c003 | Trainer: \[Bit\] Bit 0 = Linebacker Dan (Football Stadium) Bit 1 = Linebacker Bob (Football Stadium) Bit 2 = Hoopster Lamarcus (Bascketball Court) Bit 5 = Hoopster Bobby (Bascketball Court) Bit 6 = Hoopster John (Bascketball Court) | |
| 0x23c004 | Trainer: \[Bit\] Bit 0 = Backers Hawk & Dar (Football Stadium) Bit 2 = Backers Joe & Ross (Tennis Court) Bit 4 = Backers Masa & Yas (Bascketball Court) bit6 - Backers♂ Alf & Fred | |
| 0x23c005 | Bit2- Backers (female) Ami & Eira Bit 3 = Backers Cam & Abby (Football Stadium) Bit 4 = Ai & Ciel (Tennis Court) Bit 5 = Kat & Phae (Bascketball Court) | |
| 0x23c006 | Ace Trainer Charlie (Tennis Court) | |
| 0x23c007 | Bit 4 = Rich Boy Anthony (Tennis Court) | |
| 0x23c00a | Trainer: \[Bit\] Bit 1 = Swimmer M Wright (Route 17) Bit 2 = Swimmer F Joyce (Route 17) | |
| 0x23c00b | Bit 3 = Preschooler Mia (Tennis Court) | |
| 0x23c00c | Trainer: \[Bit\] Bit 4 = Cyclist Hector (Route 16) Bit 5 = Cyclist Krissa (Route 16) Bit 6 = Ace Trainer Junko (Route 14) bit7 - Ace Trainer Kipp (Route 14) | |
| 0x23c00d | Trainer: \[Bit\] Bit 0 = Policeman Daniel (Route 16) Bit 1 = Swimmer M Berke (Route 17) bit2 - black belt banjamin (route 13) Bit 3 = Black Belt Jay (Route 14) Bit 4 = Artist Zach (Route 13) bit5 - scientist kathrine (dreamyard) bit6 - scientist chan (dreamyard basement) Bit 7 = Scientist Markus (Dreamyard) | |
| 0x23c00e | Trainer: \[Bit\] bit0 - Scientist luke (dreamyard) Bit 1 = Scientist Nathan (P2 Laboratory) bit2 - psychic future (dreamyard) bit3 - Psychic rudolf (dreamyard) bit4 - psychic tommy (dreamyard) Bit 5 = Gentleman Yan (Route 13) Bit 6 = Socialiste Marian (Route 13) Bit 7 = School Kid Jem (Route 12) | |
| 0x23c00f | Trainer: \[Bit\] Bit 0 = School Kid Ann (Route 12) Bit 1 = Pokefan Elliot (Route 15) Bit 2 = Youngster Astor (Route 13) bit3 - fisherman sid (route 14) Bit 4 = Fisherman Lydon (Route 17) Bit 5 = Fisherman Jones (Route 13) bit6 - Fisherman Mick bit7 - fisherman pete | |
| 0x23c010 | Trainer: \[Bit\] Bit 0 = Fisherman Vince (Route 13) Bit 1 = Backpacker Talon (Route 11) Bit 2 = Backpacker Lora (Route 16) Bit 3 = Backpacker Kumiko (Route 18) Bit 4 = Backpacker Corin (Route 11) Bit 5 = Backpacker Sam (Route 18) Bit 6 = Backpacker Peter (Route 16) Bit 7 = Backpacker Stephen (Route 16) | |
| 0x23c011 | Trainer: \[Bit\] bit0 - Battle girl susie (route 15) Bit 1 = Battle Girl Hillary (Route 18) Bit 2 = Parasol Lady Laura (Route 13) Bit 3 = Swimmer F Caroline (Route 17) Bit 4 = Backers Fey & Sue (Route 12) Bit 5 = Twins Emy & Lin (Route 13) Bit 6 = Veteran Ray (Route 18) Bit 7 = PKMN Breeder Eustace (Route 12) | |
| 0x23c012 | Trainer: \[Bit\] Bit 0 = PKMN Breeder Ethel (Route 12) Bit 1 = PKMN Ranger Thalia (Route 11) bit2 - PKMN Ranger Shelly (route 15) Bit 3 = PKMN Ranger Crofton (Route 11) bit4 - Pokemon Ranger Keith (Route 15) Bit 5 = Lass Fey (Route 13) Bit 6 = Hiker Jebediah (Route 14) Bit 7 = Hiker Kit (Route 15) | |
| 0x23c013 | Trainer: \[Bit\] Bit 0 = Hiker Jeremiah (Route 18) | |
| 0x23c018 | Trainer: \[Bit\] Bit 1 = Preschooler Juliet (Pinwheel Forest) Bit 2 = Preschooler Homer (Pinwheel Forest) Bit 3 = Harlequin Pat (Route 7) Bit 4 = Harlequin Ian (Route 7) Bit 5 = Parasol Lady April (Route 4) | |
| 0x23c01a | Trainer: \[Bit\] Bit 2 = Ace Trainer Caroll (Twist Mountain) | |
| 0x23c01b | \[8bit\] trainers bit7 - Ranger Brenda (Route 1) | |
| 0x23c01c | \[8bit\] trainers bit0 - Ranger Brenda (Route 1) bit1 - Fisherman sean (route 1) bit3 - Hiker andy (Boy, ferris wheel) bit4 - Preschooler (Boy, ferris wheel) bit5 - dancer dirk (Girl, ferris wheel) bit6 - Waitress Aurora (Girl, Ferris wheel) | |
| 0x23c01d | Trainer: \[Bit\] bit 5- black empoleon leader deafeted Bit 6 = Nurse Shelly (Pinwheel Forest) | |
| 0x23c01e | Trainer: \[Bit\] Bit 1 = PKMN Ranger Mylene (Desert Ressort) Bit 2 = PKMN Ranger Jaden (Desert Ressort) | |
| 0x23c020 | \[8bit\] Trainers bit4 - swimmer matt (undella bay) bit5 - swimmer bart (undella bay) bit6 - swimmer tim (undella bay) bit7 - Simmer Rebecca (undella bay) | |
| 0x23c021 | Trainer: \[Bit\] bit0 - Swimmer Tyra (undella bay) bit1- swimmer larissa (undella bay) bit2 - lass maki (abundant shrine) Bit 3 = Youngster Wes (Abundant Shrine) bit4 - youngster lester (abundant shrine) Bit 5 = Backpacker Vicki (Route 14) bit6 - Backpacker Toru (challengers cave) Bit 7 = School Kid Serena (Village Bridge) | |
| 0x23c022 | Trainer: \[Bit\] Bit 0 = Scientist Shannon (Village Bridge) bit1 - lass lurleen (abundant shrine) bit2 - Pokemon ranger Chloris (Moor of Icirrus) Bit 3 = PKMN Ranger Harry (Moor of Icirrus) bit4 - fisherman damon (Moor of Icirrus) bit5 - Parasol Lady Mariah | |
| 0x23c025 | \[8bit\] Trainers bit0 - ace trainer glinda bit3 - Ace Trainer Elmer Bit 7 = Team Plasma Grunt (Chargestone Cave) | |
| 0x23c026 | Trainer: \[Bit\] Bit 0 = Team Plasma Grunt (Dragonspiral Tower) Bit 1 = Doctor Jerry (Desert Ressort) | |
| 0x23c054 | Menu: \[Bits\] Bit 1 = Pokemon Bit 2 = Pokedex | |
| 0x23c07d | \[8bit\] events bit6 - pokemon massaged bit7 - Casteliacone given | |
| 0x23c07e | \[8bit\] Events bit5 - birthday quiz | |
| 0x23c07f | \[8bit\] Events bit0 - trainer blocking the ferris wheel battled bit4 - Musharna with telepathy ability | |
| 0x23c080 | \[8bit\] events bit3 - accepted job for chef at village bridge | |
| 0x23c081 | \[8bit\] Events bit1 - patrat minigame guessed correctly | |
| 0x23cdac | Money: \[32-Bit\] | |
| 0x23cdb0 | Badge: \[Bits\] Bit 0 = Trio Badge (TM83) Bit 1 = Basic Badge (TM67) Bit 2 = Insect Badge (TM76) Bit 3 = Bolt Badge (TM72) Bit 4 = Quake Badge (TM @0x23be28) Bit 5 = Jet Badge (TM62) Bit 6 = Freeze Badge (TM79) Bit 7 = Legend Badge (TM 82) | |
| 0x23d1b0 | Pokedex Bit 0 = National Dex Bit 1 = Search Option | |
| 0x23d1b4 | Pokédex Obtained: \[Bits\] Bit 0 = Bulbisaur Bit 1 = Ivysaur Bit 2 = Venusaur Bit 3 = Charmander Bit 4 = Charmeleon Bit 5 = Charizard Bit 6 = Squirtle Bit 7 = Wartortle | |
| 0x23d1b5 | Pokédex Obtained: \[Bits\] Bit 0 = Blastoise Bit 1 = Caterpie Bit 2 = Metapod Bit 3 = Butterfree Bit 4 = Weedle Bit 5 = Kakuna Bit 6 = Beedrill Bit 7 = Pidgey | |
| 0x23d1b6 | Pokédex Obtained: \[Bits\] Bit 0 = Pidgeotto Bit 1 = Pidgeot Bit 2 = Rattata Bit 3 = Raticate Bit 4 = Spearow Bit 5 = Fearow Bit 6 = Ekans Bit 7 = Arbok | |
| 0x23d1b7 | Pokédex Obtained: \[Bits\] Bit 0 = Pikachu Bit 1 = Raichu Bit 2 = Sandshrew Bit 3 = Sandslash Bit 4 = Nidoran F Bit 5 = Nidorina Bit 6 = Nidoqueen Bit 7 = Nidoran M | |
| 0x23d1b8 | Pokédex Obtained: \[Bits\] Bit 0 = Nidorino Bit 1 = Nidoking Bit 2 = Clefairy Bit 3 = Clefable Bit 4 = Vulpix Bit 5 = Ninetales Bit 6 = Jigglypuff Bit 7 = Wigglytuff | |
| 0x23d1b9 | Pokédex Obtained: \[Bits\] Bit 0 = Zubat Bit 1 = Golbat Bit 2 = Oddish Bit 3 = Gloom Bit 4 = Vileplume Bit 5 = Paras Bit 6 = Parasect Bit 7 = Venomat | |
| 0x23d1ba | Pokédex Obtained: \[Bits\] Bit 0 = Venomoth Bit 1 = Diglett Bit 2 = Dugtrio Bit 3 = Meowth Bit 4 = Persian Bit 5 = Psyduck Bit 6 = Golduck Bit 7 = Mankey | |
| 0x23d1bb | Pokédex Obtained: \[Bits\] Bit 0 = Primeape Bit 1 = Growlithe Bit 2 = Arcanine Bit 3 = Poliwag Bit 4 = Poliwhirl Bit 5 = Poliwrath Bit 6 = Abra Bit 7 = Kadabra | |
| 0x23d1bc | Pokédex Obtained: \[Bits\] Bit 0 = Alakazam Bit 1 = Machop Bit 2 = Machoke Bit 3 = Machamp Bit 4 = Bellsprout Bit 5 = Weepinbel Bit 6 = Victreebel Bit 7 = Tentacool | |
| 0x23d1bd | Pokédex Obtained: \[Bits\] Bit 0 = Tentacruel Bit 1 = Geodude Bit 2 = Graveler Bit 3 = Golem Bit 4 = Ponyta Bit 5 = Rapidash Bit 6 = Slowpoke Bit 7 = Slowbro | |
| 0x23d1be | Pokédex Obtained: \[Bits\] Bit 0 = Magnemite Bit 1 = Magneton Bit 2 = Farfetch'd Bit 3 = Doduo Bit 4 = Dodrio Bit 5 = Seel Bit 6 = Dewgong Bit 7 = Grimer | |
| 0x23d1bf | Pokédex Obtained: \[Bits\] Bit 0 = Muk Bit 1 = Shellder Bit 2 = Cloyster Bit 3 = Gastly Bit 4 = Haunter Bit 5 = Gengar Bit 6 = Onix Bit 7 = Drowzee | |
| 0x23d1c0 | Pokédex Obtained: \[Bits\] Bit 0 = Hypno Bit 1 = Krabby Bit 2 = Kingler Bit 3 = Voltorb Bit 4 = Electrode Bit 5 = Exeggcute Bit 6 = Exeggutor Bit 7 = Cubone | |
| 0x23d1c1 | Pokédex Obtained: \[Bits\] Bit 0 = Marowak Bit 1 = Hitmonlee Bit 2 = Hitmonchan Bit 3 = Licktung Bit 4 = Koffing Bit 5 = Weezing Bit 6 = Rhyhorn Bit 7 = Rhydon | |
| 0x23d1c2 | Pokédex Obtained: \[Bits\] Bit 0 = Chansey Bit 1 = Tangela Bit 2 = Kangaskhan Bit 3 = Horsea Bit 4 = Seadra Bit 5 = Goldeen Bit 6 = Seaking Bit 7 = Staryu | |
| 0x23d1c3 | Pokédex Obtained: \[Bits\] Bit 0 = Starmie Bit 1 = Mr. Mime Bit 2 = Scyther Bit 3 = Jynx Bit 4 = Electabuzz Bit 5 = Magmar Bit 6 = Pinsir Bit 7 = Tauros | |
| 0x23d1c4 | Pokédex Obtained: \[Bits\] Bit 0 = Magikarp Bit 1 = Gyarados Bit 2 = Lapras Bit 3 = Ditto Bit 4 = Eevee Bit 5 = Vaporeon Bit 6 = Jolteon Bit 7 = Flareon | |
| 0x23d1c5 | Pokédex Obtained: \[Bits\] Bit 0 = Porygon Bit 1 = Omanyte Bit 2 = Omastar Bit 3 = Kabuto Bit 4 = Kabutops Bit 5 = Aerodactyl Bit 6 = Ronflex Bit 7 = Articuno | |
| 0x23d1c6 | Pokédex Obtained: \[Bits\] Bit 0 = Zapdos Bit 1 = Moltres Bit 2 = Dratini Bit 3 = Dragonair Bit 4 = Dragonite Bit 5 = Mewtwo Bit 6 = Mew Bit 7 = Chikorita | |
| 0x23d1c7 | Pokédex Obtained: \[Bits\] Bit 0 = Bayleef Bit 1 = Meganium Bit 2 = Cyndaquil Bit 3 = Quilava Bit 4 = Typhlosion Bit 5 = Totodile Bit 6 = Croconaw Bit 7 = Feraligatr | |
| 0x23d1c8 | Pokédex Obtained: \[Bits\] Bit 0 = Sentret Bit 1 = Furret Bit 2 = Hoothoot Bit 3 = Noctowl Bit 4 = Ledyba Bit 5 = Ledian Bit 6 = Spinarak Bit 7 = Ariados | |
| 0x23d1c9 | Pokédex Obtained: \[Bits\] Bit 0 = Crobat Bit 1 = Chinchou Bit 2 = Lanturn Bit 3 = Pichu Bit 4 = Cleffa Bit 5 = Igglybuff Bit 6 = Togepi Bit 7 = Togetic | |
| 0x23d1ca | Pokédex Obtained: \[Bits\] Bit 0 = Natu Bit 1 = Xatu Bit 2 = Mareep Bit 3 = Flaaffy Bit 4 = Ampharos Bit 5 = Bellossom Bit 6 = Marill Bit 7 = Azumarill | |
| 0x23d1cb | Pokédex Obtained: \[Bits\] Bit 0 = Sudowoodo Bit 1 = Politoed Bit 2 = Hoppip Bit 3 = Skiploom Bit 4 = Jumpluff Bit 5 = Aipom Bit 6 = Sunkern Bit 7 = Sunflora | |
| 0x23d1cc | Pokédex Obtained: \[Bits\] Bit 0 = Yanma Bit 1 = Wooper Bit 2 = Quagsire Bit 3 = Espeon Bit 4 = Embreon Bit 5 = Murkrow Bit 6 = Slowking Bit 7 = Misdreavus | |
| 0x23d1cd | Pokédex Obtained: \[Bits\] Bit 0 = Unown Bit 1 = Wobbuffet Bit 2 = Girafarig Bit 3 = Pineco Bit 4 = Forretress Bit 5 = Dunsparce Bit 6 = Gligar Bit 7 = Steelix | |
| 0x23d1ce | Pokédex Obtained: \[Bits\] Bit 0 = Snubbull Bit 1 = Granbull Bit 2 = Qwilfish Bit 3 = Scizor Bit 4 = Shuckle Bit 5 = Heracross Bit 6 = Sneasel Bit 7 = Teddiursa | |
| 0x23d1cf | Pokédex Obtained: \[Bits\] Bit 0 = Ursaring Bit 1 = Slugma Bit 2 = Magcargo Bit 3 = Swinub Bit 4 = Piloswine Bit 5 = Corsola Bit 6 = Remoraid Bit 7 = Octillery | |
| 0x23d1d0 | Pokédex Obtained: \[Bits\] Bit 0 = Delibird Bit 1 = Mantine Bit 2 = Skarmory Bit 3 = Houndour Bit 4 = Houndoom Bit 5 = Kingdra Bit 6 = Phanpy Bit 7 = Donphan | |
| 0x23d1d1 | Pokédex Obtained: \[Bits\] Bit 0 = Porygon2 Bit 1 = Stantler Bit 2 = Smeargle Bit 3 = Tyrogue Bit 4 = Hitmontop Bit 5 = Smoochum Bit 6 = Elekid Bit 7 = Magby | |
| 0x23d1d2 | Pokédex Obtained: \[Bits\] Bit 0 = Miltank Bit 1 = Blissey Bit 2 = Raikou Bit 3 = Entei Bit 4 = Suicune Bit 5 = Larvitar Bit 6 = Pupitar Bit 7 = Tyranitar | |
| 0x23d1d3 | Pokédex Obtained: \[Bits\] Bit 0 = Lugia Bit 1 = Ho-Oh Bit 2 = Celebi Bit 3 = Treecko Bit 4 = Grovyle Bit 5 = Sceptile Bit 6 = Torchic Bit 7 = Combusken | |
| 0x23d1d4 | Pokédex Obtained: \[Bits\] Bit 0 = Blaziken Bit 1 = Mudkip Bit 2 = Marshtomp Bit 3 = Swampert Bit 4 = Poochyena Bit 5 = Mightyena Bit 6 = Zigzagoon Bit 7 = Linoone | |
| 0x23d1d5 | Pokédex Obtained: \[Bits\] Bit 0 = Wurmple Bit 1 = Silcoon Bit 2 = Beautifly Bit 3 = Cascoon Bit 4 = Dustox Bit 5 = Lotad Bit 6 = Lombre Bit 7 = Ludicolo | |
| 0x23d1d6 | Pokédex Obtained: \[Bits\] Bit 0 = Seedot Bit 1 = Nuzleaf Bit 2 = Shiftry Bit 3 = Taillow Bit 4 = Swellow Bit 5 = Wingull Bit 6 = Pelipper Bit 7 = Raltz | |
| 0x23d1d7 | Pokédex Obtained: \[Bits\] Bit 0 = Kirlia Bit 1 = Gardevoir Bit 2 = Surskit Bit 3 = Masquerain Bit 4 = Shroomish Bit 5 = Breloom Bit 6 = Slakoth Bit 7 = Vigoroth | |
| 0x23d1d8 | Pokédex Obtained: \[Bits\] Bit 0 = Slaking Bit 1 = Nincada Bit 2 = Ninjask Bit 3 = Shedinja Bit 4 = Whismur Bit 5 = Loudred Bit 6 = Exploud Bit 7 = Makuhita | |
| 0x23d1d9 | Pokédex Obtained: \[Bits\] Bit 0 = Hariyama Bit 1 = Azurill Bit 2 = Nosepass Bit 3 = Skitty Bit 4 = Delcatty Bit 5 = Sableye Bit 6 = Mawile Bit 7 = Aron | |
| 0x23d1da | Pokédex Obtained: \[Bits\] Bit 0 = Lairon Bit 1 = Aggron Bit 2 = Meditite Bit 3 = Medicham Bit 4 = Electrike Bit 5 = Manectric Bit 6 = Plusle Bit 7 = Minun | |
| 0x23d1db | Pokédex Obtained: \[Bits\] Bit 0 = Volbeat Bit 1 = Illumise Bit 2 = Roselia Bit 3 = Gulpin Bit 4 = Swalot Bit 5 = Carvanha Bit 6 = Sharpedo Bit 7 = Wailmer | |
| 0x23d1dc | Pokédex Obtained: \[Bits\] Bit 0 = Wailord Bit 1 = Numel Bit 2 = Camerupt Bit 3 = Torkoal Bit 4 = Spoink Bit 5 = Grumpig Bit 6 = Spinda Bit 7 = Trapinch | |
| 0x23d1dd | Pokédex Obtained: \[Bits\] Bit 0 = Vibrava Bit 1 = Flygon Bit 2 = Cacnea Bit 3 = Cacturne Bit 4 = Swablu Bit 5 = Altaria Bit 6 = Zangoose Bit 7 = Seviper | |
| 0x23d1de | Pokédex Obtained: \[Bits\] Bit 0 = Lunatone Bit 1 = Solrock Bit 2 = Barboach Bit 3 = Whiscasth Bit 4 = Corphish Bit 5 = Crawdaunt Bit 6 = Baltoy Bit 7 = Claydol | |
| 0x23d1df | Pokédex Obtained: \[Bits\] Bit 0 = Lileep Bit 1 = Cradily Bit 2 = Anorith Bit 3 = Armaldo Bit 4 = Feebas Bit 5 = Milotic Bit 6 = Castform Bit 7 = Kecleon | |
| 0x23d1e0 | Pokédex Obtained: \[Bits\] Bit 0 = Shuppet Bit 1 = Banette Bit 2 = Duskull Bit 3 = Dusclops Bit 4 = Tropius Bit 5 = Chimecho Bit 6 = Absol Bit 7 = Wynaut | |
| 0x23d1e1 | Pokédex Obtained: \[Bits\] Bit 0 = Snorunt Bit 1 = Glalie Bit 2 = Spheal Bit 3 = Sealeo Bit 4 = Walrein Bit 5 = Clamperl Bit 6 = Huntail Bit 7 = Gorebyss | |
| 0x23d1e2 | Pokédex Obtained: \[Bits\] Bit 0 = Relicanth Bit 1 = Luvdisc Bit 2 = Bagon Bit 3 = Shelgon Bit 4 = Salamence Bit 5 = Beldum Bit 6 = Metang Bit 7 = Metagross | |
| 0x23d1e3 | Pokédex Obtained: \[Bits\] Bit 0 = Regirock Bit 1 = Regice Bit 2 = Registeel Bit 3 = Latias Bit 4 = Latios Bit 5 = Kyogre Bit 6 = Groudon Bit 7 = Rayquaza | |
| 0x23d1e4 | Pokédex Obtained: \[Bits\] Bit 0 = Jirachi Bit 1 = Deoxys Bit 2 = Turtwig Bit 3 = Grotle Bit 4 = Torterra Bit 5 = Chimchar Bit 6 = Monferno Bit 7 = Infernape | |
| 0x23d1e5 | Pokédex Obtained: \[Bits\] Bit 0 = Piplup Bit 1 = Prinplup Bit 2 = Empoleon Bit 3 = Starly Bit 4 = Staravia Bit 5 = Staraptor Bit 6 = Bidoof Bit 7 = Bibarel | |
| 0x23d1e6 | Pokédex Obtained: \[Bits\] Bit 0 = Kricketot Bit 1 = Kricketune Bit 2 = Shinx Bit 3 = Luxio Bit 4 = Luxray Bit 5 = Budew Bit 6 = Roserade Bit 7 = Cranidos | |
| 0x23d1e7 | Pokédex Obtained: \[Bits\] Bit 0 = Rampardos Bit 1 = Shieldon Bit 2 = Bastiodon Bit 3 = Burmy Bit 4 = Wormadam Bit 5 = Mothim Bit 6 = Combee Bit 7 = Vespiquen | |
| 0x23d1e8 | Pokédex Obtained: \[Bits\] Bit 0 = Pachirisu Bit 1 = Buizel Bit 2 = Floatzel Bit 3 = Cherubi Bit 4 = Cherrim Bit 5 = Shellos Bit 6 = Gastrodon Bit 7 = Ambipom | |
| 0x23d1e9 | Pokédex Obtained: \[Bits\] Bit 0 = Drifloon Bit 1 = Drifblim Bit 2 = Buneary Bit 3 = Lopunny Bit 4 = Mismagius Bit 5 = Honchkrow Bit 6 = Glameow Bit 7 = Purugly | |
| 0x23d1ea | Pokédex Obtained: \[Bits\] Bit 0 = Chingling Bit 1 = Stunky Bit 2 = Skuntank Bit 3 = Bronzor Bit 4 = Bronzong Bit 5 = Bonsly Bit 6 = Mime Jr. Bit 7 = Happiny | |
| 0x23d1eb | Pokédex Obtained: \[Bits\] Bit 0 = Chatot Bit 1 = Spiritomb Bit 2 = Gible Bit 3 = Gabite Bit 4 = Garchomp Bit 5 = Munchlax Bit 6 = Riolu Bit 7 = Lucario | |
| 0x23d1ec | Pokédex Obtained: \[Bits\] Bit 0 = Hippopotas Bit 1 = Hippowdon Bit 2 = Skorupi Bit 3 = Drapion Bit 4 = Croagunk Bit 5 = Toxicroak Bit 6 = Carnivine Bit 7 = Finneon | |
| 0x23d1ed | Pokédex Obtained: \[Bits\] Bit 0 = Lumineon Bit 1 = Mantyke Bit 2 = Snover Bit 3 = Abomasnow Bit 4 = Weavile Bit 5 = Magnezone Bit 6 = Lickilicky Bit 7 = Rhyperior | |
| 0x23d1ee | Pokédex Obtained: \[Bits\] Bit 0 = Tangrowth Bit 1 = Electivire Bit 2 = Magmortar Bit 3 = Togekiss Bit 4 = Yanmega Bit 5 = Leafeon Bit 6 = Glaceon Bit 7 = Gliscor | |
| 0x23d1ef | Pokédex Obtained: \[Bits\] Bit 0 = Mamoswine Bit 1 = Porygon-Z Bit 2 = Gallade Bit 3 = Probopass Bit 4 = Dusknoir Bit 5 = Froslass Bit 6 = Rotom Bit 7 = Uxie | |
| 0x23d1f0 | Pokédex Obtained: \[Bits\] Bit 0 = Mesprit Bit 1 = Azelf Bit 2 = Dialga Bit 3 = Palkia Bit 4 = Heatran Bit 5 = Regigigas Bit 6 = Giratina Bit 7 = Cresselia | |
| 0x23d1f1 | Pokédex Obtained: \[Bits\] Bit 0 = Phione Bit 1 = Manaphy Bit 2 = Darkrai Bit 3 = Shaymin Bit 4 = Arceus Bit 5 = Victini Bit 6 = Snivy Bit 7 = Servine | |
| 0x23d1f2 | Pokédex Obtained: \[Bits\] Bit 0 = Serperior Bit 1 = Tepig Bit 2 = Pignite Bit 3 = Emboar Bit 4 = Oshawott Bit 5 = Dewott Bit 6 = Samurott Bit 7 = Patrat | |
| 0x23d1f3 | Pokédex Obtained: \[Bits\] Bit 0 = Watchog Bit 1 = Lillipup Bit 2 = Herdier Bit 3 = Stoutland Bit 4 = Purrloin Bit 5 = Liepard Bit 6 = Pansage Bit 7 = Simisage | |
| 0x23d1f4 | Pokédex Obtained: \[Bits\] Bit 0 = Pansear Bit 1 = Simisear Bit 2 = Panpour Bit 3 = Simipour Bit 4 = Munna Bit 5 = Musharna Bit 6 = Pidove Bit 7 = Tranquill | |
| 0x23d1f5 | Pokédex Obtained: \[Bits\] Bit 0 = Unfezant Bit 1 = Blitzle Bit 2 = Zenstrika Bit 3 = Roggenrola Bit 4 = Boldore Bit 5 = Gigalith Bit 6 = Woobat Bit 7 = Swoobat | |
| 0x23d1f6 | Pokédex Obtained: \[Bits\] Bit 0 = Drilbur Bit 1 = Excadrill Bit 2 = Audino Bit 3 = Timburr Bit 4 = Gurdurr Bit 5 = Conkeldurr Bit 6 = Tumpole Bit 7 = Palpitoad | |
| 0x23d1f7 | Pokédex Obtained: \[Bits\] Bit 0 = Seismitoad Bit 1 = Throh Bit 2 = Sawk Bit 3 = Sewaddle Bit 4 = Swadloon Bit 5 = Leavanny Bit 6 = Yenipede Bit 7 = Whirlpede | |
| 0x23d1f8 | Pokédex Obtained: \[Bits\] Bit 0 = Scolipede Bit 1 = Cottonee Bit 2 = Whimsicott Bit 3 = Petilil Bit 4 = Lilligant Bit 5 = Basculin Bit 6 = Sandile Bit 7 = Krokorok | |
| 0x23d1f9 | Pokédex Obtained: \[Bits\] Bit 0 = Krookodile Bit 1 = Darumaka Bit 2 = Darmanitan Bit 3 = Maractus Bit 4 = Dwebble Bit 5 = Crustle Bit 6 = Scraggy Bit 7 = Scrafty | |
| 0x23d1fa | Pokédex Obtained: \[Bits\] Bit 0 = Sigilyph Bit 1 = Yamask Bit 2 = Cofagrigus Bit 3 = Tirtouga Bit 4 = Carracosta Bit 5 = Archen Bit 6 = Archeops Bit 7 = Trubbish | |
| 0x23d1fb | Pokédex Obtained: \[Bits\] Bit 0 = Garbodor Bit 1 = Zorua Bit 2 = Zoroark Bit 3 = Minccino Bit 4 = Cinccino Bit 5 = Gothita Bit 6 = Gothorita Bit 7 = Gothitelle | |
| 0x23d1fc | Pokédex Obtained: \[Bits\] Bit 0 = Solosis Bit 1 = Duosion Bit 2 = Reuniclus Bit 3 = Ducklett Bit 4 = Swanna Bit 5 = Vanillite Bit 6 = Vanillish Bit 7 = Vanilluxe | |
| 0x23d1fd | Pokédex Obtained: \[Bits\] Bit 0 = Deerling Bit 1 = Sawsbuck Bit 2 = Emolga Bit 3 = Karrablast Bit 4 = Escavalier Bit 5 = Foongus Bit 6 = Amoonguss Bit 7 = Frillish | |
| 0x23d1fe | Pokédex Obtained: \[Bits\] Bit 0 = Jellicent Bit 1 = Alomomola Bit 2 = Joltik Bit 3 = Galvantula Bit 4 = Ferroseed Bit 5 = Ferrothorn Bit 6 = Klink Bit 7 = Klang | |
| 0x23d1ff | Pokédex Obtained: \[Bits\] Bit 0 = Klinklang Bit 1 = Tynamo Bit 2 = Eelektrik Bit 3 = Eelektross Bit 4 = Elgyem Bit 5 = Beheeyem Bit 6 = Litwick Bit 7 = Lampent | |
| 0x23d200 | Pokédex Obtained: \[Bits\] Bit 0 = Chandelure Bit 1 = Axew Bit 2 = Fraxure Bit 3 = Haxorus Bit 4 = Cubchoo Bit 5 = Beartic Bit 6 = Cryogonal Bit 7 = Shelmet | |
| 0x23d201 | Pokédex Obtained: \[Bits\] Bit 0 = Accelgor Bit 1 = Stunfisk Bit 2 = Mienfoo Bit 3 = Mienshao Bit 4 = Druddugon Bit 5 = Golett Bit 6 = Golurk Bit 7 = Pawniard | |
| 0x23d202 | Pokédex Obtained: \[Bits\] Bit 0 = Bisharp Bit 1 = Bouffalant Bit 2 = Rufflet Bit 3 = Braviary Bit 4 = Vullaby Bit 5 = Mandibuzz Bit 6 = Heatmor Bit 7 = Durant | |
| 0x23d203 | Pokédex Obtained: \[Bits\] Bit 0 = Deino Bit 1 = Zweilous Bit 2 = Hydreigon Bit 3 = Larvesta Bit 4 = Volcarona Bit 5 = Cobalion Bit 6 = Terrakion Bit 7 = Virizion | |
| 0x23d204 | Pokédex Obtained: \[Bits\] Bit 0 = Tornadus Bit 1 = Thundurus Bit 2 = Reshiram Bit 3 = Zekrom Bit 4 = Landorus Bit 5 = Kyurem Bit 6 = Keldeo Bit 7 = Meloetta | |
| 0x23d205 | Pokédex Obtained: \[Bits\] Bit 0 = Genesect | |
| 0x23d6dd | Repel Steps: \[8-Bit\] | |
| 0x23d7ae | \[8bit\] Subway car # | |
| 0x23d8b0 | \[8bit\] Types of records saved bit4 - Super single train activated in vs recorder bit5 - Super double train activated in vs recorder bit6 - Super multi activated in Vs recorder | |
| 0x23d8c6 | \[16bit\] Single train subway win records current | |
| 0x23d8c8 | \[16bit\] Double train subway win records current | |
| 0x23d8ca | \[16bit\] Multi Train subway win records current (with trainer) | |
| 0x23d8cc | current streak of 7 battles (multi) | |
| 0x23d8d0 | \[16bit\] High Score of Super Single Subway | |
| 0x23d8d2 | \[16bit\] High Score of Super Double Subway | |
| 0x23d8d4 | \[16bit\] High Score of Super Multi Subway (with trainer) | |
| 0x23d8d8 | Current streak of 7 battles (single) \=1 for battles 1-7 \=2 for battles 8-14 \=3 for battles 15-21 | |
| 0x23d8da | \[8bit\] Current streak of 7 battles (double) \=1 for battles 1-7 \=2 for battles 8-14 \=3 for battles 15-21 | |
| 0x23d8dc | \[8bit\] current streak of 7 battles (multi) \=1 for battles 1-7 \=2 for battles 8-14 \=3 for battles 15-21 | |
| 0x23d8e2 | 16bit Highest Streak of Super Single Subway | |
| 0x23d8e4 | \[16bit\] Current streak of 7 battles (super double) | |
| 0x23d8e6 | \[16bit\] Current streak of 7 battles (super multi) | |
| 0x23f5ae | \[16bit\] Battle Institute Rank Points 0-999 - Beginner 1000 - 1999 - Novice 2000 - 2999 - Normal 3000 - 3999 - Super 4000 - 4999 - Hyper 5000 - 5999 - Elite 6000 - 9999 - Master | |
| 0x24f90c | Map ID: \[16-Bit\] 0007 = Striation Gym Leader Room 0013 = Nacrene Gym Leader Room 001D = Castelia Gym Leader Room 003F = Nimbasa Gym Leader Room 0061 = Driftveil Gym Leader Room 006C = Mistralton Gym Leader Room 0072 = Icirrus Gym Leader Room 0079 = Opelucid Gym Leader Room 0187=At home, upstairs 018d=Accumula Town | |
| 0x24f910 | \[32bit\] Player x coordinates | |
| 0x24f918 | \[32bit\] Player y coordinates | |
| 0x24f92c | Player's Name: \[16-Bit\] | |
| 0x24f92e | Player's Name: \[16-Bit\] | |
| 0x24f930 | Player's Name: \[16-Bit\] | |
| 0x24f932 | Player's Name: \[16-Bit\] | |
| 0x24f934 | Player's Name: \[16-Bit\] | |
| 0x24f936 | Player's Name: \[16-Bit\] | |
| 0x24f938 | Player's Name: \[16-Bit\] | |
| 0x24f949 | \[8bit\] Boy or Girl 0x00 - Boy 0x01 - Girl | |
| 0x24f9bc | \[8bit\] Current Season 0=Spring 1=Summer 2=Autumn 3=Winter | |
| 0x258230 | Music ID: \[16-Bit\] 46C = Gym Leader Battle 47B = Gym Leader Battle (Last Pokémon) 47A = Low HP theme 518 = Catch theme | |
| 0x258ba4 | Village Bridge Flute 00 = Activated 01 = Not Activated | |
| 0x258bdc | Village Bridge Beatbox 00 = Activated 01 = Not Activated | |
| 0x258c14 | Village Bridge Guitar 00 = Activated 01 = Not Activated | |
| 0x258c4c | Village Bridge Lyrics 00 = Activated 01 = Not Activated | |
| 0x2598e6 | \[8bit\] Battle Institute Type bit0 off - Single Bit0 on - Double | |
| 0x2598ee | Rank | |
| 0x2602b1 | \[8bit\] Subway Mode 0x00 - Single 0x01 - Double 0x02 - Multi 0x03 - Wifi train? 0x04 - Wifi Train (again) 0x05 - Super Single 0x06 - Super Double 0x07 - Super Multi | |
| 0x2602b6 | \[8bit\] Subway streak | |
| 0x260ab4 | Subway Mode | |
| 0x260aba | Battle Subway: Win Steak | |
| 0x26da0e | Turns? | |
| 0x26e38c | In Battle: \[16-Bit\] Player's Pokemon Health | |
| 0x2befc4 | In Battle: \[8-Bit\] Player's Pokemon Level | |
| 0x2befc8 | In Battle: \[8-Bit\] 08 = Player's Idle 09 = Player's Damaged | |
| 0x2bf044 | In Battle: \[8-Bit\] Opponent's Pokemon Level | |
| 0x2bf048 | In Battle: \[8-Bit\] 00 = Faint 08 = Opponent Idle 09 = Opponent Damaged | |
| 0x3ffa88 | Rom Header: \[8-Bit\] 42 = Black 57 = White | |
