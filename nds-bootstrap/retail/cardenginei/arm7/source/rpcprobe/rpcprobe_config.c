// rpcprobe_config.c - see rpcprobe_config.h.
#include "rpcprobe_config.h"
#include "my_fat.h"
#include "debug_file.h"
#include <string.h>

RpcProbeConfig rpcProbeConfig;
RpcProbeHandoff rpcProbeHandoff;

#define CFG_MAX_BYTES     1024
#define DEFAULT_UDP_PORT  4244

static char cfgReadBuf[CFG_MAX_BYTES + 1];

static int atoiLocal(const char *s) {
	int val = 0;
	int neg = 0;
	if (*s == '-') { neg = 1; s++; }
	while (*s >= '0' && *s <= '9') { val = val * 10 + (*s - '0'); s++; }
	return neg ? -val : val;
}

static u8 hexNibble(char c) {
	if (c >= '0' && c <= '9') return (u8)(c - '0');
	if (c >= 'a' && c <= 'f') return (u8)(c - 'a' + 10);
	if (c >= 'A' && c <= 'F') return (u8)(c - 'A' + 10);
	return 0xFF;
}

static u8 parseMac(const char *s, u8 out[6]) {
	for (int i = 0; i < 6; i++) {
		u8 hi = hexNibble(s[0]);
		u8 lo = hexNibble(s[1]);
		if (hi == 0xFF || lo == 0xFF) return 0;
		out[i] = (u8)((hi << 4) | lo);
		s += 2;
		if (i < 5) {
			if (*s != ':' && *s != '-') return 0;
			s++;
		}
	}
	return 1;
}

static u8 parseIp(const char *s, u8 out[4]) {
	int part = 0;
	int val = 0;
	u8 haveDigit = 0;
	for (int i = 0; i < 4; i++) out[i] = 0;
	while (*s) {
		if (*s >= '0' && *s <= '9') {
			val = val * 10 + (*s - '0');
			haveDigit = 1;
		} else if (*s == '.') {
			if (!haveDigit || part > 3 || val > 255) return 0;
			out[part++] = (u8)val;
			val = 0;
			haveDigit = 0;
		} else {
			break;
		}
		s++;
	}
	if (!haveDigit || part != 3 || val > 255) return 0;
	out[part] = (u8)val;
	return 1;
}

static void trimTrailing(char *s) {
	int len = (int)strlen(s);
	while (len > 0 && (s[len-1] == '\r' || s[len-1] == '\n' || s[len-1] == ' ' || s[len-1] == '\t')) {
		s[--len] = 0;
	}
}

static u8 isNonZero(const u8 *p, int n) {
	for (int i = 0; i < n; i++) if (p[i]) return 1;
	return 0;
}

static void applyLine(char *line) {
	while (*line == ' ' || *line == '\t') line++;
	if (*line == '#' || *line == ';' || *line == 0) return;

	char *eq = strchr(line, '=');
	if (!eq) return;
	*eq = 0;
	char *key = line;
	char *value = eq + 1;
	trimTrailing(key);
	trimTrailing(value);

	if (strcmp(key, "pc_mac") == 0) {
		parseMac(value, rpcProbeConfig.pcMac);
	} else if (strcmp(key, "dsi_ip") == 0) {
		parseIp(value, rpcProbeConfig.dsiIp);
	} else if (strcmp(key, "pc_ip") == 0) {
		parseIp(value, rpcProbeConfig.pcIp);
	} else if (strcmp(key, "port") == 0) {
		int port = atoiLocal(value);
		if (port > 0 && port < 65536) rpcProbeConfig.udpPort = (u16)port;
	}
	// Unrecognized keys are ignored on purpose.
}

u8 RpcProbeConfig_Load(void) {
	memset(&rpcProbeConfig, 0, sizeof(rpcProbeConfig));
	rpcProbeConfig.udpPort = DEFAULT_UDP_PORT;

	aFile cfgFile;
	getBootFileCluster(&cfgFile, "RPCPROBE.CFG", 0); // 0 = SD card slot
	if (cfgFile.firstCluster == CLUSTER_FREE) {
		#ifdef DEBUG
		dbg_printf("rpcprobe: RPCPROBE.CFG not found\n");
		#endif
		return 0;
	}

	char *buf = cfgReadBuf;
	u32 readLen = fileRead(buf, &cfgFile, 0, CFG_MAX_BYTES);
	if (readLen > CFG_MAX_BYTES) readLen = CFG_MAX_BYTES;
	buf[readLen] = 0;

	// aFile doesn't expose the file's real byte length, so this reads up to
	// CFG_MAX_BYTES regardless; anything past the true end of file is
	// whatever else sits in that SD cluster. Keep the file short.
	char *line = buf;
	while (*line) {
		char *nl = strchr(line, '\n');
		if (nl) *nl = 0;
		applyLine(line);
		if (!nl) break;
		line = nl + 1;
	}

	rpcProbeConfig.valid = isNonZero(rpcProbeConfig.pcIp, 4);
	#ifdef DEBUG
	dbg_printf(rpcProbeConfig.valid ? "rpcprobe: config loaded\n"
	                                : "rpcprobe: RPCPROBE.CFG found but no usable pc_ip=\n");
	#endif
	return rpcProbeConfig.valid;
}

static void applyHandoffLine(char *line) {
	while (*line == ' ' || *line == '\t') line++;
	char *eq = strchr(line, '=');
	if (!eq) return;
	*eq = 0;
	char *key = line;
	char *value = eq + 1;
	trimTrailing(key);
	trimTrailing(value);

	if (strcmp(key, "mac") == 0) {
		parseMac(value, rpcProbeHandoff.dsiMac);
	} else if (strcmp(key, "ip") == 0) {
		parseIp(value, rpcProbeHandoff.dsiIp);
	} else if (strcmp(key, "gateway") == 0) {
		parseIp(value, rpcProbeHandoff.gateway);
	}
}

u8 RpcProbeHandoff_Load(void) {
	memset(&rpcProbeHandoff, 0, sizeof(rpcProbeHandoff));

	aFile hoFile;
	getBootFileCluster(&hoFile, "RPCHAND.TXT", 0);
	if (hoFile.firstCluster == CLUSTER_FREE) {
		#ifdef DEBUG
		dbg_printf("rpcprobe: RPCHAND.TXT not found (run the launcher first)\n");
		#endif
		return 0;
	}

	const u32 maxBytes = 256;
	char *buf = cfgReadBuf;
	u32 readLen = fileRead(buf, &hoFile, 0, maxBytes);
	if (readLen > maxBytes) readLen = maxBytes;
	buf[readLen] = 0;

	char *line = buf;
	while (*line) {
		char *nl = strchr(line, '\n');
		if (nl) *nl = 0;
		trimTrailing(line);
		if (strcmp(line, "end") == 0) break;
		applyHandoffLine(line);
		if (!nl) break;
		line = nl + 1;
	}

	rpcProbeHandoff.valid = isNonZero(rpcProbeHandoff.dsiMac, 6) && isNonZero(rpcProbeHandoff.dsiIp, 4);
	#ifdef DEBUG
	dbg_printf(rpcProbeHandoff.valid ? "rpcprobe: handoff loaded\n"
	                                 : "rpcprobe: RPCHAND.TXT found but no usable mac=/ip=\n");
	#endif
	return rpcProbeHandoff.valid;
}
