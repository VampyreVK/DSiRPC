# Mario Kart DS: checks on the console

The overlay's race view (`overlay/mkds.py`) reads Mario Kart DS (USA, `AMCE`)
from addresses that come from other people's work, not from this console
(`core/mkds_reader.py` lists each one and where it's from). These checks
confirm the ones that matter most. Each takes a few minutes in a race.

Before the `dsirpc_client.py` steps, close DSiRPC: only one program can use
UDP port 4244. Run the commands from the repo folder while the race is on.

## 1. The racers' characters

The reader takes driver *n*'s character from `0x023CDD40 + 0x30 * n`
(worked out from two cheats; the player is driver 0). In a Grand Prix race:

```
python core\dsirpc_client.py --read 0x023CDD40:1 0x023CDD70:1 0x023CDDA0:1 0x023CDDD0:1 0x023CDE00:1 0x023CDE30:1 0x023CDE60:1 0x023CDE90:1
```

You should get eight different numbers, the first being your character:
0 Mario, 1 DK, 2 Toad, 3 Bowser, 4 Peach, 5 Wario, 6 Yoshi, 7 Luigi,
8 Dry Bones, 9 Daisy, 10 (0x0A) Waluigi, 11 (0x0B) R.O.B. Check that the
other seven are the CPUs in that race (the bottom screen's map shows their
heads). If they're wrong, the overlay's ranking will show the wrong heads.

## 2. Places

Your own place comes from the game (`0x02368754`). The CPUs' places come from
how far round the course each one is: its lap, the last checkpoint it passed,
and how far it is toward the next one. To check the lap and checkpoint
counting, first get the race status pointer:

```
python core\dsirpc_client.py --read 0x021755FC:4
```

It prints four bytes, lowest first: `00 57 17 02` is `0x02175700`. Add 0x38
for your lap and 0x46 for your last checkpoint, and watch both (with
`0x02175700` that's):

```
python core\dsirpc_client.py --watch 0x02175738:1 0x02175746:1
```

Start this during the countdown and note what the lap and checkpoint are
before you cross the line, then as you cross it, then as you cross it again.
The reader expects the lap to go up by one exactly when the checkpoint goes
back to 0.

Then run DSiRPC with the overlay open, and in a race with CPUs close together
compare the overlay's ranking with the game's bottom screen. If CPUs swap
places in the overlay well before or after they do in the game, tell me with
the numbers from the watch above.

## 3. Mirror mode

The course maps were lined up using the courses' checkpoints from the game's
files. In a normal race, DSiRPC's log (`logs\dsirpc.log`) has a line like:

```
Mario Kart DS: Figure-8 Circuit, 26 checkpoints, the finish line's middle at (-80, 0)
```

Play a Mirror race (any course) with DSiRPC running and find the same line,
marked `(mirror)`. If its finish line is at the normal position with the x
negated, the overlay shows the map flipped. If it's at the normal position,
the map shows as it is. If it's anywhere else, the overlay draws just the
line through the checkpoints, with no map: send me that log line.

## 4. Time Trial

In Time Trial only you are shown. If a ghost is racing, check that the
overlay doesn't put a second racer on the map.

## 5. After a race

The race view shows while the racers pointer (`0x0217ACF8`) isn't 0. After
the results, back in the menus, the overlay should go back to the game card
within a couple of seconds. If it stays on the race, tell me what screen
you're on.
