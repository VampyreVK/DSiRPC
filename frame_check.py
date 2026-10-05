#!/usr/bin/env python3
"""
frame_check.py - can the DSi capture the game's memory frame by frame?

RetroAchievements definitions are checked once per frame and many of them
compare a value with the one from the frame before, so a RetroAchievements
client needs every frame's values, in order. rpcprobe's per-frame capture
(set_watch / fetch_frames) reads a short list of values on the ARM7 at each
VBlank. The game runs on the ARM9, whose data cache holds recent writes for a
while before they reach main RAM, and both CPUs wake up at the same VBlank, so
the ARM7 could see some values a frame (or more) late. This tool measures that.

It watches a VBlank counter: a value the game adds one to after waiting for
a VBlank, so it can go up by at most one per frame. Between two consecutive
frames the capture can then see:

  +1        the game counted that frame
  0         the game didn't count that frame (a 30 fps screen, or lag). An
            emulator sees exactly the same, so this is fine.
  +2 or more  impossible for the game, so the read(s) before it were late and
            this one caught up. A one-frame catch-up can be a race with the
            game's own code right at the start of VBlank, or the ARM9 cache;
            a longer one can only be the cache.

Late reads are the only problem. The counter's rate (60 or 30 a second) just
says how fast that screen runs.

Builds whose hellos say a9=1 or more have the ARM9 read the values: through
its own cache (so never late) and at the very start of each VBlank, before
the game's own VBlank code, so a value the game changes right then is always
read on the same side of that change. The ARM7 only fills in when there's no
ARM9 snapshot to record; the report counts both and judges the ARM9's records
on their own. --arm7-only turns the ARM9 off for a run, to compare.

--save NAME writes every record to logs/NAME.csv and this report to
logs/NAME.txt (logs/ is next to this file and git ignores it).

Usage, from the repo root (only one tool can use UDP port 4244 at a time):
  python frame_check.py                          # Platinum: its own VBlank counter, 20 s
  python frame_check.py --seconds 60
  python frame_check.py --watch 0x021BF6A8:4     # any game: the first watch must be a frame counter
  python frame_check.py --watch 0x021BF6A8:4 0x021BF6B4:4   # extra watches: how often they changed
  python frame_check.py --find-counter 0x021BF000:0x1000    # look for frame counters in a range
  python frame_check.py --save boot              # also save logs/boot.csv and logs/boot.txt
  python frame_check.py --arm7-only               # the old way (ARM7 reads main RAM), to compare
"""

import argparse
import csv
import sys
import time
from pathlib import Path

from core.dsirpc_client import DSiClient, MAX_WATCHES, split_values, _hello_fields

# Pokemon Platinum (US): gSystem.vblankCounter (pret/pokeplatinum, include/
# system.h). The main loop adds one after a VBlank it waited for, so it goes
# up at most once a frame: every frame on some screens, every other frame in
# the overworld (30 fps). gSystem itself is at 0x021BF67C.
PLATINUM_COUNTER = (0x021BF6A8, 4)
KNOWN_COUNTERS = {"CPUE": PLATINUM_COUNTER}

FRAME_RATES = (60.0, 30.0)  # what a per-frame counter can go up by, per second

LOGS_DIR = Path(__file__).resolve().parent / "logs"


def parse_watch(s):
    addr, _, size = s.partition(":")
    return int(addr, 0), int(size or "4", 0)


def parse_span(s):
    addr, _, length = s.partition(":")
    return int(addr, 0), int(length or "0x1000", 0)


