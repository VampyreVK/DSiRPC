import time
import logging
import sys
from utils.config import Config
from core.charmap import parse_charmap_txt
from core.memory_reader import MemoryReader
from core.parser import PlatinumParser
from api.pokeapi import PokeAPI
from rpc.discord_client import DiscordRPC

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    conf = Config("PokemonPlatinumRPC.cfg")
    
    # Load charmap
    charmap = parse_charmap_txt("PokeGen4Charmap.txt")
    if not charmap:
        logging.warning("Proceeding without charmap. Text translation will fail.")

    mem_reader = MemoryReader(host=conf.host_url, port=conf.port)
    pokeapi = PokeAPI()
    
    rpc = DiscordRPC(conf.discord_client_id)
    rpc.connect()

    logging.info("Starting RPC Loop. Press Ctrl+C to stop.")
    start_time = time.time()
    
    try:
        while True:
            # 1. Fetch RAM
            ram_dump = mem_reader.fetch_memory()
            if not ram_dump:
                logging.info("Waiting for melonDS... retrying in 15 seconds.")
                time.sleep(15)
                continue
            
            # 2. Parse Data
            parser = PlatinumParser(ram_dump, charmap)
            parsed_data = parser.parse()
            
            if not parsed_data:
                logging.warning("Could not locate live save block. Is the game loaded?")
                time.sleep(15)
                continue
            
            trainer_name = parsed_data.get('trainer_name', 'Unknown')
            party_count = parsed_data.get('party_count', 0)
            party = parsed_data.get('party', [])
            
            # 3. Form RPC Layout
            substate = f"Trainer {trainer_name} | {party_count}/6 in Party"
            details = "Exploring Sinnoh"
            
            if party:
                lead = party[0]
                hp_str = f"Lvl {lead['level']} | {lead['curr_hp']}/{lead['max_hp']} HP"
                details = f"Lead PKMN: {hp_str}"
            
            # 4. Update RPC
            rpc.update(
                state=substate,
                details=details,
                large_image="platinum_logo", # Add string mappings as needed
                large_text="Pokémon Platinum",
                start=int(start_time)
            )

            # Discord rate limit is 1 per 15s. Wait slightly longer to be safe.
            time.sleep(15)
            
    except KeyboardInterrupt:
        logging.info("Shutting down gracefully...")
    finally:
        rpc.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
