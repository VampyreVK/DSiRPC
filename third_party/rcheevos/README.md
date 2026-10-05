# rcheevos (prebuilt)

[rcheevos](https://github.com/RetroAchievements/rcheevos) is RetroAchievements'
own rule engine, the library emulators use to run achievement sets.
`core/rcheevos.py` loads it with ctypes to evaluate a game's rich presence
and achievements against the DSi's memory. MIT licence, see
`LICENSE` (copied from the rcheevos repository).

- Version: v12.5.0 (commit `1433173`)
- `rcheevos.dll`: Windows x64 (64-bit Python), built with MinGW-w64. It only
  needs `KERNEL32.dll` and `msvcrt.dll`.

Only the runtime part is built: no `rc_client`, no ROM hashing and no server
API. DSiRPC talks to RetroAchievements itself, in Python (`core/ra_api.py`,
which builds its requests exactly as rcheevos' `src/rapi` does, and
`core/ra_hash.py`, a port of rcheevos' DS ROM hash). From an rcheevos
checkout:

```
x86_64-w64-mingw32-gcc -O2 -shared -DRC_SHARED -Iinclude -Isrc src/rcheevos/*.c src/rhash/md5.c src/rc_compat.c src/rc_util.c src/rc_version.c -o rcheevos.dll -static-libgcc -Wl,--no-insert-timestamp
```
```
x86_64-w64-mingw32-strip rcheevos.dll
```

On Linux the same sources with `gcc -O2 -shared -fPIC -DRC_SHARED ... -o librcheevos.so`
work too (`*.so` files are gitignored, so build it there yourself).
