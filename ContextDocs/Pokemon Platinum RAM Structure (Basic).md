### 1. The Pointer Chain

As you suspected, Platinum utilizes dynamic memory allocation. The game constantly moves data around to prevent memory fragmentation.

- **The Anchor (`0x02101D40`):** This is the static pointer for Platinum (USA). It never moves.
    
- **The Destination:** If you read the 4 bytes at that anchor, it gives you a memory address (usually starting with `0x022...`). That new address is the start of the **Live Save Block**.
    

### 2. The Live Save Block Offsets

Once we jump to that dynamic address, we are essentially looking at a live, breathing version of a `.sav` file. From the start of that block, we can add fixed offsets to find exactly what we need:

- **`+ 0x64`**: Trainer Name (String, 16 bytes)
    
- **`+ 0x94`**: Playtime (4 bytes: Hours, Minutes, Seconds, Frames)
    
- **`+ 0xD0`**: The Party Block
    

### 3. The Party Structure (The Best News)

The Party Block starting at `+ 0xD0` is perfectly structured for our Discord RPC.

- **Party Count:** The very first 4 bytes of the Party Block tell you exactly how many Pokémon are currently in your party (an integer between 0 and 6).
    
- **The Slots:** Immediately after that count, there are six slots reserved for Pokémon. Every single Pokémon in the party is exactly **236 bytes** long.
    

**Here is the absolute best part:** In the game's code, the first 136 bytes of a Pokémon contain its deep data (Species, IVs, EVs, PID) and are _encrypted_ using a pseudo-random number generator. However, the remaining 100 bytes are temporary "Battle Stats" that the game uses for quick reference. **The Battle Stats are entirely unencrypted!**

This means inside a 236-byte Pokémon structure, we can instantly read:

- **`+ 0x8C`**: Current Level (1 byte)
    
- **`+ 0x8E`**: Current HP (2 bytes)
    
- **`+ 0x90`**: Max HP (2 bytes)
    

We won't need to write a complex decryption algorithm just to show your party's health bars on Discord!