



Is there any (If not no worries) way to show my game status in Steam / Discord activity with this powershell script setup since it is already running? (I would assume the strat here would be to pull from the emulated memory of the rom in melonDS directly and update the RPC based on that in real-time, maybe, if we got the static address within the NDS memory, we could use a memory map of pokemon platinum to determine which hex addresses correspond to things like XY coordinates, current party, battle state, etc.) I was thinking something along the lines of
Line 1: highly dynamic, current action.

Examples: "Exploring Mt. Coronet", "Battling Gym Leader Fantina", or "Browsing the PC in Jubilife City".

State (Line 2 - The "Stats"): 

Example: "Badges: 4 | Pokédex: 87" or any other information that would be useful in the moment here.

Party Size (The native Discord fraction):
We could use this to show how many Pokémon are currently alive out of my total party size Ex. "Party: (3 of 5)"

Large/Small Image: We could map the location ID's in the game to asset keys allowing me to put things like an area Icon for the main image and a little icon of dawn in her current up-down-left-right orientation + we could show if she is running or biking with their own 4 each if we have space. The discord API limits updates to every 5 seconds though so having all 4 directions for the non-walking states could be overkill

This page has a TON of assets we could use! :

https://www.spriters-resource.com/ds_dsi/pokemonplatinum/

This repo worked off of the save, and was designed for diamond/pearl, but could give us some ideas?

https://github.com/kiwi515/Gen4RPC

We could change up this activity type depending on what I am doing too, potentially even get creative: since there are 300 asset slots available, we could add my own party as assets, as well as either the pokemon that can be carried by trainers + elite 4, and then use the smaller image in the bottom right design to put a flipped sprite of their pokemon as the large image, and a flipped sprite of mine as the small image so it looks like a little battle! (edited)Wednesday, May 6, 2026 4:37 PM

---

Could you look into the memory allocation for pokemon platinum running on the Nintendo DS? I am looking to complete a task I was working on earlier, I will past my initial goal for the project last. for this, I would like you to create a document outlining the location and access of all values that might be relevant to this project, including ones that were not explicitly mentioned, but could be useful. Basically anything relating the the save or live game-state. With this map of both what is possible, The location (offset/pointers etc) of each item in memory, within the 4MB block of RAM dumped from the DS, as well as the way in which item is encoded or potentially encrypted.

  

Could you look into how this data is handled in the save file itself and how info maps within the save file, and then the translation of that to RAM. Cover both the save-structure-in-RAM (decrypted party/box layout, checksums, the Gen 4 substructure shuffle) AND the volatile live-state addresses (player XY, map ID, battle flags, menu state, etc. 

The version of the game being targeted here is `Pokemon - Platinum Version (USA) (Rev 1).nds` running on melonEMU, modified to provide a live web-server that shows the current system memory.

Since in Gen IV Pokémon Games, most "addresses" are actually `[base_pointer] + offset` chains rather than static, Please Include the known base pointers and how to resolve them at runtime (which is what you'd actually need for melonDS RAM reads), as well as the conceptual offsets.


---