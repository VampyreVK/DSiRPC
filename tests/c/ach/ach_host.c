// Host driver for offline play's checker (rpcprobe/probe_ach.c with
// probe_ach_vm.c), for tests/test_offline_checker.py. The SD card's
// RPCSET.BIN and RPCUNLK.BIN, main RAM, VCOUNT and the clock are the PC's.
//
// Commands on stdin, one per line:
//   unlockfile <path>     RPCUNLK.BIN's contents for the next `set` (else an
//                         empty file)
//   set <path> [code]     load RPCSET.BIN from a file, as a game whose header
//                         says `code` (default: the set's own); path "-": no
//                         RPCSET.BIN (a game without a set)
//   w <addr> <hexbytes>   write the game's memory (RetroAchievements address)
//   frame <idle> <visits> [romwait] [fresh] [nullwait]
//                         a VBlank: the frame lane samples, then the tick (the
//                         idle side alive or not), then <visits> visits of
//                         the swiHalt hook. romwait: an ARM9 ROM read waits
//                         at the first visit (the hook serves it, then calls
//                         again); fresh 0: no write-back from the ARM9 since
//                         the last VBlank; nullwait: the visits pass no
//                         romWaiting (altReadMethod games)
//   push <id> <when>      DSiRPC's unlock
//   save                  write every unlock waiting to RPCUNLK.BIN
//   dump <path>           write RPCUNLK.BIN's contents to a file
//   stats                 print the report's numbers
//   list                  print the menu list's marked entries
// Prints "T <id>" for each new unlock, as soon as the checker has it.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nds/ndstypes.h"
#include "my_fat.h"
#include "dsirpc_ach_menu.h"
#include "probe_ach.h"

uint8_t hostAch[0x40000] __attribute__((aligned(4)));
uint8_t hostRam[0x400000] __attribute__((aligned(4)));
static uint8_t setFile[0x40000], unlockFile[4096];
static uint32_t setLen;
static int haveUnlockFile, unlockFileGiven;

// The scanline counter: one line every `perLine` reads
static uint32_t vreads, perLine = 40, vline = 192;
u16 hostVcount(void) { if (++vreads % perLine == 0) vline = (vline + 1) % 263; return (u16)vline; }
// The console's clock: 2026-10-09 12:00:00
int hostRtc(u8 *t) { t[0] = 26; t[1] = 10; t[2] = 9; t[3] = 5; t[4] = 12; t[5] = 0; t[6] = 0; return 1; }

// nds-bootstrap's loader finds the files (RPCHAND.TXT, RPCSET.BIN, RPCUNLK.BIN)
u32 rpcClusters[3] = { 1, 2, 3 };
void getFileFromCluster(aFile *f, u32 cluster, int x) {
	(void)x;
	if (cluster == 2) { f->firstCluster = setLen ? 1 : 0; f->which = 0; }
	else { f->firstCluster = cluster == 3 && haveUnlockFile ? 1 : 0; f->which = 1; }
}
uint32_t fileRead(char *buf, aFile *f, uint32_t at, uint32_t len) {
	uint8_t *src = f->which ? unlockFile : setFile;
	uint32_t size = f->which ? sizeof unlockFile : sizeof setFile;
	if (at > size || len > size - at) { printf("bad read %u+%u\n", at, len); exit(3); }
	memcpy(buf, src + at, len);
	return len;
}
uint32_t fileWrite(const char *buf, aFile *f, uint32_t at, uint32_t len) {
	if (!f->which || at > sizeof unlockFile || len > sizeof unlockFile - at) { printf("bad write %u+%u\n", at, len); exit(3); }
	memcpy(unlockFile + at, buf, len);
	return len;
}

// probe_watch.c: a write-back from the ARM9 since the last VBlank
static int fresh = 1;
int ProbeWatch_Fresh(void) { return fresh; }

static int romWait;
static int romWaiting(void) { return romWait; }

static int readFile(const char *path, uint8_t *buf, uint32_t max, uint32_t *len) {
	FILE *f = fopen(path, "rb");
	if (!f) return 0;
	*len = (uint32_t)fread(buf, 1, max, f);
	fclose(f);
	return 1;
}

