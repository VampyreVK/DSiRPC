

https://projectpokemon.org/home/docs/other/notable-breakpoints-r31/

This page contains RAM addresses to various interesting and useful processes of GBA and DS Pokemon games.

Breakpoints can be set at these addresses.

## Inspiration

This page is inspired by tsanth's thread with the same name on GameFAQs: [[1]](http://boards.gamefaqs.com/gfaqs/genmessage.php?board=925602&topic=40532445)

## Pokemon DPP (U)

|DP RAM Address|Pl RAM Address|Description|Discovered by|
|---|---|---|---|
|02000C54|02000C88|Main()|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020064F0|02006AA4|Load from NARC (r1=archive_id, r2=file_id)|[Alpha](https://projectpokemon.org/wiki/index.php?title=Alpha&action=edit&redlink=1 "Alpha (page does not exist)")|
|02000FB0|02001034|Begin Seed Calculation Routine|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02005FDC|02006590|Load Overlay (r0=overlay_id)|[Alpha](https://projectpokemon.org/wiki/index.php?title=Alpha&action=edit&redlink=1 "Alpha (page does not exist)")|
|0201B9E0|0201D2DC|Set [PRNG](https://projectpokemon.org/wiki/index.php?title=PRNG&action=edit&redlink=1 "PRNG (page does not exist)") seed|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0201B9EC|0201D2E8|PRNG|[loadingNOW](https://projectpokemon.org/wiki/index.php?title=LoadingNOW&action=edit&redlink=1 "LoadingNOW (page does not exist)"), [tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0201BA10|0201D30C|Alternate RNG used in some cases: Examples, PID generation for mystery gift pokemon, recalculating a PID after a failed shiny check, number which determines swarm pokemon and great marsh pokemon|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|0201BA1C|0201D318|Set [IRNG](https://projectpokemon.org/wiki/index.php?title=IRNG&action=edit&redlink=1 "IRNG (page does not exist)") Seed|[mingot, arcee](https://projectpokemon.org/wiki/index.php?title=Mingot,_arcee&action=edit&redlink=1 "Mingot, arcee (page does not exist)")|
|02038B70|0203E778|Script Handler|[loadingNOW](https://projectpokemon.org/wiki/index.php?title=LoadingNOW&action=edit&redlink=1 "LoadingNOW (page does not exist)")|
||0203E7D2|Loads address for a command then branches to that address|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|02042FB4|0204BAFC|ARNG call for PID of Wondercard pokemon|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02042FBA|0204BB02|Loads PID from wondercard to r0|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02042FC8|0204BB10|First Shiny Check call during the generation of some wondercard pokemon|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02042FD0|0204BB18|Beginning of loop that makes sure you do not get a shiny wondercard pokemon (in some cases)|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0204305E|0204BBA6|PRNG call for first set of Wondercard pokemon IVs|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0204309C|0204BBE4|PRNG call for second set of Wondercard pokemon IVs|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||02050958|Run item routines|Mikelan98|
||020535E8|Use of Journal item entrypoint|Mikelan98|
||02068884|Use of Bicycle item entrypoint|Mikelan98|
||0205EABC|Load player's X coord to r0|Mikelan98|
||0205EAC8|Load player's Y coord to r0|Mikelan98|
|0205DED4||Create chain set (not sure about address in tsanth's thread it said 205DED|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [loadingNOW](https://projectpokemon.org/wiki/index.php?title=LoadingNOW&action=edit&redlink=1 "LoadingNOW (page does not exist)")|
|0205DF42||End of Create chain set routine|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [loadingNOW](https://projectpokemon.org/wiki/index.php?title=LoadingNOW&action=edit&redlink=1 "LoadingNOW (page does not exist)")|
||02069820|Determines the 4 grassy patches that will move in Pokeradar and determines whether they are in a tall grass tile or not|Mikelan98|
||02069A00|Use of Pokeradar item entrypoint|Mikelan98|
|0205E40C|02069B00|Pokeradar Routine|[loadingNOW](https://projectpokemon.org/wiki/index.php?title=LoadingNOW&action=edit&redlink=1 "LoadingNOW (page does not exist)"), [tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02068AAC|02075E38|Shiny Check, used to decide what sprite to show for a pokemon and to make sure dynamic PID mystery gift pokemon are not shiny as well as preventing manaphy from hatching shiny in some cases.|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||02075C86|128 step RNG advancement|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||0207760E|Poketch check @ daycare screen|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0206A90C|02078780|Begin Calculation of [Pokemon ID](https://projectpokemon.org/wiki/index.php?title=Pokemon_ID&action=edit&redlink=1 "Pokemon ID (page does not exist)") for alternate forms.|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)"), [arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||0207CF48|Use item and load item data|Mikelan98|
|020EBC80|020E1F6C|Division routine; R0= R0 / R1, R1=R0%R1|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)"), [SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|020F355C|020EAC58|Pointer to Begin Routine for Script Command 0000|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
||020EB974|Pointer to Begin Routine for Script Command 0347|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
||020F0CCA|Item data slots|Mikelan98|
|021C4D48|021BFB14|PRNG State|[Kazo](https://projectpokemon.org/wiki/index.php?title=Kazo&action=edit&redlink=1 "Kazo (page does not exist)")|
|021C4D4C|021BFB18|Mersenne Twister Lookup Table|[Kazo](https://projectpokemon.org/wiki/index.php?title=Kazo&action=edit&redlink=1 "Kazo (page does not exist)")|
|021F4DA8||Beginning of [Honey Tree](https://projectpokemon.org/wiki/Honey_Tree "Honey Tree") Routine|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|021F4EE4||Determines a value from 0-3 to use to determine which list will be used and how the shake value is calculated. If 0, slathering fails and not pokemon will show up.|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|021F4F44||Determines a number from 0-5 that represents which pokemon will be encountered in a honey tree.|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|021F4F98||Determines which list will be used by (value determined by 021F4EE4) - 1 (its not done this way, but is equivalent)|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|021F4FAC||Determines a number from 0-3 that represents how much a [Honey Tree](https://projectpokemon.org/wiki/Honey_Tree "Honey Tree") will shake|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|021F5138|021EFF4C|Returns 1 if the current tree being slathered is a [Munchlax Tree](https://projectpokemon.org/wiki/index.php?title=Munchlax_Tree&action=edit&redlink=1 "Munchlax Tree (page does not exist)") and 0 otherwise.|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
|02211E60||Set [GRNG](https://projectpokemon.org/wiki/GTS_protocol#Payload "GTS protocol") seed|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|02211E70||[GRNG](https://projectpokemon.org/wiki/GTS_protocol#Payload "GTS protocol")|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|0223BA10||Movement Handler Start|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0223BA46||"Am I on grass?" check|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0223BAD4||Wild Encounter Check|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0223BB2E||Pair-battle (NPC partner) check|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0223BD1C||Movement Handler END|[tsanth](https://projectpokemon.org/wiki/index.php?title=Tsanth&action=edit&redlink=1 "Tsanth (page does not exist)")|
|0223C1EE|022377A2|Pokeball catching routine|[tsanth, arcee](https://projectpokemon.org/wiki/index.php?title=Tsanth,_arcee&action=edit&redlink=1 "Tsanth, arcee (page does not exist)")|
|0223C5B8||Start of Encounter Table Lookup Handler|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|0223C66A||Start of Water (Sweet Scent/Surfing) Encounter Table Lookup Handler|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|0223C6A0||Start of Water (Fishing) Encounter Table Lookup Handler. There are 3 branches for each of the rods in this routine with different results for old and good/super.|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
||022417F4|Encounter- terrain check|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||02241848|Encounter- motion mod|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
||022479E6|Call to get ID routine (result in r0)|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|
||0224E920|Start of Frozen Handler|[SCV](https://projectpokemon.org/wiki/index.php?title=SCV&action=edit&redlink=1 "SCV (page does not exist)")|

0224190A - ESV calc 02241B28 - nature calc (probably)

## Pokémon HGSS (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|02000CA4|Main()|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02007508|Load from NARC (r0=offset, r1=archive_id, r2=file_id)|[Alpha](https://projectpokemon.org/wiki/index.php?title=Alpha&action=edit&redlink=1 "Alpha (page does not exist)")|
|0201FD44|PRNG advancement routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201FD68|Alternate(simpler) PRNG|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203FE24|Script Handler - Read parameter of command (parameter saved in r0)|Mikelan98|
|0204036C|Script Handler - Read RAM offset of variable in r1 (offset saved in r0)|Mikelan98|
|020403A4|Script Handler - Read value of variable in r1 (value saved in r0)|Mikelan98|
|0204BFF0|Wondercard pokemon generation- full routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02050544|Run item routines|Mikelan98|
|02061E2A|NPC movement|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0206C9D8|International shiny PID generation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02070068|Shiny check|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020D34B0|Make wondercard PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020D3A38|Disable slow IRQ|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020D3A4C|Enable slow IRQ|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020F2998|Signed divmod()|?|
|020F2BA4|Unsigned divmod()|?|
|020F6BC8|Map headers table (Wild, Tileset, X-coord, Y-coord, Matrix, Scripts, Level scripts, Texts, Music 1, Music 2, Events, Name, Name style, Weather, Camera, ?, Allowed actions)|Mikelan98|
|02100182|Item data slots|Mikelan98|
|0210F6CC|Mersenne Twister lookup table counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D15A8|PRNG State|[Kazo](https://projectpokemon.org/wiki/index.php?title=Kazo&action=edit&redlink=1 "Kazo (page does not exist)")|
|021D15AC|Mersenne Twister lookup table|[Kazo](https://projectpokemon.org/wiki/index.php?title=Kazo&action=edit&redlink=1 "Kazo (page does not exist)")|
|021E19DC|Upper half of wondercard PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022074A2|Overworld Sprite Control Table|[Alpha](https://projectpokemon.org/wiki/index.php?title=Alpha&action=edit&redlink=1 "Alpha (page does not exist)")|
|022440A0|Pickup / Honey Gather handler|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|02246B24|Start of Water (Fishing) Encounter Table Lookup Handler [[2]](http://www.smogon.com/forums/showpost.php?p=2564048&postcount=215)|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|02246FCC|Fishing decision|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02247228|Pokéball catching routine|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|022475F2|Partial encounter calc- movement modifier|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|0224767A|Partial encounter calc- ability/item modifier|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02247698|Encounter slots|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02247720|Start of Water (Sweet Scent/Surfing) Encounter Table Lookup Handler [[3]](http://www.smogon.com/forums/showpost.php?p=2564048&postcount=215)|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|022477C0|Headbutt tree encounter slots (Post-National Dex)|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|022483C4|Partial encounter calc- roamer modifier|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|02108514|Starter species in RAM(in the decompressed arm9 @ 108514)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0226CC7C|Type Effectiveness Table (overlay 0012)|[Alpha](https://projectpokemon.org/wiki/index.php?title=Alpha&action=edit&redlink=1 "Alpha (page does not exist)")|

## Pokémon BW (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|01FF8000|ITCM start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|01FF80F0|ARM9 IRQ Handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005124|main() function- infinite main/busy loop that runs the game starts at 02005166|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200520C|VBlank handler function|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020056D0|Set up both main RNGs for use|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020056EC|PRNG advancement routine 1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005728|PRNG advancement routine 2|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200852C|Store sidtid as uint|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201778C|IV creation routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02017EF4|Shiny check routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02018746|PID type decision|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02018788|Shiny prevention routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02019A6C|PKM + RAM encryption|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02035F50|Input handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203EFE0|memcmp()- memory compare: 2 pointers and length of comparison(in bytes))|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203F04C|Set init MT seed (seed = init rng >> 32)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203F078|ARNG(same as gen 4)- build initial MT seed table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203F0C0|Mersenne Twister seed table handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203F270|Initial Seed Creation Routine|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|
|0203F374|.sav encryption|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020592E8|MD5 hashing routine for wifi|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0207FD4C|VRAM bank control handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02082BE4|Takes 3 arguments: pointer to start of data write, length(in bytes) of data to write, uint to write multiple times- used constantly for clearing freed memory|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02082D5C|memcpy32()- accepts pointer to data start, pointer to copy start, and a length in bytes to copy|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02085D54|DSi Detection Routine|[chiizu](https://projectpokemon.org/wiki/index.php?title=Chiizu&action=edit&redlink=1 "Chiizu (page does not exist)")|
|02088A98|Date/time switch statement- used to grab pieces of the date and time and convert them to hex|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02088E74|Convert BCD->hex, for RTC|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020946AC|Metrowerks ARM-provided lib rand- used for DS-to-DS handshake|[XFR](https://projectpokemon.org/wiki/index.php?title=XFR&action=edit&redlink=1 "XFR (page does not exist)"),[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209C0C4|Signed divmod- r0/r1, result in r0; r0%r1, result in r1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209C2C8|Unsigned divmod- r0/r1, result in r0; r0%r1, result in r1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020A1B50|Model/texture definitions/positioning data|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020AA1C4|RNG state pointer|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02146292|Pokemon to be encountered|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02146974|Pointer to the struct for the current heap being used|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02146A18|Mersenne Twister seed table pointer|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02146A2C|u32 date_time[8] (in hex)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02150920|SVC mode stack location for card reads/writes|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02151260|SWI/SVC mode stack|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02168844|rand(0xFFFFFFFF) / 0xFFFF|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02168A52|ID generation for Battle Subway partner|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021763DC|Inside probability loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021763F8|Probability routine- influences starting frame/seed|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02176444|Outside probability loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02176C6C|Probability table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02193914|White Forest Trainer # Counter- returns # of trainers in White Forest|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A9370|Pre-battle setup(battle test, etc)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A948C|Double battle test|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A9DB2|0x80000000 OR PID decision routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A9DE8|((rand() * 0xFFFF) >> 32) /0x290 -> function is called quite a bit for multiple calcs|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A9DF8|Fishing decision|[arcee](https://projectpokemon.org/wiki/index.php?title=Arcee&action=edit&redlink=1 "Arcee (page does not exist)")|
|021AA41C|Battle test/decision|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021AA43A|Battle test|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021AA44C|White Forest Battle Decision Routine- return 0 if no battle, 1 if there's a battle|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021AA700|((rand() * 0xFFFF) >> 32) /0x290 -> seems to only be used for battle tests|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BC4F8|Player setup on new game|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BC50A|Make IDs|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C0A6C|Battle routine(setup)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C390C|Complete breeding routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C4048|International breeding PID generation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C6C18|Damage formula routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021F6388|Battle PRNG State|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|02215374|Mersenne Twister Lookup Table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02215D34|Mersenne Twister Lookup Table Counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02216244|PRNG State|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221BBD0|Start of save data in RAM(when saving, all relevant data is written here, then cart RAM, then .sav)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022394E0|Date/time in hex - uint array|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223C9D0|Daycare pokemon 1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223CAB4|Daycare pokemon 2|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223D8CC|BP Counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0224120C|Wifi RNG|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02250030|Encounter slots in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02257030|Step Counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02257034|Shaking Patch Step Counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0226DC5A|Move Consecutive Use Counter (Wild Battle)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|0226DC66|Protect Consecutive Turn Counter (Wild Battle)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|0226E70E|Move Consecutive Use Counter (Trainer Battle)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|0226E71A|Protect Consecutive Turn Counter (Trainer Battle)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|02274302|Move Decision Dump (Wild Battle)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|022BC734|Are there trainers in White Forest? (bool)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0233F004|Egg step counter|[ToastPlusOne](https://projectpokemon.org/wiki/index.php?title=ToastPlusOne&action=edit&redlink=1 "ToastPlusOne (page does not exist)")|
|02FE0000|DTCM start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FE0020|Interrupt handler lookup table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FE3780|Main(user/system mode) stack start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FE3F80|IRQ mode stack start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FE3FC0|Supervisor mode stack start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FFFC3C|Vertical blank counter buffer|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|
|02FFFDE8|RTC buffer(char rtc[8])|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|
|037FBCEC|ARM7 IRQ Handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02017638|Pokemon creation routine(makePKM)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02019AB8|PKM checksum generation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02019C54|PKM block shuffling|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203F3A0|Encrypt SAV, battle video, mystery gift|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)"), [Codr](https://projectpokemon.org/wiki/index.php?title=Codr&action=edit&redlink=1 "Codr (page does not exist)"), [XFR](https://projectpokemon.org/wiki/index.php?title=XFR&action=edit&redlink=1 "XFR (page does not exist)")|
|02150E6C|Graphics bank assignment struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214EA70|Sound archive info struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02006984|Play PKM cry- in battle and otherwise|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02011298|Script handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0224FED4|Expanded heap memory allocation struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02169024|Runs everything that has to happen after midnight|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200D440|Swarm calculation and storage|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02151350|Tick system|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0272E9E8|DSi library overlay|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021E6184|Moonlight modifier picker|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

## Pokémon BW (J)

|RAM Address|Description|Discovered by|
|---|---|---|
|02005124|Main()|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022151D4|Mersenne Twister Lookup Table|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|
|02215B94|Mersenne Twister Lookup Table Counter|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|022160A8|PRNG State|[Kazo](https://projectpokemon.org/wiki/index.php?title=Kazo&action=edit&redlink=1 "Kazo (page does not exist)")|
|02FFFC3C|Delay|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|
|02FFFDE8|Date|[OmegaDonut](https://projectpokemon.org/wiki/index.php?title=OmegaDonut&action=edit&redlink=1 "OmegaDonut (page does not exist)")|

(All offsets are White offsets. Black offsets are White offset minus 0x20)

## Pokémon Emerald (J)

|RAM Address|Description|Discovered by|
|---|---|---|
|02024664|Frame Counter|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|03005AE0|PRNG State|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|08000248|IRQ setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080003A4|Main loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080005E4|Keypress handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000758|VBlank interrupt|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806F050|PRNG Advancement Routine|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|080B413A|Feebas setup routine on finding a Feebas tile|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08295E87|Signed division|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|
|08296518|Modulus routine- r0 % r1, return result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08297D6C|memset|[magical](https://projectpokemon.org/wiki/index.php?title=Magical&action=edit&redlink=1 "Magical (page does not exist)")|

## Pokémon Emerald (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|02020000|Timer1 storage on TID creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020249C0|Main RNG Frame counter|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|03000DC0|RTC array buffer(char rtc[8])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|03000E20|Directional movement counters(possibly per frame)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|030022E0|Timer PRNG Initial State (Egg PIDs)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|03002750|IRQ Handler (user mode)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|03005D80|PRNG State|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|03005D84|Timer RNG Current Seed (Egg PIDs)|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|08000248|IRQ setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080003A4|Main loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080005E4|Keypress handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000738|VBlank interrupt callback|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000988|Memblock header setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000B1C|Malloc init|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000B38|Declare memblock(malloc()?)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B49E2|Feebas setup routine on finding a Feebas tile|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B4AC8|Encounter Slot|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B4C74|Set level|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B4E2A|Sync (bool)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B4E4C|Nature Setup/Decision (skip "if(sync())")|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080B5144|Battle Test|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08067BF8|Roamer creation start|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08067E96|PKM Building Routine (test temp PIDs, make IVs on success)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806D088|Get nature from tempPID(pass tempPID as an arg, return nature value)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806F5CC|PRNG Advancement Routine|[mingot](https://projectpokemon.org/wiki/index.php?title=Mingot&action=edit&redlink=1 "Mingot (page does not exist)")|
|0817759E|ARNG|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|082E7BE0|Modulus routine- r0 % r1, return result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|082E7B68|Division routine- r0 / r1, return result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|082E7540|Division routine- r0 / r1, return result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08070AC4|Make bred pokemon|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080701E0|Make bred PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020241F0|Damage storage- base dmg, etc|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08070266|Inheritance- bugged to not prevent inheriting the same IV multiple times|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08070218|Inheritance check- make sure the same IV isn't inherited multiple times- bugged due to the wrong argument being passed to it|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806AD9C|Set PKM data field|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806A674|Read PKM data field|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806A518|Get PKM data field|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806ACAC|Write PKM data field|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806DCB4|Pokerus handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0806DEC4|Pokerus spread|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|03004134|IME store|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

## Pokémon Ruby / Sapphire (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|02024D1C|Quick Claw Determination|[FractalFusion](https://projectpokemon.org/wiki/index.php?title=FractalFusion&action=edit&redlink=1 "FractalFusion (page does not exist)")|
|020287E4|Egg Creation Step Counter|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|03004818|PRNG State|Multiple|
|03000460|RTC|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0800024C|Main loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080003E4|Initial seed creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000428|Keypress handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0803AADC|PID creation routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08040048|Pokerus handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08040EA4|Seed set routine, post creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08040E84|rand()|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08084AA6|Feebas decision|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|081E0770|Interrupts/SWIs|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080421B0|Make bred PKM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|080418F0|Build bred PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|081E0E20|Division r0/r1, result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|081E0E98|Modulus r0%r1, result in r0|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08041960|Inheritance check- insure no duplicate IVs|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

## Pokémon FireRed / LeafGreen (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|02020000|Timer1 storage on initial seed creation|[flovv, Bond697](https://projectpokemon.org/wiki/index.php?title=Flovv,_Bond697&action=edit&redlink=1 "Flovv, Bond697 (page does not exist)")|
|03005000|PRNG State|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000558|Turn on Timer1 @ TM1CNT_H = 0x80|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000564|Grab and return the value of Timer1 for use in seeding|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08000570|Turn off Timer1 @ TM1CNT_H = 0x0 and store the grabbed value to 0x02020000|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0803DA54|Make PKM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08044EC8|PRNG Advancement Routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02023D50|Damage store|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

## Pokémon Ruby Debug Version (G)

|RAM Address|Description|Discovered by|
|---|---|---|
|02024F54|P1 successive Protects||
|030043D3|Turns in battle||
|030046F0|CPU Active Sleep counter||
|030048F8|PRNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08045324|PRNG Advancement Routine(rand())|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08085CEC|ARNG Advancement Routine|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|08220E5E|Protect success rates||

## Pokémon B2W2 (J)

|RAM Address|Description|Discovered by|
|---|---|---|
|02005124|TwlMain|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005748|RNG advancement routine 1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005784|RNG advancement routine 2|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020158E8|Script handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02043BE8|Mersenne Twister setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02043C38|Mersenne Twister handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02043DA4|Seed building function|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A0E30|Create wild PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FE6E8|Mersenne Twister table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0276FA88|DSi Mersenne Twister table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FF0A8|Mersenne Twister table counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FF5D8|RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02770978|DSi RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021707DC|Probability table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0216FCE0|Probability loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0216FCFC|Inside probability loop|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B188|Encounter slots in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021DD22C|Battle RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221D3A4|Item slots in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022268D1|Repel counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022260A4|Cash|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022229A4|Total steps|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223AEB4|Current game(loaded save) step counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0208D574|Unsigned divmod|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0208D368|Signed divmod|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209D46C|RNG pointer|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A0E9A|0x80000000 PID-OR decision|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A1994|Shaking patch generation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0219FAE4|Hardcoded trainer name length|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0219CB1C|Hardcoded wild pokemon name length|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D9DEC|Data entry setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BF190|Hardcoded starter pokemon name length|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02249BD0|Script info struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020825B8|Abort on bad allocation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BDA68|Breeding- normal/Shiny Charm/Masuda Method|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021412C0|Mersenne Twister table pointer|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02153100|Scripting system- memory allocation/setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022581F4|Wild pokemon PID storage|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02181E80|Hollow pokemon generation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02228B70|Hollow pokemon data array(u16 hollow[20])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F84C|Is hollow filled|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C8938|Hollow fill decisions|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214BE7C|SVC stack|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F8B4|Get hollow|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F8BC|Set hollow|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02228B98|Current hollow number|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221DDAC|Slot 1 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221DE88|Slot 2 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221DF64|Slot 3 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221E040|Slot 4 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221E11C|Slot 5 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0221E1F8|Slot 6 PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0207A998|DSi check|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214DC24|Mic status|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F898|Set hollow gender|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F830|Enable hollow|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F818|Set subslot|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200F800|Set slot|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0205780C|Build seed - wifi|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02241970|Wifi RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BCAC0|Battle rand|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A5318|Damage formula|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BCC58|Base damage|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BCC80|Damage type modifier|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005234|Vblank calback|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201C4E0|PKM creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201CDC0|Shiny check|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201D6E0|PID creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203D988|Input handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BD21C|Breeding|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02156410|Create scripted pokemon|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02140B1E|Current special pokemon being created|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201D644|Special PID creation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02026858|HM check|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B3E4|Expanded heap memory allocation struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02141324|G3D info struct|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214340C|G3D global state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022263A4|Pokedex data in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02162A14|Runs everything that has to happen after midnight|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0200DD20|Swarm calculation and storage|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02141440|VRAM transfer task array|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214BF70|Tick System|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02258454|Decrypted battle video allocation|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

(All offsets are White offsets.)

## Pokémon B2W2 (U)

|RAM Address|Description|Discovered by|
|---|---|---|
|02005124|TwlMain|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005748|RNG advancement routine 1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02005784|RNG advancement routine 2|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201592C|Script handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020191D8|Read event flag|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02019204|Update event flag|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201922C|Set event flag|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201D688|Create special PID (N's pokemon, etc)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0201D724|Create wild PID|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02026B44|Check for a hidden machine move|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02043F08|Mersenne Twister setup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02043F58|Mersenne Twister handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020440C4|Seed building function|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209DAC0|Current music|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214185C|Game Freak's memory allocator|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214C5B0|Tick system|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02153748|Scripting system- virtual machine pointer list and count|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02153978|execute script|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A2428|EV handler|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BDA74|Breeding|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021DD88C|Battle RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FED68|Mersenne Twister table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FF728|Mersenne Twister table counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FFC58|RNG state|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02205244|Save data info|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0220528C|Save data block list (12 bytes per block: blknum, size, start)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02205624|Save data in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02223024|Total steps|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02225882|Const data storage in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02225524|Event flag storage in RAM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02226328|Daycare poke 1|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0222640C|Daycare poke 2|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022264F0|Egg seed|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02226724|Money|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|022291F0|Hollow pokemon data array|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B534|Current game step counter|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02FE35C8|Egg data local array in RAM(u32 eggData[34])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021FFB00|Overlays currently loaded list, 1 list each for EWRAM, ITCM, and DTCM|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203CED0|Overlay inspector|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0203CE38|Overlay loader|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D01C0|N's pokemon|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D0230|Swarm pokemon|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D0190|Encounter slots|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D014C|Item percentages|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D0B6C|Move tutor|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D0310|Dust cloud rewards|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D0420|Field effect lookup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C9F90|Fog table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021C9F34|Edge color table|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D21B0|Incense breeding lookup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0208F18C|Save block action lookup|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0208F948|Form lookup (u16 pkmFormSet[21][2])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0208FA58|Key system keys|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02090394|Rotom special moves|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020903A0|Lookup table for adjusting stats for nature (u8 stat_nature_adjust[25][5])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020904A0|Lookup table for pkm block shuffling (u8 pkm_blk_shuf[32][4])|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02091C42|State list|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02091B58|Sweden county list|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02090CB0|TM List(tm1-92, hm1-6, tm93-95)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02090B78|Berries|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BD100|Battle rand|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021A5958|Damage formula|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02141914|Main rtc date - year, month, day, week|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02141924|Main rtc time - hour, minute, second|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020492E8|Get resource and resource type: bva, bma, bca, btp, bmd, btx|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020493B0|Load 3d gfx from narc(from already loaded narc)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02049370|Load 3d gfx from file(load narc then file from narc)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020493F0|Load 3d gfx from file path(from path to narc)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B484|Map number|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B48A|X pos|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B48E|Z pos|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B492|Y pos|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0223B49D|Direction facing|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|02246830|Area data(zonedata)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209DAA4|VRAM transfer manager counter for successful transfer|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021D7540|Type-effectiveness chart(0- no effect, 2- .5x dmg, 4- 1x dmg, 8- 2x dmg)|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|021BD1A0|Determine type effectiveness for the current attack|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|020308EC|Set up opposing trainers and their pokes for battle|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0209D780|Start of .sbss|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0214F540|End of .sbss|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

## Pokémon X / Y (U)

|RAM Address|Description|Location|Discovered by|
|---|---|---|---|
|00119C4C|Mersenne Twister generate unsigned int|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0011E52C|Seeding function for TinyMT|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0011E550|Generate seed for RNG|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0011E5C8|Seeding function for Mersenne Twister|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0015E958|Unsigned 32-bit divmod|ExeFS|magical|
|00163CC4|TinyMT PRNG|ExeFS|magical|
|00168660|Decrypt pokemon|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|001685F0|Encrypt pokemon|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0016B358|Get pkm block 0 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0016B3D4|Get pkm block 1 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|00176168|Get pkm block 2 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|001761E8|Get pkm block 3 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0018FB50|powf|ExeFS|magical|
|002C67A0|LCRNG, generate random unsigned int|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|003C71D8|Do pickup and honey gather|ExeFS|magical|
|004455A8|Pickup item table|ExeFS|magical|
|0002EFC0|Capture routine|DllBattle.cro|magical|
|000D12A8|Type effectiveness table|DllBattle.cro|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

(All offsets are X offsets.)  
(CRO locations are offset, not address.)

## Pokémon Omega Ruby / Alpha Sapphire (U)

|RAM Address|Description|Location|Discovered by|
|---|---|---|---|
|00168EC0|Decrypt pokemon|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|00168E50|Encrypt pokemon|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0016BC84|Get block 0 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0016BD00|Get block 1 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|00176EFC|Get block 2 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|0016BD80|Get block 3 pointer after shuffle|ExeFS|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|
|004872FC|Pickup item table|ExeFS|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|004960F8|Move Tutor List|ExeFS|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|004A67EE|TM/HM Move List|ExeFS|[Kaphotics](https://projectpokemon.org/wiki/index.php?title=Kaphotics&action=edit&redlink=1 "Kaphotics (page does not exist)")|
|000DB428|Type effectiveness table|DllBattle.cro|[Bond697](https://projectpokemon.org/wiki/index.php?title=Bond697&action=edit&redlink=1 "Bond697 (page does not exist)")|

(All offsets are Omega Ruby offsets.)  
(CRO locations are offset, not address.)