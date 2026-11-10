// Host stand-in for libnds' nds/input.h: the keys' bits.
#pragma once
#include <nds/ndstypes.h>
enum {
	KEY_A = BIT(0), KEY_B = BIT(1), KEY_SELECT = BIT(2), KEY_START = BIT(3), KEY_RIGHT = BIT(4),
	KEY_LEFT = BIT(5), KEY_UP = BIT(6), KEY_DOWN = BIT(7), KEY_R = BIT(8), KEY_L = BIT(9), KEY_X = BIT(10),
	KEY_Y = BIT(11), KEY_TOUCH = BIT(12), KEY_LID = BIT(13),
};
