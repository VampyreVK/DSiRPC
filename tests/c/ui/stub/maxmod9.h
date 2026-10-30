// The maxmod calls the launcher makes (music.c), for the PC: host_stubs.c
// notes each in host_music_log

#ifndef MAXMOD9_H__
#define MAXMOD9_H__

#include <stdbool.h>

typedef unsigned int mm_word;
typedef void *mm_addr;
typedef enum { MM_PLAY_LOOP, MM_PLAY_ONCE } mm_pmode;

bool mmInitDefaultMem(mm_addr soundbank);
void mmLockChannels(mm_word bitmask);
mm_word mmLoad(mm_word module_ID);
mm_word mmUnload(mm_word module_ID);
void mmStart(mm_word module_ID, mm_pmode mode);
void mmStop(void);
void mmSetModuleVolume(mm_word volume);

#endif // MAXMOD9_H__
