// SPDX-License-Identifier: MIT
//
// MD5 (RFC 1321), small and plain, for romhash.c: RetroAchievements
// identifies a game by an MD5 of parts of its ROM.

#ifndef MD5_H__
#define MD5_H__

#include <stddef.h>
#include <stdint.h>

typedef struct
{
    uint32_t state[4];
    uint64_t length;            // bytes so far
    uint8_t block[64];          // the part of a block not hashed yet
    size_t used;
} Md5;

void md5_init(Md5 *m);
void md5_update(Md5 *m, const void *data, size_t len);
void md5_final(Md5 *m, uint8_t out[16]);

#endif // MD5_H__
