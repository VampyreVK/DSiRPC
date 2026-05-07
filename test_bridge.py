import socket
import logging

# Configure standard logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def fetch_memory_dump():
    host = '127.0.0.1'
    port = 8090
    expected_size = 4 * 1024 * 1024  # 4MB (0x400000 bytes)
    output_file = "ram_dump.bin"

    logging.info(f"Attempting to connect to melonDS at {host}:{port}...")
    
    try:
        # Open a standard TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            logging.info("Connection established. Downloading RAM...")
            
            # Receive the data in chunks until the emulator closes the connection
            raw_ram = b''
            while True:
                chunk = s.recv(8192)
                if not chunk:
                    break
                raw_ram += chunk
                
        logging.info(f"Bytes received: {len(raw_ram):,}")
        
        # Save the raw dump for analysis
        with open(output_file, "wb") as f:
            f.write(raw_ram)
        logging.info(f"Memory dump saved to '{output_file}'")
        
        # Validate dump size
        if len(raw_ram) == expected_size:
            logging.info("Success: Captured the exact 4MB memory dump.")
        else:
            logging.warning(f"Size mismatch. Expected {expected_size} bytes, got {len(raw_ram)} bytes.")
            
    except ConnectionRefusedError:
        logging.error("Connection refused. Ensure the custom melonDS build is running and a ROM is loaded.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    fetch_memory_dump()