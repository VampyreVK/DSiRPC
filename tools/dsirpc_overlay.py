"""
dsirpc_overlay.py - the overlay window on its own, like before the tray app:
the same as 'dsirpc.py --overlay --no-discord'.

    python tools/dsirpc_overlay.py                  # read the DSi
    python tools/dsirpc_overlay.py --discord        # ...and run the Rich Presence too
    python tools/dsirpc_overlay.py --demo           # made-up scenes, no DSi needed
    python tools/dsirpc_overlay.py --file ram_dump.bin
    python tools/dsirpc_overlay.py --chroma 00FF00  # green background for a chroma key

Every other option is dsirpc.py's (see 'python dsirpc.py --help').
"""

import os
import sys

# The repo root (this file is in tools/).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import dsirpc  # noqa: E402


def main():
    args = sys.argv[1:]
    if "--discord" in args:
        args.remove("--discord")
    elif "--no-discord" not in args:
        args.append("--no-discord")
    if "--overlay" not in args:
        args.append("--overlay")
    return dsirpc.main(args)


if __name__ == "__main__":
    sys.exit(main())
