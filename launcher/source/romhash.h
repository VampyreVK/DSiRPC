// SPDX-License-Identifier: MIT
//
// RetroAchievements' hash of a DS game file: the same MD5 every RA emulator
// computes (rcheevos' rc_hash_nintendo_ds, which DSiRPC's core/ra_hash.py
// ports too), of the header's first 0x160 bytes, the ARM9 and ARM7 code and
// the 0xA00-byte icon and title block. RetroAchievements says by it which
// game, and which version of it, a file is (picker.c's first-time setup
// hashes each game once, and DSiRPC asks).

#ifndef ROMHASH_H__
#define ROMHASH_H__

#include <stdint.h>

enum
{
    ROMHASH_UNREADABLE = -1,    // can't be opened or read
    ROMHASH_NOT_DS = 0,         // too short for a DS game, or its code over 16 MB (as rcheevos refuses)
    ROMHASH_OK = 1,
};

// How far it got: bytes hashed of the total it hashes
typedef void (*RomHashProgress)(uint32_t done, uint32_t total, void *ctx);

// The file's hash in out (16 bytes). progress may be NULL.
int rom_hash(const char *path, uint8_t out[16], RomHashProgress progress, void *ctx);

#endif // ROMHASH_H__
