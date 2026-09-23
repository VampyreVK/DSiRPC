import os
from PIL import Image, ImageOps, ImageSequence

# --- CONFIGURATION ---
CANVAS_SIZE = 160
BOTTOM_Y = 126
BACKGROUND_BASE_PATH = "BattleBackgroundNormal.png"

def process_sprite(file_path, bg_base_img):
    try:
        # 1. Read all frames into memory so we can close the file before overwriting
        frames = []
        durations = []
        loop_count = 0
        
        with Image.open(file_path) as img:
            loop_count = img.info.get('loop', 0)
            original_width, original_height = img.size
            
            for frame in ImageSequence.Iterator(img):
                # Copy and convert frame to memory to release the file lock
                frame = frame.copy().convert("RGBA")
                durations.append(img.info.get('duration', 100))
                
                flipped_frame = ImageOps.mirror(frame)
                
                # Create the strict 160x160 canvas
                new_frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
                
                # Paste the base diorama image first
                if bg_base_img:
                    new_frame.paste(bg_base_img, (0, 0), bg_base_img)
                    
                # Calculate Coordinates: Centered horizontally, bottom exactly at y=126
                paste_x = (CANVAS_SIZE - original_width) // 2
                paste_y = BOTTOM_Y - original_height
                
                new_frame.paste(flipped_frame, (paste_x, paste_y), flipped_frame)
                
                frames.append(new_frame)
        
        # 2. The file is now closed. Safe to overwrite!
        frames[0].save(
            file_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop_count,
            disposal=2,
            transparency=0
        )
        print(f"Overwrote: {os.path.basename(file_path)}")
            
    except Exception as e:
        print(f"Error processing {os.path.basename(file_path)}: {e}")

def main():
    # Load and verify the battle background
    bg_base_img = None
    if os.path.exists(BACKGROUND_BASE_PATH):
        bg_base_img = Image.open(BACKGROUND_BASE_PATH).convert("RGBA")
        # Ensure the base image is exactly 160x160 so it fits the canvas
        if bg_base_img.size != (CANVAS_SIZE, CANVAS_SIZE):
            bg_base_img = bg_base_img.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.NEAREST)
    else:
        print(f"Warning: {BACKGROUND_BASE_PATH} not found. Outputting with transparent backgrounds. UwU")

    # Target the current directory
    gif_files = [f for f in os.listdir('.') if f.lower().endswith('.gif')]
    
    if not gif_files:
        print("No GIFs found in this directory!")
        return

    print(f"Found {len(gif_files)} sprites. Processing and overwriting in-place...")
    
    for gif in gif_files:
        process_sprite(gif, bg_base_img)

if __name__ == "__main__":
    main()