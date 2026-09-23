import logging

def parse_charmap_txt(filepath):
    """Parses PokeGen4Charmap.txt or similar Hexpat tables."""
    mapping = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    parts = line.strip().split('=', 1)
                    if len(parts) == 2:
                        hex_val, char = parts[0], parts[1]
                        try:
                            # 4 digit hex -> int, e.g. 0100=A
                            mapping[int(hex_val, 16)] = char
                        except ValueError:
                            pass
        return mapping
    except FileNotFoundError:
        logging.error(f"Charmap file {filepath} not found.")
        return {}

def decode_string(byte_array, charmap):
    """Decodes a bytearray representing a string using the provided charmap."""
    result = ""
    # Gen 4 uses 16-bit characters (2 bytes)
    for i in range(0, len(byte_array), 2):
        if i + 1 >= len(byte_array):
            break
        char_val = int.from_bytes(byte_array[i:i+2], byteorder='little')
        
        # End of string typically 0xFFFF
        if char_val == 0xFFFF:
            break
        
        if char_val in charmap:
            result += charmap[char_val]
        else:
            result += "?" # Unknown character
    return result
