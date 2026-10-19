// Stands in for nds-bootstrap's FAT code in the offline checker test:
// ach_host.c keeps RPCSET.BIN and RPCUNLK.BIN in memory.
#pragma once
#include <stdint.h>
#define CLUSTER_FREE 0
typedef struct { uint32_t firstCluster; int which; } aFile;
void getBootFileCluster(aFile *f, const char *name, int x);
uint32_t fileRead(char *buf, aFile *f, uint32_t at, uint32_t len);
uint32_t fileWrite(const char *buf, aFile *f, uint32_t at, uint32_t len);
