"""
dsirpc_overlay.py - a pixel-art window showing your party and battles live,
for OBS (Window Capture) or a Discord screen share.

Usage, from the repo root:
  python dsirpc_overlay.py                  # read the DSi
  python dsirpc_overlay.py --discord        # ...and run the Rich Presence too
  python dsirpc_overlay.py --demo           # made-up scenes, no DSi needed
  python dsirpc_overlay.py --file ram_dump.bin
  python dsirpc_overlay.py --chroma 00FF00  # green background for a chroma key

Don't run dsirpc.py at the same time (both need UDP port 4244); use
--discord here instead. See overlay/app.py for all options and keys.
"""

from overlay.app import main

if __name__ == "__main__":
    main()
