#include <nds.h>
#include <dswifi9.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <stdio.h>
#include <string.h>

// TODO: set this to your PC's local IPv4 address (same as Stage 1 - run
// "ipconfig" on the PC, use the IPv4 Address under your active Wi-Fi adapter).
#define PC_IP "192.168.2.196"
#define PC_PORT 4242

// Port this DSi listens on for incoming test messages from the PC.
#define DSI_LISTEN_PORT 4243

#define STARTUP_MESSAGE "DSi RPC stage 2 online"
#define EXIT_COMMAND "EXIT"

static void reverse_string(char *s, int len) {
	for (int i = 0; i < len / 2; i++) {
		char tmp = s[i];
		s[i] = s[len - 1 - i];
		s[len - 1 - i] = tmp;
	}
}

int main(void) {
	consoleDemoInit();

	iprintf("DSi RPC - Stage 2 echo test\n\n");
	iprintf("Connecting to Wi-Fi (WFC settings)...\n");

	if (!Wifi_InitDefault(WFC_CONNECT)) {
		iprintf("Wifi connect failed.\n");
		goto wait_for_exit;
	}

	{
		struct in_addr ip, gateway, mask, dns1, dns2;
		ip = Wifi_GetIPInfo(&gateway, &mask, &dns1, &dns2);
		iprintf("Connected. IP: %s\n\n", inet_ntoa(ip));

		int sock = socket(AF_INET, SOCK_DGRAM, 0);
		if (sock < 0) {
			iprintf("socket() failed\n");
			goto wait_for_exit;
		}

		// Bind so we can receive messages on a known port.
		struct sockaddr_in local;
		memset(&local, 0, sizeof(local));
		local.sin_family = AF_INET;
		local.sin_port = htons(DSI_LISTEN_PORT);
		local.sin_addr.s_addr = htonl(INADDR_ANY);

		if (bind(sock, (struct sockaddr *)&local, sizeof(local)) < 0) {
			iprintf("bind() failed\n");
			goto wait_for_exit;
		}

		// Startup ping so the PC knows we're up, same idea as stage 1.
		struct sockaddr_in pcAddr;
		memset(&pcAddr, 0, sizeof(pcAddr));
		pcAddr.sin_family = AF_INET;
		pcAddr.sin_port = htons(PC_PORT);
		pcAddr.sin_addr.s_addr = inet_addr(PC_IP);
		sendto(sock, STARTUP_MESSAGE, strlen(STARTUP_MESSAGE), 0,
			(struct sockaddr *)&pcAddr, sizeof(pcAddr));
		iprintf("Sent startup ping to %s:%d\n\n", PC_IP, PC_PORT);

		iprintf("Listening on port %d...\n", DSI_LISTEN_PORT);
		iprintf("(send \"%s\" from the PC to stop)\n\n", EXIT_COMMAND);

		char buf[256];
		struct sockaddr_in senderAddr;
		socklen_t senderLen;

		// Blocking receive loop - simplest option for this test. This will
		// sit here until a packet arrives, so there's no key-scanning while
		// waiting; sending "EXIT" from the PC is how you stop it cleanly.
		for (;;) {
			senderLen = sizeof(senderAddr);
			int received = recvfrom(sock, buf, sizeof(buf) - 1, 0,
				(struct sockaddr *)&senderAddr, &senderLen);

			if (received < 0) {
				iprintf("recvfrom() failed\n");
				break;
			}

			buf[received] = '\0';
			iprintf("Got: \"%s\"\n", buf);

			if (strcmp(buf, EXIT_COMMAND) == 0) {
				iprintf("Exit command received, stopping.\n");
				break;
			}

			// The verifiable transform: reverse the string before sending
			// it back, so a correct round trip is obvious at a glance.
			reverse_string(buf, received);
			sendto(sock, buf, received, 0,
				(struct sockaddr *)&senderAddr, senderLen);
			iprintf("Echoed back: \"%s\"\n\n", buf);
		}
	}

wait_for_exit:
	iprintf("\nPress START to exit.\n");
	while (pmMainLoop()) {
		swiWaitForVBlank();
		scanKeys();
		if (keysDown() & KEY_START) break;
	}

	return 0;
}
