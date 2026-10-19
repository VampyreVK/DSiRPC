"""Shared pieces of DSiRPC's tests (see tests/README.md): where things are,
and the simulated games, sets and DSi the tests run against."""

import os

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TESTS)
C_DIR = os.path.join(TESTS, "c")

RETAIL = os.path.join(REPO, "nds-bootstrap", "retail")
COMMON_INCLUDE = os.path.join(RETAIL, "common", "include")
RPCPROBE = os.path.join(RETAIL, "cardenginei", "arm7", "source", "rpcprobe")
ARM9_SOURCE = os.path.join(RETAIL, "cardenginei", "arm9", "source")
