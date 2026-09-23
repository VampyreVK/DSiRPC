// SPDX-License-Identifier: MIT
//
// DSiRPC launcher (grew out of stage 4, the handoff spike).
//
// Connects the DSi's wifi in DSi mode, then exits WITHOUT disconnecting so
// our nds-bootstrap build can boot Pokemon Platinum and keep using the
// connection (the "handoff").
//
// Flow:
//   1. Connect with DSWiFi in DSi mode using the saved WFC settings (the same
//      slots the DSi menu uses - no passphrase in any file on the SD card).
//   2. Show IP, gateway, mask and the DSi's MAC address.
//   3. Send a few UDP test packets to the PC (pc_ip from /RPCPROBE.CFG, port
//      4242, spikes/stage1-listen/pc/listener.py).
//   4. Write the connection info to sd:/RPCHAND.TXT, which the in-game side
//      of nds-bootstrap reads to address its packets.
//   5. START: exit WITHOUT disconnecting (then launch our nds-bootstrap).
//      SELECT: disconnect cleanly, then exit.

#include <stdio.h>
#include <string.h>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>

#include <fat.h>
#include <nds.h>
#include <dswifi9.h>

#define LISTENER_PORT     4242
#define CONNECT_TIMEOUT_S 45
#define HELLO_PACKETS     3

static bool read_pc_ip(char *out, size_t out_size)
{
    FILE *f = fopen("sd:/RPCPROBE.CFG", "r");
    if (f == NULL)
        return false;

    bool found = false;
    char line[128];
    while (fgets(line, sizeof(line), f) != NULL)
    {
        if (strncmp(line, "pc_ip=", 6) != 0)
            continue;

        const char *value = line + 6;
        size_t len = strcspn(value, "\r\n \t");
        if ((len > 0) && (len < out_size))
        {
            memcpy(out, value, len);
            out[len] = '\0';
            found = true;
        }
        break;
    }

    fclose(f);
    return found;
}

static void wait_for_key_release(void)
{
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);
        scanKeys();
        if ((keysHeld() & (KEY_START | KEY_SELECT)) == 0)
            break;
    }
}

static int wait_for_start_or_select(void)
{
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);
        scanKeys();
        u32 down = keysDown();
        if (down & KEY_START)
            return KEY_START;
        if (down & KEY_SELECT)
            return KEY_SELECT;
    }
}

static void send_hello_packets(const char *pc_ip, const char *dsi_ip)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
    {
        printf("socket() failed\n");
        return;
    }

    struct sockaddr_in to;
    memset(&to, 0, sizeof(to));
    to.sin_family = AF_INET;
    to.sin_port = htons(LISTENER_PORT);
    to.sin_addr.s_addr = inet_addr(pc_ip);

    for (int i = 0; i < HELLO_PACKETS; i++)
    {
        char msg[96];
        int len = snprintf(msg, sizeof(msg),
                           "DSiRPC spike: hello %d/%d from %s (DSi-mode WPA2)",
                           i + 1, HELLO_PACKETS, dsi_ip);
        if (sendto(sock, msg, len, 0, (struct sockaddr *)&to, sizeof(to)) < 0)
            printf("sendto() failed (packet %d)\n", i + 1);

        // ~1 second between packets
        for (int f = 0; f < 60; f++)
            cothread_yield_irq(IRQ_VBLANK);
    }

    closesocket(sock);
}

