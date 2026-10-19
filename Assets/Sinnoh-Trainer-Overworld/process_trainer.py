import os
from PIL import Image

# --- CONFIGURATION ---
CANVAS_SIZE = 160
BOTTOM_Y = 126          # same placement as process_diorama.py
BACKGROUND_BASE_PATH = "BattleBackgroundNormal.png"
CELL_SIZE = 64          # each sheet is a 4x4 grid of 64x64 cells
FRAME_DURATION = 150    # ms per walking frame
# Sheet rows, top to bottom. The 4 columns are the walk cycle frames.
DIRECTIONS = ["Down", "Left", "Right", "Up"]
SHEETS = {
    "NPC_198_Lucas.png": "Lucas",
    "NPC_201_Dawn.png": "Dawn",
}

def build_gif(sheet, row, bg_base_img, output_path):
    try:
        frames = []
        for col in range(4):
            box = (col * CELL_SIZE, row * CELL_SIZE, (col + 1) * CELL_SIZE, (row + 1) * CELL_SIZE)
            cell = sheet.crop(box)

            # Create the strict 160x160 canvas
            new_frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))

            # Paste the base diorama image first
            if bg_base_img:
                new_frame.paste(bg_base_img, (0, 0), bg_base_img)

            # Centered horizontally, bottom of the cell at y=126 (not mirrored, so
            # Left/Right keep their meaning)
            paste_x = (CANVAS_SIZE - CELL_SIZE) // 2
            paste_y = BOTTOM_Y - CELL_SIZE
            new_frame.paste(cell, (paste_x, paste_y), cell)

            frames.append(new_frame)

        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=FRAME_DURATION,
            loop=0,
            disposal=2,
            transparency=0
        )
        print(f"Success: {output_path}")

    except Exception as e:
        print(f"Error processing {output_path}: {e}")

def main():
    bg_base_img = None
    if os.path.exists(BACKGROUND_BASE_PATH):
        bg_base_img = Image.open(BACKGROUND_BASE_PATH).convert("RGBA")
        if bg_base_img.size != (CANVAS_SIZE, CANVAS_SIZE):
            bg_base_img = bg_base_img.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.NEAREST)
    else:
        print(f"Warning: {BACKGROUND_BASE_PATH} not found. Outputting with transparent backgrounds.")

    for sheet_name, trainer in SHEETS.items():
        if not os.path.exists(sheet_name):
            print(f"Missing sprite sheet: {sheet_name}")
            continue
        sheet = Image.open(sheet_name).convert("RGBA")
        for row, direction in enumerate(DIRECTIONS):
            build_gif(sheet, row, bg_base_img, f"{trainer}-{direction}.gif")

if __name__ == "__main__":
    main()
