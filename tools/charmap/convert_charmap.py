import sys

def parse_charmap(filename):
    mapping = {}
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            if '=' in line:
                parts = line.split('=', 1)
                hex_val = parts[0].strip()
                char_val = parts[1] # preserve trailing spaces if needed
                
                # Filter out control codes or backslash escapes for valid identifiers
                mapping[hex_val] = char_val
    return mapping

def generate_hexpat_enum(mapping, out_filename):
    """
    Generates a .hexpat enum mapping hex codes to generic identifiers
    and a formatting function to decode arrays.
    """
    with open(out_filename, 'w', encoding='utf-8') as f:
        f.write("#pragma endian little\n\n")
        f.write("enum PokeCharGen4 : u16 {\n")
        for hex_val, char_val in mapping.items():
            f.write(f"    Code_{hex_val} = 0x{hex_val},\n")
        f.write("};\n\n")
        
        f.write("import std.mem;\n\n")
        f.write("struct PokeString {\n")
        f.write("    PokeCharGen4 chars[while(std::mem::read_unsigned($, 2, std::mem::Endian::Little) != 0xFFFF)];\n")
        f.write("    PokeCharGen4 terminator;\n")
        f.write("};\n")
        
        print(f"Saved hexpat enum to {out_filename}")

def generate_imhex_encoding(mapping, out_filename):
    """
    If you want ImHex to natively display these characters in the Hex Editor view,
    you can generate a Custom Encoding format (e.g. standard TSV hex to char mapping).
    """
    with open(out_filename, 'w', encoding='utf-8') as f:
        for hex_val, char_val in mapping.items():
            # Byte swap for raw byte encodings (e.g. 0140 -> 4001)
            swapped_hex = hex_val[2:4] + hex_val[0:2] if len(hex_val) == 4 else hex_val
            f.write(f"{swapped_hex}\t{char_val}\n")
            
        print(f"Saved ImHex encoding table to {out_filename}")

def generate_tbl_file(mapping, out_filename):
    """
    Generates a standard Thingy Table (.tbl) file format (HEX=Char).
    """
    with open(out_filename, 'w', encoding='utf-8') as f:
        for hex_val, char_val in mapping.items():
            # Byte swap for raw byte encodings (e.g. 0140 -> 4001)
            swapped_hex = hex_val[2:4] + hex_val[0:2] if len(hex_val) == 4 else hex_val
            f.write(f"{swapped_hex}={char_val}\n")
            
        print(f"Saved Thingy Table to {out_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_charmap.py charmap.txt")
        sys.exit(1)
        
    mapping = parse_charmap(sys.argv[1])
    generate_hexpat_enum(mapping, "PokeGen4Charmap.hexpat")
    generate_imhex_encoding(mapping, "PokeGen4Encoding.tsv")
    generate_tbl_file(mapping, "PokeGen4Encoding.tbl")