"""
paths.py - where DSiRPC's files are. ROOT is the folder with the code and
what comes with it (Assets/Consoles, the charmap, defaults.cfg, the rcheevos
library); DATA is where DSiRPC writes: dsirpc.cfg, logs/, ra/ (sets and
caches) and the sprites it downloads (Assets/).

They're the same folder, except in the macOS app (packaging/macos/), whose
bundle shouldn't be written to: there DATA is
~/Library/Application Support/DSiRPC.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAC_APP = bool(getattr(sys, "frozen", False)) and sys.platform == "darwin"
DATA = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "DSiRPC") if MAC_APP else ROOT