def find_counters(c, start, length):
    """Reads the range twice (and the hits a third time) and returns
    [(addr, per second)] for aligned 32-bit values that went up by about 60
    or 30 per second both times."""
    length -= length % 4
    block = 1536

    def sweep():
        values = {}
        for off in range(0, length, block):
            n = min(block, length - off)
            t = time.time()
            data = c.read_ranges([(start + off, n)])[0]
            for i in range(0, n, 4):
                values[start + off + i] = (t, int.from_bytes(data[i:i + 4], "little"))
        return values

    print(f"Reading 0x{start:08X}-0x{start + length:08X} twice (about {max(3.0, 2 + 2 * length / 10000):.0f} s)...")
    t0 = time.time()
    first = sweep()
    # At least 2 s apart, so a counter's rate isn't lost in the rounding.
    time.sleep(max(0.0, 2.0 - (time.time() - t0)))
    second = sweep()
    hits = []
    for a, (t0, v0) in first.items():
        t1, v1 = second[a]
        rate = ((v1 - v0) & 0xFFFFFFFF) / max(1e-3, t1 - t0)
        if any(0.85 * r <= rate <= 1.15 * r for r in FRAME_RATES):
            hits.append(a)
    if not hits:
        return []
    time.sleep(1.0)
    confirmed = []
    for a in hits[:64]:
        t2 = time.time()
        v2 = int.from_bytes(c.read_ranges([(a, 4)])[0], "little")
        t1, v1 = second[a]
        rate = ((v2 - v1) & 0xFFFFFFFF) / max(1e-3, t2 - t1)
        if any(0.85 * r <= rate <= 1.15 * r for r in FRAME_RATES):
            confirmed.append((a, rate))
    return confirmed


def capture(c, watches, seconds, arm7_only=False):
    """Runs the capture for `seconds`. Returns (records, stats): records are
    (record number, tick, scanline, [values], by_arm7) with a None entry
    wherever records were lost."""
    sizes = [n for _, n in watches]
    c.set_watch(watches, arm7_only=arm7_only)
    records, nxt, lost_total = [], 0, 0
    fetches = timeouts = 0
    longest_wait, last_ok = 0.0, time.time()
    end = time.time() + seconds
    try:
        while time.time() < end:
            try:
                first, lost, recs = c.fetch_frames(nxt, timeout=0.3)
            except TimeoutError:
                timeouts += 1
                continue
            now = time.time()
            longest_wait = max(longest_wait, now - last_ok)
            last_ok = now
            fetches += 1
            if lost:
                lost_total += lost
                records.append(None)
            for i, (tick, vcount, raw, by_arm7) in enumerate(recs):
                records.append(((first + i) & 0xFFFF, tick, vcount, split_values(raw, sizes), by_arm7))
            nxt = (first + len(recs)) & 0xFFFF
            if len(recs) < 4:
                time.sleep(0.04)  # caught up; let a few frames build up
    finally:
        try:
            c.set_watch([])
        except (TimeoutError, RuntimeError):
            pass
    got = sum(1 for r in records if r)
    return records, {"records": got, "lost": lost_total, "fetches": fetches,
                     "timeouts": timeouts, "longest_wait": longest_wait}


def analyse(records):
    """Frame-to-frame steps of the first watch, within unbroken stretches.
    Returns a dict: steps, ups (+1), still (0), resets (went down), and
    catchups: [(by, scanline of the late read, scanline of the catch-up)]
    for every step of +2 or more (`by` = how many counts were seen late)."""
    out = {"steps": 0, "ups": 0, "still": 0, "resets": 0, "increase": 0, "catchups": []}
    prev = None
    for r in records:
        if r is None:
            prev = None
            continue
        if prev is not None:
            d = (r[3][0] - prev[3][0]) & 0xFFFFFFFF
            out["steps"] += 1
            if d > 0x7FFFFFFF:
                out["resets"] += 1
                d = 0
            elif d == 0:
                out["still"] += 1
            elif d == 1:
                out["ups"] += 1
            else:
                out["catchups"].append((d - 1, prev[2], r[2]))
            out["increase"] += d
        prev = r
    return out


def only(records, by_arm7):
    """The records read by one CPU, with a break wherever the other one (or
    a loss) came in between, so steps never mix the two."""
    return [r if r is not None and r[4] == by_arm7 else None for r in records]


def log_paths(name):
    """(CSV path, report path) for --save NAME: a bare name (with or without
    .csv) goes in logs/, a path with a folder in it is used as given."""
    p = Path(name)
    if p.suffix.lower() != ".csv":
        p = p.with_name(p.name + ".csv")
    if p.parent == Path("."):
        p = LOGS_DIR / p.name
    return p, p.with_suffix(".txt")


class Tee:
    """Writes everything to the console and to a file."""

    def __init__(self, stream, f):
        self.stream, self.f = stream, f

    def write(self, text):
        self.stream.write(text)
        self.f.write(text)

    def flush(self):
        self.stream.flush()
        self.f.flush()


