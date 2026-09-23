import logging
import json
import os
from utils.config import Config
from core.charmap import parse_charmap_txt
from core.memory_reader import MemoryReader
from core.parser import PlatinumParser

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def debug_dump():
    logging.info("--- melonDS-RPC-Suite Debugger ---")
    conf = Config("PokemonPlatinumRPC.cfg")
    
    charmap = parse_charmap_txt("PokeGen4Charmap.txt")
    mem_reader = MemoryReader(host=conf.host_url, port=conf.port)
    
    dump_filename = "ram_dump.bin"
    logging.info(f"Fetching RAM from {conf.host_url}:{conf.port} and saving to {dump_filename}...")
    
    # 1. Fetch & Dump
    ram = mem_reader.fetch_memory(save_to_file=dump_filename)
    if not ram:
        logging.error("Failed to fetch RAM. Exiting debug.")
        return

    # 2. Parse & Print
    logging.info(f"RAM dumped. Size: {len(ram)} bytes. Parsing structures...")
    
    parser = PlatinumParser(ram, charmap)
    data = parser.parse()
    
    if data:
        logging.info("Successfully identified Live Save block!")
        # Print with indent to visually show layout
        formatted_json = json.dumps(data, indent=4)
        print(f"\n[PARSED DATA]\n{formatted_json}\n")
    else:
        logging.error("Failed to parse RAM structure. Ensure Platinum is fully booted past the main menu.")

if __name__ == "__main__":
    debug_dump()
