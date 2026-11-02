// A stand-in for DSWiFi (see nds.h)
#include <stdbool.h>

#include <arpa/inet.h>
#include <netinet/in.h>

enum
{
    ASSOCSTATUS_DISCONNECTED, ASSOCSTATUS_SEARCHING, ASSOCSTATUS_AUTHENTICATING, ASSOCSTATUS_ASSOCIATING,
    ASSOCSTATUS_ACQUIRINGDHCP, ASSOCSTATUS_ASSOCIATED, ASSOCSTATUS_CANNOTCONNECT,
};
#define INIT_ONLY               1
#define WIFI_ATTEMPT_DSI_MODE   2
#define WIFIGETDATA_MACADDRESS  0
bool Wifi_InitDefault(int flags);
void Wifi_AutoConnect(void);
int Wifi_AssocStatus(void);
unsigned Wifi_GetIP(void);
struct in_addr Wifi_GetIPInfo(struct in_addr *gateway, struct in_addr *mask, struct in_addr *dns1,
                              struct in_addr *dns2);
int Wifi_GetData(int what, int size, unsigned char *out);
void Wifi_DisconnectAP(void);
void Wifi_DisableWifi(void);
