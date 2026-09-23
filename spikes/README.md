# Spikes

These are the early experiments that proved each step of DSiRPC. They're kept
for reference and aren't needed to run the project. Their sources haven't
changed since they were run, but they aren't maintained.

| Stage | Folder | What it proved | Status |
|---|---|---|---|
| 1 | `stage1-listen/` | A standalone DSi homebrew app can connect to Wi-Fi and send a UDP packet to the PC (`pc/listener.py`, port 4242) | Done |
| 2 | `stage2-echo/` | Two-way UDP: the DSi echoes back a reversed string for whatever it receives, and the PC finds the DSi's IP from its startup ping (`pc/echo_test.py`) | Done |
| 3 | `stage3-testrom/` | A synthetic test ROM with known values, meant to check memory reads | Abandoned. It ran through nds-bootstrap's homebrew path, which never uses the retail VBlank hook the real project needs. `pc/probe_client.py` speaks the first request format (`'Q'`/`'A'`), which the DSi side no longer implements. |
| 4 | [`launcher/`](../launcher) | A DSi-mode Wi-Fi connection survives into a retail game booted by nds-bootstrap | Became the launcher |
| 5 | [`core/dsirpc_client.py`](../core/dsirpc_client.py) | Reading game memory over Wi-Fi in batched requests | Became the PC side's protocol client |

Stages 1 and 2 hardcode the PC's IP in `source/main.c` (`PC_IP`), so change
it before building. The spikes use devkitPro's makefiles and the newer libnds
from `devkitpro/devkitarm:latest` (not the older image nds-bootstrap needs).
Mount the folder under its own name, because the output file is named after
it. For example, from PowerShell:

```
docker run --rm -v "C:\Projects\DSiRPC\spikes\stage1-listen:/stage1-listen" -w /stage1-listen devkitpro/devkitarm:latest make
```

The full story is in [docs/HISTORY.md](../docs/HISTORY.md).
