# How twl_wifi.c talks to the DSi's wifi chip

`twl_wifi.c` is a tiny, polled, CMD52-only subset of BlocksDS DSWiFi's
DSi-mode driver (`source/arm7/twl/`). It never initializes or resets the
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
   at the last mailbox address (starting at `0x4000 - full_len`), one CMD52
   per byte. The whole packet is always drained, even the part that doesn't
   fit the buffer. This mirrors the send path and works on hardware.
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

## Cost and upgrade path

Every frame the chip receives has to be drained, including other LAN
broadcasts, at one CMD52 per byte (128+ commands per frame). On a busy home
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

The upgrade is CMD53 block transfers (DSWiFi's `wifi_card_read_func1_block`
/ `wifi_card_write_func1_block`): one command per packet and the data read
32 bits at a time from the controller's FIFO, instead of one command per
byte. DSWiFi moves that data with NDMA; a polled FIFO loop (the code DSWiFi
has commented out next to its NDMA calls) would avoid sharing an NDMA
channel with nds-bootstrap. It hasn't been tried on hardware yet.

## Not handled

Group-key renewal (the WPA2 group handshake). The chip keeps using the keys
the launcher's DSWiFi driver installed, and nothing answers the router's
renewal messages once the launcher has exited. Depending on the router, that
can end with the DSi being disconnected after a few retries. The `eap`
counter in the hello packets shows when renewals happen. If hellos stop at a
regular interval, check the router's group-key update interval.
