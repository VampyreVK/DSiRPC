import os
from PIL import Image, ImageOps, ImageSequence

# --- CONFIGURATION ---
MARGIN = 6  # Additional padding added to all sides before scaling
OUTPUT_DIR = "processed_sprites"
SCALE_FACTOR = 2  # Multiplier for nearest-neighbor upscale

def process_sprite(file_path, output_path):
    try:
        with Image.open(file_path) as img:
            frames = []
            durations = []
            
            # 1. Calculate the base 1:1 Canvas Size
            original_width, original_height = img.size
            max_dim = max(original_width, original_height)
            target_size = max_dim + (MARGIN * 2)

            # 2. Iterate through the animated frames
            for frame in ImageSequence.Iterator(img):
                frame = frame.convert("RGBA")
                
                flipped_frame = ImageOps.mirror(frame)
                
                new_frame = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
                
                paste_x = (target_size - original_width) // 2
                paste_y = (target_size - original_height) // 2
                
                new_frame.paste(flipped_frame, (paste_x, paste_y), flipped_frame)
                
                # 3. Apply Nearest-Neighbor Scaling to the assembled square
                scaled_size = (target_size * SCALE_FACTOR, target_size * SCALE_FACTOR)
                final_frame = new_frame.resize(scaled_size, Image.Resampling.NEAREST)
                
                frames.append(final_frame)
                durations.append(img.info.get('duration', 100))

            # 4. Save the new GIF with strict disposal settings
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=img.info.get('loop', 0),
                disposal=2,
                transparency=0
            )
            print(f"Success: {os.path.basename(file_path)}")
            
    except Exception as e:
        print(f"Error processing {os.path.basename(file_path)}: {e}")

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    gif_files = [f for f in os.listdir('.') if f.lower().endswith('.gif')]
    
    if not gif_files:
        print("No GIFs found in this directory!")
        return

    print(f"Found {len(gif_files)} sprites. Processing and upscaling...")
    
    for gif in gif_files:
        output_path = os.path.join(OUTPUT_DIR, gif)
        process_sprite(gif, output_path)

if __name__ == "__main__":
    main()