// Host stand-in for libnds' nds/ndstypes.h: just the types and BIT() that
// rpcprobe's and the ARM9 half's code use, so they compile with the PC's gcc.
#pragma once
#include <stdint.h>
#include <stdbool.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int8_t s8; typedef int16_t s16; typedef int32_t s32;
typedef volatile u8 vu8; typedef volatile u16 vu16; typedef volatile u32 vu32; typedef volatile s32 vs32;
typedef volatile uint16_t vuint16; typedef volatile uint32_t vuint32;
#ifndef BIT
#define BIT(n) (1u << (n))
#endif
