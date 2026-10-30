"""
render_launcher.py - the launcher's modern look, drawn by its own code on this
PC (tests/c/ui's host, built with gcc: Linux or WSL, like the tests) from a
made-up SD card (tests/helpers/launcher_ui.py):

    python tools/render_launcher.py               the README's pictures, as pixel-art SVGs
    python tools/render_launcher.py --png         every screen as a PNG, and a contact sheet
    python tools/render_launcher.py --demo        a walk through the screens, about 30 s:
                                                  demo.mp4 (with the Bright song) and demo.gif

Everything goes to renders/ (--out DIR for another folder); --scale N sizes
the PNGs and the video (3: 816x1224). The PNGs and the GIF need Pillow, the
video ffmpeg (built with libopenmpt for the song, as Ubuntu's is; without it
the video is silent). The README shows the SVGs and the GIF from the
renders branch, which .github/workflows/renders.yml updates when a release
comes out.

Each SVG is a DSi: the top screen's diamonds as an SVG pattern, the rest as
rectangles of one color.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from helpers import REPO, launcher_ui as lui  # noqa: E402

PICTURES = {
    "home": ("launcher-home.svg", "The launcher's main screen"),
    "games": ("launcher-games.svg", "The game list, with the picked game's details on the top screen"),
    "achievements": ("launcher-achievements.svg", "A game's achievements"),
    "saves": ("launcher-saves.svg", "The save sync, with the picked save's details on the top screen"),
}
BACKGROUND = (14, 20, 27)       # the launcher's darkest grey, around the screens
GAP = 8                         # DS pixels between the screens, and around them
DEMO_FPS = 15
SONG = os.path.join(REPO, "launcher", "audio", "bright.xm")


def image(path, scale):
    """A 256x384 dump (both screens) as a DSi would hold them: the two screens
    a gap apart, scaled up by a whole number."""
    from PIL import Image
    w, h, px = lui.read_ppm(path)
    shot = Image.new("RGB", (w, h))
    shot.putdata([p for row in px for p in row])
    out = Image.new("RGB", (w + 2 * GAP, h + 3 * GAP), BACKGROUND)
    out.paste(shot.crop((0, 0, w, h // 2)), (GAP, GAP))
    out.paste(shot.crop((0, h // 2, w, h)), (GAP, h // 2 + 2 * GAP))
    return out.resize((out.width * scale, out.height * scale), Image.NEAREST)


def render_svgs(host, sd, shots, out_dir):
    rom = os.path.join(sd, "roms", "nds", "Pokemon Platinum.nds")
    out = lui.run(host, f"render {shots}|{sd}|{rom}|1")
    pattern = next(ln.split()[1:] for ln in out if ln.startswith("pattern "))
    for screen, (name, title) in PICTURES.items():
        svg = lui.to_svg(os.path.join(shots, screen + ".ppm"), pattern, title)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"{os.path.join(out_dir, name)}: {len(svg) // 1024} KB")


def render_pngs(host, sd, shots, out_dir, scale):
    from PIL import Image
    rom = os.path.join(sd, "roms", "nds", "Pokemon Platinum.nds")
    lui.run(host, f"render {shots}|{sd}|{rom}|0")
    names = sorted(n[:-4] for n in os.listdir(shots) if n.endswith(".ppm"))
    small = []
    for name in names:
        image(os.path.join(shots, name + ".ppm"), scale).save(os.path.join(out_dir, name + ".png"))
        small.append(image(os.path.join(shots, name + ".ppm"), 1))
    cols = 6
    w, h = small[0].size
    sheet = Image.new("RGB", (cols * w, (len(small) + cols - 1) // cols * h), BACKGROUND)
    for i, im in enumerate(small):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(os.path.join(out_dir, "contact-sheet.png"))
    print(f"{out_dir}: {len(names)} screens and contact-sheet.png")


def scenes(path):
    """scenes.txt: (name, first frame, seconds) a scene"""
    with open(path) as f:
        return [(name, int(first), float(seconds)) for name, first, seconds in (ln.split() for ln in f)]


def render_demo(host, sd, work, out_dir, scale):
    from PIL import Image
    frames, stills = os.path.join(work, "frames"), os.path.join(work, "stills")
    os.makedirs(frames)
    os.makedirs(stills)
    lui.run(host, f"demo {frames}|{sd}|{DEMO_FPS}")
    lui.run(host, f"demo {stills}|{sd}|0")
    length = sum(seconds for _, _, seconds in scenes(os.path.join(stills, "scenes.txt")))

    # The GIF: a still a scene, for the README (no sound, and small)
    gif = os.path.join(out_dir, "demo.gif")
    shots = [(image(os.path.join(stills, f"frame_{first:04d}.ppm"), 2), seconds)
             for _, first, seconds in scenes(os.path.join(stills, "scenes.txt"))]
    first = shots[0][0].quantize(colors=255)
    first.save(gif, save_all=True, append_images=[im.quantize(colors=255) for im, _ in shots[1:]],
               duration=[round(seconds * 1000) for _, seconds in shots], loop=0, optimize=True)
    print(f"{gif}: {length:.1f} s, {os.path.getsize(gif) // 1024} KB")

    # The video: every frame, the spinner and the diamonds moving, with the
    # Bright song (ffmpeg plays the XM with libopenmpt) fading out at the end
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("No ffmpeg: no demo.mp4")
        return
    w, h, gap = 256 * scale, 192 * scale, GAP * scale
    picture = (f"[0:v]split[a][b];"
               f"[a]crop=256:192:0:0,scale={w}:{h}:flags=neighbor,"
               f"pad={w + 2 * gap}:{h + gap + gap // 2}:{gap}:{gap}:color=0x{bytes(BACKGROUND).hex()}[top];"
               f"[b]crop=256:192:0:192,scale={w}:{h}:flags=neighbor,"
               f"pad={w + 2 * gap}:{h + gap + gap - gap // 2}:{gap}:{gap - gap // 2}:color=0x{bytes(BACKGROUND).hex()}[bottom];"
               f"[top][bottom]vstack,format=yuv420p[v]")
    video = ["-framerate", str(DEMO_FPS), "-i", os.path.join(frames, "frame_%04d.ppm")]
    encode = ["-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "animation", "-r", "30",
              "-movflags", "+faststart", "-t", f"{length:.2f}"]
    mp4 = os.path.join(out_dir, "demo.mp4")
    with_song = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *video, "-i", SONG,
                 "-filter_complex", picture, "-map", "[v]", "-map", "1:a",
                 "-af", f"afade=t=out:st={max(0.0, length - 2):.2f}:d=2", "-c:a", "aac", "-b:a", "160k", *encode, mp4]
    if subprocess.run(with_song).returncode != 0:
        print("ffmpeg couldn't play the song (no libopenmpt?): demo.mp4 without it")
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *video, "-filter_complex", picture,
                        "-map", "[v]", *encode, mp4], check=True)
    print(f"{mp4}: {os.path.getsize(mp4) // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description="Draw the launcher's modern look with its own code")
    ap.add_argument("--out", default=os.path.join(REPO, "renders"), help="where they go (default renders/)")
    ap.add_argument("--png", action="store_true", help="every screen as a PNG, and a contact sheet")
    ap.add_argument("--demo", action="store_true", help="a walk through the screens: demo.mp4 and demo.gif")
    ap.add_argument("--scale", type=int, default=3, help="the PNGs' and the video's scale (default 3)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        host = lui.build(os.path.join(tmp, "ui_host"), sanitize=False)
        sd = os.path.join(tmp, "sd")
        lui.make_sd(sd)
        shots = os.path.join(tmp, "shots")
        os.makedirs(shots)
        render_svgs(host, sd, shots, args.out)
        if args.png:
            png_dir = os.path.join(args.out, "png")
            os.makedirs(png_dir, exist_ok=True)
            render_pngs(host, sd, shots, png_dir, args.scale)
        if args.demo:
            render_demo(host, sd, os.path.join(tmp, "demo"), args.out, args.scale)


if __name__ == "__main__":
    main()
