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

The places come from how far round the course each racer is: its lap, the
last checkpoint it passed, and how far it is toward the next one. The code
notes' place byte (`0x02368754`) isn't used: on the console it reads the same
whatever your place (08 all race, for one), which put you last and everyone
else a place up.

**Where the game keeps the places.** With DSiRPC running, race a Grand Prix
race past the 1-minute mark. The log (`logs\dsirpc.log`) gets two lines like
this, about 20 s and 60 s into the race:

```
Mario Kart DS: place probe at 20.4 s: the place byte 0x02368754 reads 00 (...); worked-out order [5, 1, ...]; race status bytes that rank the racers: +0x5C (1-based, 8 of 8 agree)
```

Note your place and the places on the bottom screen at that moment if you can,
and send me both lines. An offset that ranks the racers in both lines is
almost certainly where the game keeps everyone's place, and then the overlay
can use the game's own order.

**The lap and checkpoint counting.** First get the race status pointer:

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

## 3. Items

The item box reads the item pointer at `0x0217BC2C` (four bytes, lowest
first, like the status pointer above). Your item is at that pointer + 0x4C and
how many at + 0x54. With the pointer `0x0218A000`, say:

```
python core\dsirpc_client.py --watch 0x0218A04C:1 0x0218A054:1
```

Note the first number for each item you get. The ones not checked yet are
1 Red Shell, 3 Fake Item Box, 4 Mushroom, 5 Triple Mushrooms, 9 Triple Green
Shells, 10 (0x0A) Triple Bananas and 13 (0x0D) Golden Mushroom. 0x13 means
no item.

**The roulette.** While the item roulette spins, the overlay shows whatever
the item byte says (an empty box if it stays 0x13). To find a byte that says
it's spinning, watch the whole start of your item's block through a few item
boxes:

```
python core\dsirpc_client.py --watch 0x0218A040:32 --settle 3
```

Stay still for the 3 settle seconds, then drive through an item box. Send me
which addresses change when the roulette starts and when it stops.

## 4. Grand Prix standings

In a Grand Prix the right column shows your points in the cup, from the
standings pointer at `0x022AC39C`, + 0x30 (the RetroAchievements set's 3-star
cup achievements read it). Nothing known gives the other racers' points, so
the overlay can't show your place in the cup yet. To find them, get the
pointer:

```
python core\dsirpc_client.py --read 0x022AC39C:4
```

and over the results screen after a race, watch around your points (with the
pointer `0x0229F000`, say):

```
python core\dsirpc_client.py --watch 0x0229F000:256 --settle 3
```

Each race gives 10, 8, 6, 4, 3, 2, 1 and 0 points by place, so after the
first race eight bytes should take those values. Send me which addresses
change and to what.

## 5. Mirror mode

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

## 6. Time Trial

In Time Trial only you are shown. If a ghost is racing, check that the
overlay doesn't put a second racer on the map.

## 7. Starting and ending a race

The race view shows once a race has read steadily for 0.4 s, and stays until
2 s after the last read with a race in it. At the countdown it shouldn't
switch back to the game card any more. If it still does, the log has lines
like `Mario Kart DS: no race in this read (no racers)` around that moment:
send me them. After the results, back in the menus, the overlay should go back
to the game card about 2 s later. If it stays on the race, tell me what screen
you're on.
