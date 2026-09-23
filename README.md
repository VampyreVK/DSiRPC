This repository contains the backend code for bridging custom melonDS memory TCP server to Discord Rich Presence using Python.

## Architecture

This tool uses a 4-step modular process:
1. `core.memory_reader`: TCP socket client to obtain a full 4MB RAM dump.
2. `core.parser`: Analyzes memory offsets dynamically starting from the anchor pointer `0x02101D40` for Pokémon Platinum.
3. `api.pokeapi`: Hits `pokeapi.co` for contextual lookup.
4. `rpc.discord_client`: Manages local Discord updating (Respects 15s limit).

## Usage Requirements

**Install Dependencies**
```powershell
pip install -r requirements.txt
```
*(Ensure `pypresence` and `requests` are installed)*

**Invoking with Windows PowerShell alongside MelonDS**
To ensure the script exits when MelonDS ends, use a standard wrap script like below:

```powershell
# Launch the backend RPC daemon as a background job
Start-Job -Name "MelonRPC" -ScriptBlock { python main.py }

# Launch modified melonDS and wait for it to exit
Start-Process -FilePath ".\melonDS.exe" -Wait

# When the game terminates, kill the RPC script
Stop-Job -Name "MelonRPC"
Remove-Job -Name "MelonRPC"
```

## Debugging
* Leave `test_bridge.py` intact to verify basic TCP echo capabilities.
* Use `python debug_dump_and_parse.py` to capture a single `ram_dump.bin` output and print all available address locations and parsed offset data safely parsed into stdout.
A python tool to integrate Discord Rich Presence into melonDS. Designed to work alongside https://github.com/VampyreVK/melonDS-shmem 


Create Python env:
```
python -m venv .venv


Avtivate Python env:
```
.\.venv\Scripts\Activate.ps1
```

Install dependancies:
```
pip install pypresence
```

Test:
> Open Pokemon Platinum and run this command:
```
python test_bridge.py
```
This will dump the system memory to `ram_dump.bin`


CREDIT to (PurpleZaffre) for the overworld assets. 