# How twl_wifi.c talks to the DSi's wifi chip

`twl_wifi.c` is a tiny, polled subset of BlocksDS DSWiFi's DSi-mode driver
(`source/arm7/twl/`): CMD53 block transfers to move packets both ways, and
CMD52 for register reads and as the fallback. It never initializes or resets the
chip. It only sends and receives packets through the connection the
launcher already made. This file records how that works, and what could be
improved.

## Registers (SDIO function 1)

| Addr  | Name                  | Use |
|-------|-----------------------|-----|
| 0x400 | HOST_INT_STATUS       | bit 0 = mailbox 0 has data waiting |
| 0x402 | ERROR_INT_STATUS      | bit 0 = TX overflow (checked after every send) |
| 0x408 | RX_LOOKAHEAD0 (u32)   | header of the next waiting packet |

## Sending

A packet goes into mailbox 0 with a 6-byte header (type 2 = data, no ack,
length, flags `0x2008`), followed by the data header DSWiFi uses: an unknown
u16, destination MAC, source MAC, big-endian length, then LLC/SNAP and the
IP packet. The mailbox's extended window ends at `0x4000`, and writing the
last byte at `0x3FFF` marks the end of the message.

## Receiving (`TwlWifi_RxPending` / `TwlWifi_ReadPacket` / `TwlWifi_RxBusy`)

1. If `0x400` bit 0 is clear, nothing is waiting.
2. Read the lookahead at `0x408`: byte 0 = type, byte 1 = "ack present",
   bytes 2-3 = length (`len`).
3. The packet occupies `round_up(len + 6, 0x80)` bytes and is read ending
   at the last mailbox address (starting at `0x4000 - full_len`). The whole
   packet is always drained, even the part that doesn't fit the buffer.
   With `RPCPROBE_RX_CMD53` (the default) that's one CMD53 block read, see
   below. Otherwise it's one CMD52 per byte, which mirrors the send path and
   works on hardware.
   The chip only treats the message as consumed when its last address is
   read, so `TwlWifi_ReadPacket` reads at most a byte budget per call
   (`RPCPROBE_RX_BYTES_PER_VBLANK`, 128) and continues the same packet on
   the next VBlank. `TwlWifi_RxBusy` is 1 while a packet is half read;
   nothing is sent in the meantime.
4. Types 2-5 are data. The data header starts at byte 6: RSSI, unknown,
   dst MAC, src MAC, big-endian length, LLC/SNAP, ethertype, then the
   payload. Types 0 (HTC) and 1 (WMI) are chip control messages, which are
   drained and ignored.

`probe_req.c` handles the payload: ARP for our IP, `'R'` memory requests on
port 4244, and counting EAPOL (`0x888E`) frames.

## Cost of CMD52 receiving (and why CMD53)

Every frame the chip receives has to be drained, including other LAN
broadcasts. With CMD52 that's one command per byte (128+ commands per
frame). On a busy home
network that means ~56 packets a second, so a request can wait behind
broadcast traffic (~15-400 ms per request measured). That's fine for Rich
Presence.

All of it runs inside the ARM7's VBlank interrupt. A big frame (a 1.5 KB
broadcast is about 1,540 commands) used to be drained in one interrupt,
which blocks the game's own ARM7 work for several milliseconds and can
make it stutter. The byte budget above caps that; the `vb=` hello field
reports the longest tick. The trade-off is that junk traffic now takes
longer to clear, so requests can wait a little longer behind it.

The numbers: one CMD52 is about 19 µs (a 256-byte hello or reply write takes
about 76 scanlines, 4.8 ms), so 128 bytes per VBlank is about 2.4 ms a tick
and at most one frame and about 7.7 KB per second. Background traffic is
mostly broadcast and multicast frames of one to a few 128-byte blocks, at
somewhere around 20 to 60 frames a second on a home network, which can be
more than that. When the drain falls behind, the chip's receive buffers
fill and it drops frames, including memory requests; the PC then waits out a
one-second timeout per lost request. `core/dsirpc_client.py --stats` measures
this from the PC side.

## CMD53 receiving (`RPCPROBE_RX_CMD53`)

Each received packet is read with one CMD53 block read, set up the way
DSWiFi's `wifi_card_read_func1_block` and `wifi_sdio_send_command` do it:

| Register (controller 2) | Value | Why |
|---|---|---|
| `0x008` STOP | `0x0100` | as DSWiFi's `wifi_sdio_stop()`, before and after |
| `0x004`/`0x006` argument | function 1, block mode (bit 27), incrementing address (bit 26), address `0x4000 - full_len`, block count | the same run of addresses the CMD52 path reads |
| `0x026`, `0x104` block length | `0x80` | the function 1 block size DSWiFi set on the card |
| `0x00A`, `0x108` block count | `full_len / 0x80` | |
| `0x0D8` data control | `0x0002` | 32-bit data |
| `0x100` DATA32 IRQ | `0x0C02` before, `0x0402` after | 32-bit FIFO, clear FIFO; bit 8 reads 1 while a block waits |
| `0x000` command | `0x7C35` | CMD53, 48-bit response, data, read, multiple blocks, bit 14 (as DSWiFi's `cmd53_read`) |

Then, for each block, the CPU waits for bit 8 of `0x100`, clears `RXRDY`
(bit 8 of `0x01E`), and reads 32 words from the FIFO at `0x10C`; the
transfer is done when `0x01C` shows both CMDRESPEND and DATAEND. DSWiFi
moves the data with NDMA; rpcprobe polls instead, so it doesn't share an
NDMA channel with nds-bootstrap's SD card code. Every poll loop has a
limit, and on an error or timeout the transfer is abandoned (STOP, FIFO
cleared, and a CMD52 write of 1 to the CCCR's I/O Abort register, 0x06).

A read counts as good only if its first 4 bytes repeat the packet's
lookahead. If nothing came across, the packet is read with CMD52 instead;
if something did (wrong), the packet is dropped. After three failed CMD53
reads, receiving switches to CMD52 for the rest of the session. The hellos
report the mode (`rxm=53` or `52`) and the failures (`e53=`).

With CMD53 a whole frame costs about one command instead of one per byte,
so each VBlank drains up to `RPCPROBE_RX53_FRAMES_PER_VBLANK` (8) frames or
`RPCPROBE_RX53_BYTES_PER_VBLANK` (2048) bytes, stopping after anything that
sends a reply (one send per VBlank).

Checked on hardware on 2026-09-27: `rxm=53 e53=0`, a 60 s link check lost
none of 231 requests, median reply 16 ms (90% under 22 ms), with about 32
other frames a second being drained.

## CMD53 sending (`RPCPROBE_TX_CMD53`)

The mirror image of receiving, as DSWiFi's `wifi_card_write_func1_block`:
argument with the write bit (31) set, `0x100` = `0x1402` (bit 12 = the
FIFO-has-room IRQ enable instead of bit 11), command `0x6C35` (bit 12, read,
clear). For each block the CPU waits for `TXRQ` (bit 9 of `0x01E`), clears
it and writes 32 words to the FIFO at `0x10C`; the frame (rounded to
`0x80`-byte blocks, as the CMD52 path does) ends at `0x4000`, which marks
the end of the message just like the last CMD52 byte write does.

The chip gives no delivery report, so a CMD53 write that "works" but
produces nothing usable would be silent. Two safeguards: every 10th hello
(`RPCPROBE_HELLO_CMD52_EVERY`, the first included) is still sent with
CMD52, so the PC always finds the DSi; and when the PC sends the same
request (same sequence number) twice more, meaning it never got the
replies, sending switches to CMD52 for the session and the third copy is
answered that way. As with receiving, a write that fails with nothing sent
is redone with CMD52, one that fails part way is dropped (with an I/O
Abort), and three failures switch to CMD52. The hellos report `txm=`,
`t53=` and `rep=`.

Checked against the simulated controller and chip (it checks the write
registers, hands out `TXRQ` block by block and rebuilds the frame from the
FIFO words), including a controller that never asks for data (ends in
`txm=52`, every reply still sent) and a chip that swallows CMD53 frames
(the PC's second re-send switches to CMD52 and the third copy gets its
answer). Checked on hardware on 2026-09-27: `txm=53 t53=0 rep=0`, 227 of
228 requests answered in a 60 s link check (the lost one never reached the
DSi), median reply 15 ms.

Tested against a simulated controller and chip (it checks every register
above and plays the FIFO block by block), including a controller that
never delivers data and one that delivers scrambled data: both end in
`rxm=52` with every request still answered. Not yet run on hardware.

## Not handled

Group-key renewal (the WPA2 group handshake). The chip keeps using the keys
the launcher's DSWiFi driver installed, and nothing answers the router's
renewal messages once the launcher has exited. Depending on the router, that
can end with the DSi being disconnected after a few retries. The `eap`
counter in the hello packets shows when renewals happen. If hellos stop at a
regular interval, check the router's group-key update interval.