int main(int argc, char *argv[])
{
    (void)argc;
    (void)argv;

    consoleDemoInit();

    printf("DSiRPC launcher\n");
    printf("---------------\n");

    if (!isDSiMode())
    {
        printf("\nRunning in DS mode!\n");
        printf("Slots 4-6 and WPA2 need DSi\n");
        printf("mode. Relaunch this app in\n");
        printf("DSi mode.\n\n");
        printf("Press START to exit\n");
        while (wait_for_start_or_select() != KEY_START)
            ;
        return 0;
    }
    printf("Mode: DSi\n");

    bool have_fat = fatInitDefault();
    if (!have_fat)
        printf("SD init failed (no cfg/log)\n");

    char pc_ip[20] = { 0 };
    bool have_pc_ip = have_fat && read_pc_ip(pc_ip, sizeof(pc_ip));
    if (have_pc_ip)
        printf("PC:   %s:%d\n", pc_ip, LISTENER_PORT);
    else
        printf("No pc_ip in /RPCPROBE.CFG,\nskipping UDP test\n");

    printf("\nConnecting with saved\nsettings (slots 1-6)...\n");

    if (!Wifi_InitDefault(INIT_ONLY | WIFI_ATTEMPT_DSI_MODE))
    {
        printf("Wifi_InitDefault() failed\n\nPress START to exit\n");
        while (wait_for_start_or_select() != KEY_START)
            ;
        return 0;
    }

    Wifi_AutoConnect();

    int status = -1;
    int old_status = -1;
    unsigned int frames = 0;
    while (1)
    {
        cothread_yield_irq(IRQ_VBLANK);

        status = Wifi_AssocStatus();
        if (status != old_status)
        {
            printf("  %s\n", ASSOCSTATUS_STRINGS[status]);
            old_status = status;
        }

        if ((status == ASSOCSTATUS_ASSOCIATED) ||
            (status == ASSOCSTATUS_CANNOTCONNECT))
            break;

        frames++;
        if (frames > CONNECT_TIMEOUT_S * 60)
        {
            printf("  Timed out\n");
            break;
        }
    }

    if (status != ASSOCSTATUS_ASSOCIATED)
    {
        printf("\nCould not connect.\n");
        printf("Check slot 4-6 settings in\nSystem Settings > Internet.\n");
        printf("\nPress START to exit\n");
        while (wait_for_start_or_select() != KEY_START)
            ;
        return 0;
    }

    struct in_addr gateway = { 0 }, mask = { 0 }, dns1 = { 0 }, dns2 = { 0 };
    struct in_addr ip = Wifi_GetIPInfo(&gateway, &mask, &dns1, &dns2);

    // inet_ntoa() returns a static buffer, so copy each result before the
    // next call.
    char ip_str[20], gw_str[20], mask_str[20];
    snprintf(ip_str, sizeof(ip_str), "%s", inet_ntoa(ip));
    snprintf(gw_str, sizeof(gw_str), "%s", inet_ntoa(gateway));
    snprintf(mask_str, sizeof(mask_str), "%s", inet_ntoa(mask));

    u8 mac[6] = { 0 };
    Wifi_GetData(WIFIGETDATA_MACADDRESS, sizeof(mac), mac);
    char mac_str[20];
    snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    printf("\nIP:   %s\n", ip_str);
    printf("GW:   %s\n", gw_str);
    printf("Mask: %s\n", mask_str);
    printf("MAC:  %s\n", mac_str);

    if (have_fat)
    {
        // 8.3 name on purpose: nds-bootstrap's ARM7 file lookup only
        // matches short names. The "end" line tells its parser where the
        // real content stops.
        FILE *f = fopen("sd:/RPCHAND.TXT", "w");
        if (f != NULL)
        {
            fprintf(f, "mode=dsi\nip=%s\ngateway=%s\nmask=%s\nmac=%s\nend\n",
                    ip_str, gw_str, mask_str, mac_str);
            fclose(f);
            printf("Wrote sd:/RPCHAND.TXT\n");
        }
    }

    if (have_pc_ip)
    {
        printf("\nSending %d UDP packets...\n", HELLO_PACKETS);
        send_hello_packets(pc_ip, ip_str);
        printf("Done.\n");
    }

    wait_for_key_release();

    printf("\nSTART:  exit, stay connected\n");
    printf("        (then boot the game)\n");
    printf("SELECT: disconnect, then exit\n");

    int key = wait_for_start_or_select();

    if (key == KEY_SELECT)
    {
        printf("Disconnecting...\n");
        Wifi_DisconnectAP();
        Wifi_DisableWifi();
        for (int f = 0; f < 30; f++)
            cothread_yield_irq(IRQ_VBLANK);
    }

    // No Wifi_DisconnectAP()/Wifi_DisableWifi() on the START path, on
    // purpose: the chip is left associated when control returns to the
    // loader.
    return 0;
}