def a9_status(a9):
    """What a hello's a9= says about the ARM9 half."""
    if a9 is None:
        # Builds from before the ARM9 half don't mark their records, but the
        # ARM7 read all of them.
        return "not in this build (no a9= in the hellos): every value is read by the ARM7"
    n = int(a9) if a9.isdigit() else 0
    if n == 0:
        return "not found (a9=0): every value will be read by the ARM7"
    if n == 1:
        return "found (a9=1)"
    if n == 2:
        return "found, VBlank hook in (a9=2)"
    return (f"found, VBlank hook in (a9={n}: the game replaced its VBlank handler "
            f"{n - 2} time{'s' if n > 3 else ''} and the hook was put back)")


def save_csv(path, watches, records):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record", "tick", "scanline", "read_by"] + [f"0x{a:08X}" for a, _ in watches])
        for r in records:
            if r is None:
                w.writerow(["lost"])
            else:
                w.writerow([r[0], r[1], r[2], "arm7" if r[4] else "arm9"] + r[3])


def main():
    ap = argparse.ArgumentParser(description="Measure whether the DSi's per-frame capture sees every frame")
    ap.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    ap.add_argument("--seconds", type=float, default=20.0, help="how long to capture (default 20)")
    ap.add_argument("--watch", nargs="+", type=parse_watch, metavar="ADDR:SIZE",
                    help="values to capture every frame; the first must be a frame counter "
                         "(default: Platinum's VBlank counter)")
    ap.add_argument("--find-counter", type=parse_span, metavar="ADDR:LEN",
                    help="look for frame counters in this range instead (about 10 KB/s, so keep it small)")
    ap.add_argument("--save", metavar="NAME",
                    help="also save every record to logs/NAME.csv and this report to logs/NAME.txt")
    ap.add_argument("--arm7-only", action="store_true",
                    help="have the ARM7 read every value itself, as before the ARM9 half (to compare)")
    args = ap.parse_args()

    csv_path = report_path = None
    if args.save:
        csv_path, report_path = log_paths(args.save)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        report = open(report_path, "w", encoding="utf-8")
        sys.stdout = Tee(sys.stdout, report)
    try:
        run(args, csv_path)
    finally:
        if report_path:
            sys.stdout.flush()
            print(f"Saved this report to {shown(report_path)}")
            sys.stdout = sys.stdout.stream
            report.close()


