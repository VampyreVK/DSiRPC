// rpcprobe_config.c - see rpcprobe_config.h.
#include "rpcprobe_config.h"
#include "my_fat.h"
#include "debug_file.h"
#include <string.h>

RpcProbeHandoff rpcProbeHandoff;

// The launcher's file is about 100 bytes.
#define HANDOFF_MAX_BYTES 256

static char handoffReadBuf[HANDOFF_MAX_BYTES + 1];

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

	char *buf = handoffReadBuf;
	u32 readLen = fileRead(buf, &hoFile, 0, HANDOFF_MAX_BYTES);
	if (readLen > HANDOFF_MAX_BYTES) readLen = HANDOFF_MAX_BYTES;
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
