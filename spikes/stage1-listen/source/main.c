#include <nds.h>
#include <dswifi9.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <stdio.h>
#include <string.h>

// TODO: set this to your PC's local IPv4 address (run "ipconfig" on the PC,
// use the IPv4 Address under your active Wi-Fi adapter).
#define PC_IP "192.168.2.196"
#define PC_PORT 4242

#define TEST_MESSAGE "hello from DSi"

int main(void) {
	consoleDemoInit();

	iprintf("DSi RPC - Stage 1 UDP test\n\n");
	iprintf("Connecting to Wi-Fi (WFC settings)...\n");

	if (!Wifi_InitDefault(WFC_CONNECT)) {
		iprintf("Wifi connect failed.\n");
	} else {
		struct in_addr ip, gateway, mask, dns1, dns2;
		ip = Wifi_GetIPInfo(&gateway, &mask, &dns1, &dns2);
		iprintf("Connected. IP: %s\n\n", inet_ntoa(ip));

		int sock = socket(AF_INET, SOCK_DGRAM, 0);
		if (sock < 0) {
			iprintf("socket() failed\n");
		} else {
			struct sockaddr_in dest;
			memset(&dest, 0, sizeof(dest));
			dest.sin_family = AF_INET;
			dest.sin_port = htons(PC_PORT);
			dest.sin_addr.s_addr = inet_addr(PC_IP);

			int sent = sendto(sock, TEST_MESSAGE, strlen(TEST_MESSAGE), 0,
				(struct sockaddr *)&dest, sizeof(dest));

			if (sent < 0) {
				iprintf("sendto() failed\n");
			} else {
				iprintf("Sent %d bytes to %s:%d\n", sent, PC_IP, PC_PORT);
				iprintf("\"%s\"\n", TEST_MESSAGE);
			}
		}
	}

	iprintf("\nPress START to exit.\n");

	while (pmMainLoop()) {
		swiWaitForVBlank();
		scanKeys();
		if (keysDown() & KEY_START) break;
	}

	return 0;
}
