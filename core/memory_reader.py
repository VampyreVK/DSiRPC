import socket
import logging

class MemoryReader:
    def __init__(self, host='127.0.0.1', port=8090, expected_size=4*1024*1024):
        self.host = host
        self.port = port
        self.expected_size = expected_size

    def fetch_memory(self, save_to_file=None):
        logging.info(f"Attempting to connect to melonDS at {self.host}:{self.port}...")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Add a timeout so it gracefully fails instead of hanging indefinitely
                s.settimeout(5.0)
                s.connect((self.host, self.port))
                
                raw_ram = b''
                while True:
                    chunk = s.recv(16384)
                    if not chunk:
                        break
                    raw_ram += chunk
            
            if save_to_file:
                with open(save_to_file, "wb") as f:
                    f.write(raw_ram)
            
            if len(raw_ram) >= self.expected_size:
                return raw_ram[:self.expected_size]
            else:
                logging.warning(f"Incomplete dump: got {len(raw_ram)} bytes.")
                return raw_ram
                
        except (ConnectionRefusedError, socket.timeout):
            logging.error("Connection failed. melonDS not running or TCP server inactive.")
            return None
        except Exception as e:
            logging.error(f"MemoryReader error: {e}")
            return None
