// Host stand-in for libnds' nds/memory.h: the cartridge header type, by name.
#pragma once
#include <nds/ndstypes.h>
typedef struct { char gameTitle[12]; char gameCode[4]; u8 rest[0x170]; } tNDSHeader;