int main(void) {
	static char line[1 << 16];
	u16 seen = 0;
	while (fgets(line, sizeof line, stdin)) {
		char cmd[16];
		if (sscanf(line, "%15s", cmd) != 1) continue;
		if (!strcmp(cmd, "unlockfile")) {
			char path[512]; uint32_t n;
			if (sscanf(line + 11, "%511s", path) != 1 || !readFile(path, unlockFile, sizeof unlockFile, &n)) return 4;
			unlockFileGiven = 1;
		} else if (!strcmp(cmd, "set")) {
			char path[512], code[8] = "";
			if (sscanf(line + 4, "%511s %7s", path, code) < 1) return 4;
			if (!strcmp(path, "-")) setLen = 0;
			else if (!readFile(path, setFile, sizeof setFile, &setLen)) return 4;
			if (!unlockFileGiven) {
				memset(unlockFile, 0, sizeof unlockFile);
				memcpy(unlockFile, "DRUL\x01\x00\x10\x00\x00\x01", 10);
			}
			haveUnlockFile = 1;
			u8 header[0x200] = {0};
			memcpy(header + 0x0C, code[0] ? (const u8 *)code : setFile + 8, 4);
			ProbeAch_SetTime(1000);
			ProbeAch_Load(header);
			printf("loaded %d waiting %u\n", probeAchLoaded, probeAchWaiting);
		} else if (!strcmp(cmd, "w")) {
			unsigned a; static char hex[1 << 15];
			if (sscanf(line + 2, "%x %32767s", &a, hex) != 2) return 4;
			for (size_t i = 0; hex[2 * i]; i++) { unsigned b; sscanf(hex + 2 * i, "%2x", &b); hostRam[a + i] = (u8)b; }
		} else if (!strcmp(cmd, "frame")) {
			int idle = 0, visits = 0, rw = 0, fr = 1, nullWait = 0;
			sscanf(line + 6, "%d %d %d %d %d", &idle, &visits, &rw, &fr, &nullWait);
			fresh = fr;
			vline = 192;
			ProbeAch_Sample();
			ProbeAch_Tick(192, idle);
			for (int v = 0; v < visits; v++) {
				vline = (vline + 7) % 263;
				if (nullWait) {
					ProbeAch_Idle(NULL);
					continue;
				}
				romWait = rw && (v == 0);
				if (ProbeAch_Idle(romWaiting)) { romWait = 0; ProbeAch_Idle(romWaiting); }
			}
		} else if (!strcmp(cmd, "push")) {
			unsigned id, when;
			if (sscanf(line + 5, "%u %u", &id, &when) != 2) return 4;
			printf("pushed %d\n", ProbeAch_Push(id, when));
		} else if (!strcmp(cmd, "save")) {
			int n = 0;
			while (ProbeAch_SavePending() && n < 1000) { ProbeAch_SaveOne(); n++; }
			printf("saved %d total %u failed %u lost %u\n", n, probeAchSaved, probeAchSaveFailed, probeAchLost);
		} else if (!strcmp(cmd, "dump")) {
			char path[512];
			if (sscanf(line + 5, "%511s", path) != 1) return 4;
			FILE *f = fopen(path, "wb");
			if (!f) return 4;
			fwrite(unlockFile, 1, sizeof unlockFile, f);
			fclose(f);
		} else if (!strcmp(cmd, "stats")) {
			ProbeAchStats s; ProbeAch_TakeStats(&s);
			printf("stats loaded=%d frame=%u passes=%u frames=%u dropped=%u unclean=%u idle=%u lines=%u trig=%u stamp=%08X\n",
			       probeAchLoaded, probeAchFrameLane, s.passes, s.frames, s.dropped, s.unclean, s.idle, s.maxLines,
			       probeAchTriggered, probeAchStamp);
		} else if (!strcmp(cmd, "list")) {
			const DsirpcMenuAnchor *an = (const DsirpcMenuAnchor *)(hostAch + DSIRPC_MENU_ANCHOR_OFFSET);
			if (!an->list) { printf("nolist status=%d\n", an->status); continue; }
			const DsirpcList *l = (const DsirpcList *)(hostAch + an->list);
			const DsirpcListEntry *e = (const DsirpcListEntry *)(l + 1);
			for (int i = 0; i < l->count; i++)
				if (e[i].flags & 3) printf("L %u flags=%u when=%u seq=%u\n", e[i].id, e[i].flags, e[i].when, e[i].seq);
			printf("Lend unlocks=%u status=%d\n", an->unlocks, an->status);
		} else {
			printf("unknown command %s\n", cmd);
			return 4;
		}
		if (probeAchTriggered != seen) {
			u32 ids[8]; int n = ProbeAch_RecentIds(ids, 8);
			int newer = probeAchTriggered - seen; if (newer > n) newer = n;
			for (int i = n - newer; i < n; i++) printf("T %u\n", ids[i]);
			seen = probeAchTriggered;
		}
		fflush(stdout);
	}
	return 0;
}