def shown(path):
    """A path as short as it can be: relative to the current folder if it's in it."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def run(args, csv_path):
    c = DSiClient(port=args.port, dsi_ip=args.dsi_ip)
    if not c.wait_for_dsi():
        print("No hello from the DSi within 15 s - is the game running after the handoff?")
        sys.exit(1)
    if c.game is None:
        c.listen(2.5)  # with --dsi-ip no hello has arrived yet
    code = c.game["code"] if c.game else None
    print(f"Game: {code or 'not reported (older rpcprobe build: per-frame capture needs the new one)'}")
    a9 = _hello_fields(c.last_hello or "").get("a9")
    print("ARM9 half: " + a9_status(a9))

    if args.find_counter:
        start, length = args.find_counter
        hits = find_counters(c, start, length)
        if not hits:
            print("No value in that range went up by 60 or 30 a second.")
            return
        print("Frame counters (goes up by about this much a second):")
        for a, rate in hits:
            print(f"  0x{a:08X}  {rate:5.1f}/s   python frame_check.py --watch 0x{a:08X}:4")
        return

    watches = args.watch or ([KNOWN_COUNTERS[code]] if code in KNOWN_COUNTERS else None)
    if not watches:
        print("No frame counter known for this game: pass --watch ADDR:4 (or find one with --find-counter).")
        sys.exit(1)
    if len(watches) > MAX_WATCHES:
        print(f"At most {MAX_WATCHES} watches.")
        sys.exit(1)

    print(f"Capturing {len(watches)} value(s) every frame for {args.seconds:g} s; "
          "play normally (walking around is a good test)...")
    try:
        records, st = capture(c, watches, args.seconds, arm7_only=args.arm7_only)
        if a9 is None:
            records = [r[:4] + (True,) if r else r for r in records]
    except RuntimeError as e:
        print(f"The DSi refused the capture ({e}). Is this the per-frame capture build of nds-bootstrap?")
        sys.exit(1)

    expected = int(args.seconds * 60)
    print(f"\nRecords: {st['records']} (about {expected} frames in {args.seconds:g} s); "
          f"lost to a full ring: {st['lost']}; fetches: {st['fetches']}, timed out: {st['timeouts']}, "
          f"longest gap between replies: {st['longest_wait'] * 1000:.0f} ms")
    real = [r for r in records if r]
    if len(real) < 2:
        print("Not enough records to say anything.")
        sys.exit(1)

    by9 = [r for r in real if not r[4]]
    by7 = [r for r in real if r[4]]
    print(f"Read by the ARM9: {len(by9)}; by the ARM7: {len(by7)}"
          + (" (it fills in when there's no ARM9 snapshot to record)" if by9 and by7 else ""))
    for name, group in (("ARM9", by9), ("ARM7", by7)):
        if group:
            vc = sorted(r[2] for r in group)
            print(f"  {name} read at scanline {vc[0]}-{vc[-1]} (median {vc[len(vc) // 2]}; 192 is the start of VBlank)")
    a9_end = _hello_fields(c.last_hello or "").get("a9")
    if a9 is not None and a9_end != a9:
        print(f"ARM9 half at the end: {a9_status(a9_end)}")

    if csv_path:
        save_csv(csv_path, watches, records)
        print(f"Saved every record to {shown(csv_path)}")

    # Judge the ARM9's records on their own when there are any: its values are
    # a VBlank older than the ARM7's, so a step between the two isn't a step
    # the game took.
    judged = "ARM9" if by9 else "ARM7"
    a = analyse(only(records, by_arm7=not by9))
    steps, catchups = a["steps"], a["catchups"]
    if by9 and by7:
        print(f"\n(Steps between two {judged} records only.)")
    rate = a["increase"] * 60.0 / max(1, steps)
    print(f"\nVBlank counter at 0x{watches[0][0]:08X}: went up {rate:.1f} times a second "
          f"(60 = every frame, 30 = every other frame). Over {steps} frame-to-frame steps:")
    print(f"  went up by one                 {a['ups']:6d}")
    print(f"  didn't change                  {a['still']:6d}  (the game didn't count that frame: fine)")
    print(f"  caught up by 2 or more         {len(catchups):6d}  (the reads before were late)")
    if a["resets"]:
        print(f"  went down (game reset?)        {a['resets']:6d}")
    if catchups:
        by = {}
        for n, _, _ in catchups:
            by[n] = by.get(n, 0) + 1
        print("  late by: " + ", ".join(f"{n} frame{'s' if n > 1 else ''} x{k}" for n, k in sorted(by.items())))
        one = [c for c in catchups if c[0] == 1]
        if one:
            early = sum(1 for _, before, after in one if before < after)
            print(f"  one-frame lates: the late read was at an earlier scanline than the catch-up in {early} of "
                  f"{len(one)} (a race at the start of VBlank looks like that)")

    for i, (addr, n) in enumerate(watches[1:], start=1):
        vals = [r[3][i] for r in (by9 or real)]
        changes = sum(1 for x, y in zip(vals, vals[1:]) if x != y)
        print(f"  watch 0x{addr:08X}:{n} changed on {changes} of {len(vals) - 1} frames")

    late = len(catchups)
    longer = sum(1 for n, _, _ in catchups if n > 1)
    print()
    if steps == 0:
        print(f"-> Not enough {judged} records in a row to judge.")
    elif late == 0:
        print(f"-> No {judged} read was ever late: the capture matched the game frame for frame.")
    elif late <= 0.005 * steps:
        print(f"-> {late} late reads in {steps} frames: rare. Fine for most achievements; "
              "worth more runs on other screens before deciding.")
    else:
        print(f"-> {late} late reads in {steps} frames ({100.0 * late / steps:.1f}%), {longer} of them by more "
              "than one frame. Too many for achievements that compare frame to frame, if it happens in play.")
    # The DSi numbers its samples itself; within an unbroken stretch they
    # must go up by one per record, or records went missing on the way.
    gaps = sum(1 for r1, r2 in zip(records, records[1:]) if r1 and r2 and (r2[1] - r1[1]) & 0xFFFF != 1)
    if gaps:
        print(f"(The DSi's sample numbers skipped {gaps} time(s) between records: send this output along.)")


if __name__ == "__main__":
    main()
