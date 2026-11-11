"""dsirpc.py's command line: --clear-learning's optional game code never
takes the mode ("--clear-learning tray" is the tray, every game), and "all"
in any case is every game."""

import pytest

import dsirpc


@pytest.mark.parametrize("argv,mode,clear", [
    ([], "run", None),
    (["--clear-learning"], "run", "all"),
    (["--clear-learning", "tray"], "tray", "all"),
    (["tray", "--clear-learning"], "tray", "all"),
    (["--clear-learning", "Setup"], "setup", "all"),
    (["--clear-learning", "ALL"], "run", "all"),
    (["--clear-learning", "All", "tray"], "tray", "all"),
    (["--clear-learning", "cpue"], "run", "CPUE"),
    (["--clear-learning", "IPKE", "tray"], "tray", "IPKE"),
    (["--clear-learning=tray"], "tray", "all"),
    (["--clear-learning", "tray", "setup"], "setup", "all"),     # (a mode name is never a game code)
])
def test_clear_learning(argv, mode, clear):
    args = dsirpc.parse_args(argv)
    assert (args.mode, args.clear_learning) == (mode, clear)
    assert dsirpc._engine_args(args)["clear_learning"] == clear
