# DSiRPC launcher

A small BlocksDS app that connects the DSi to Wi-Fi in **DSi mode**, then
exits without disconnecting, so our nds-bootstrap build can boot Pokémon
Platinum and keep using the connection. It grew out of stage 4 of the project
(the "handoff spike").

It connects with the WPA2 settings saved in DSi connection slots 4-6 using
BlocksDS + DSWiFi (MIT licensed), and no Wi-Fi password is stored in any file.
Once the game is running, the Wi-Fi chip does the WPA2 encryption itself.

## What it does

1. Connects with the saved Wi-Fi settings in DSi mode.
2. Shows the IP, gateway, mask and the DSi's MAC.
3. Sends 3 UDP test packets to `pc_ip` (from `/RPCPROBE.CFG`) on port 4242.
   `spikes/stage1-listen/pc/listener.py` can show them.
4. Writes `/RPCHAND.TXT` (`mode=dsi`, `ip=`, `gateway=`, `mask=`, `mac=`,
   then `end`) for the in-game side. The name has to be 8.3, because
   nds-bootstrap's ARM7 file lookup only matches short names.
5. **START:** exit **without** disconnecting (then launch our nds-bootstrap).
   **SELECT:** disconnect cleanly, then exit.

## Build

From PowerShell, in the repo root:

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

The output is `dsirpc-launcher.nds`. Copy it to the SD card and start it in
DSi mode.

## Checking the connection

`pc/hello_listener.py` prints the "DSiRPC hello" packets the in-game side
sends once a second (UDP 4244, the `port=` in `/RPCPROBE.CFG`):

```
python launcher\pc\hello_listener.py
```

What each field means is in [docs/DOCUMENTATION.md, section 7](../docs/DOCUMENTATION.md#7-wire-protocol).

## Known limits

- **START returns to your menu**, and you launch our nds-bootstrap build from
  there. Launching it directly from here is planned in [CHAINLOAD.md](CHAINLOAD.md).
- **The launcher relies on `/_nds/nds-bootstrap.ini`.** TWiLight rewrites
  that file whenever you launch something from its game list, so if you last
  launched a different game there, our build boots that game instead.
- **Group-key renewals aren't handled after the launcher exits.** DSWiFi's
  driver does them in software, and once the launcher exits nothing is
  running that driver. If hello packets stop at a suspiciously regular
  interval, check the router's WPA "group key update interval".
