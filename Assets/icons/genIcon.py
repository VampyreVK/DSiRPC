import sys

def build_adaptive_icns(light_icns, dark_icns, output_icns):
    with open(light_icns, 'rb') as f:
        light_data = bytearray(f.read())
        
    with open(dark_icns, 'rb') as f:
        dark_data = f.read()

    # Dark mode chunk type is an undocumented hex: FD D9 2F A8
    chunk_type = b'\xfd\xd9\x2f\xa8'
    chunk_length = len(dark_data) + 8
    
    light_data.extend(chunk_type)
    light_data.extend(chunk_length.to_bytes(4, byteorder='big'))
    light_data.extend(dark_data)
    
    # Update the master ICNS file length (bytes 4-7)
    light_data[4:8] = len(light_data).to_bytes(4, byteorder='big')
    
    with open(output_icns, 'wb') as f:
        f.write(light_data)

if __name__ == '__main__':
    build_adaptive_icns('light.icns', 'dark.icns', 'adaptive.icns')