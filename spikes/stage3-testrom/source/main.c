#include <nds.h>
#include <stdio.h>

// Known test data - what we'll try to read via the memory probe once the
// nds-bootstrap side can respond to requests. This ROM doesn't know or care
// that anything is reading it; that's the point.
const char known_string[32] = "DSi RPC test data 1234";
volatile uint32_t known_counter = 0;

int main(void) {
	consoleDemoInit();

	iprintf("DSi RPC - Stage 3 test ROM\n\n");
	iprintf("known_string @ %p\n", (void *)known_string);
	iprintf("  = \"%s\"\n\n", known_string);
	iprintf("known_counter @ %p\n\n", (void *)&known_counter);
	iprintf("Counter (updates live):\n");

	while (pmMainLoop()) {
		swiWaitForVBlank();
		scanKeys();

		known_counter++;
		iprintf("\x1b[10;0H%lu   ", (unsigned long)known_counter);

		if (keysDown() & KEY_START) break;
	}

	return 0;
}
