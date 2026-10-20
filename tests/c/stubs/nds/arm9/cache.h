// Host stand-in for libnds' nds/arm9/cache.h: the tests define these and
// count the calls.
#pragma once
void DC_FlushRange(const void *base, unsigned int size);
void DC_InvalidateRange(const void *base, unsigned int size);
void IC_InvalidateRange(const void *base, unsigned int size);
