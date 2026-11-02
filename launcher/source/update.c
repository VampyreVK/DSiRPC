// SPDX-License-Identifier: MIT
//
// Updating the launcher and our nds-bootstrap build from DSiRPC (see
// update.h). DSiRPC's core/console_update.py is the other side and describes
// the exchange, which never changes, so this launcher can update itself from
// any later DSiRPC.
//
// Nothing on the SD card changes until every file has arrived whole: each
// is received into memory and checked (size, CRC32, the .nds header's own
// CRC), then written to its name + ".tmp" with the Wi-Fi idle and read back
// (written again if the SD card didn't keep it; the SD card and the Wi-Fi
// busy at once corrupted data on a 3DS). A file that fails on the way is
// asked for again, up to TRIES times. Then the
// swap: the old file becomes ".bak" and the .tmp takes its name, and if any
// of that fails, every file goes back as it was. The launcher's own file can
// be replaced while it runs: all of it is in memory (it has no NitroFS).
//
// update.idx (in the launcher's folder) keeps each file's CRC32 with its size
// and modified time, so the check only reads a file (nds-bootstrap is about
// 1.7 MB) when it changed.

#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "update.h"

#define PROTO_VERSION     1
#define OP_LIST           1
#define OP_GET            2
#define REQUEST_SIZE      20       // as long as the offline sync's request
#define ENTRY_SIZE        9
#define MAX_FILE          (8 * 1024 * 1024)
#define BUF_SIZE          (16 * 1024)
#define NDS_HEADER_SIZE   0x200
#define INDEX_MAGIC       "DSiRPC update 1"
#define TRIES             3        // tries of a file that fails on the way, and writes of one

static uint8_t buf[BUF_SIZE] __attribute__((aligned(32)));
static bool again;                 // the last failure is worth another try

// ---------------------------------------------------------------------------
// Little helpers

static uint16_t get16(const uint8_t *p)
{
    return p[0] | (p[1] << 8);
}

static uint32_t get32(const uint8_t *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put16(uint8_t *p, uint16_t v)
{
    p[0] = v;
    p[1] = v >> 8;
}

static void join_path(char *out, size_t outsz, const char *dir, const char *name)
{
    size_t n = strlen(dir);
    snprintf(out, outsz, (n > 0 && dir[n - 1] == '/') ? "%s%s" : "%s/%s", dir, name);
}

static bool file_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 && S_ISREG(st.st_mode);
}

const char *update_file_name(uint8_t id)
{
    return id == UPDATE_LAUNCHER ? "the launcher" : id == UPDATE_BOOTSTRAP ? "nds-bootstrap" : "a file";
}

// CRC32 (zlib's)
static uint32_t crc_table[256];

static uint32_t crc_update(uint32_t crc, const uint8_t *p, size_t n)
{
    if (crc_table[1] == 0)
    {
        for (uint32_t i = 0; i < 256; i++)
        {
            uint32_t c = i;
            for (int k = 0; k < 8; k++)
                c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            crc_table[i] = c;
        }
    }
    crc = ~crc;
    while (n--)
        crc = crc_table[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

static bool file_crc(const char *path, uint32_t *crc)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL)
        return false;
    uint32_t c = 0;
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0)
        c = crc_update(c, buf, n);
    bool ok = !ferror(f);
    fclose(f);
    *crc = c;
    return ok;
}

// ndstool always sets an .nds header's own CRC (CRC-16/MODBUS of its first
// 0x15E bytes, at 0x15E), so anything but an .nds fails this.
static bool nds_header_ok(const uint8_t *h, size_t n)
{
    if (n < NDS_HEADER_SIZE)
        return false;
    uint16_t crc = 0xFFFF;
    for (int i = 0; i < 0x15E; i++)
    {
        crc ^= h[i];
        for (int k = 0; k < 8; k++)
            crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
    }
    return crc == get16(h + 0x15E);
}

// ---------------------------------------------------------------------------
// update.idx: "<CRC32> <size> <modified time> <path>" per file

typedef struct
{
    char path[UPDATE_PATH_LEN];
    uint32_t size, crc;
    long long mtime;
} IndexEntry;

static IndexEntry index_buf[UPDATE_MAX_FILES];

static int load_index(const char *path, IndexEntry *out, int max)
{
    FILE *f = fopen(path, "r");
    if (f == NULL)
        return 0;
    char line[UPDATE_PATH_LEN + 48];
    int n = 0;
    if (fgets(line, sizeof(line), f) != NULL && strncmp(line, INDEX_MAGIC, strlen(INDEX_MAGIC)) == 0)
    {
        while (n < max && fgets(line, sizeof(line), f) != NULL)
        {
            line[strcspn(line, "\r\n")] = '\0';
            unsigned crc, size;
            long long mtime;
            int at = 0;
            if (sscanf(line, "%8x %u %lld %n", &crc, &size, &mtime, &at) != 3 || at == 0 || line[at] == '\0')
                continue;
            snprintf(out[n].path, sizeof(out[n].path), "%s", line + at);
            out[n].crc = crc;
            out[n].size = size;
            out[n].mtime = mtime;
            n++;
        }
    }
    fclose(f);
    return n;
}

static IndexEntry *find_entry(IndexEntry *index, int count, const char *path)
{
    for (int i = 0; i < count; i++)
    {
        if (strcmp(index[i].path, path) == 0)
            return &index[i];
    }
    return NULL;
}

// Notes a file's CRC32 with its size and time as they are now
static void note(IndexEntry *index, int *count, const char *path, uint32_t crc)
{
    struct stat st;
    if (stat(path, &st) != 0)
        return;
    IndexEntry *e = find_entry(index, *count, path);
    if (e == NULL)
    {
        if (*count >= UPDATE_MAX_FILES)
            return;
        e = &index[(*count)++];
        snprintf(e->path, sizeof(e->path), "%s", path);
    }
    e->size = (uint32_t)st.st_size;
    e->mtime = (long long)st.st_mtime;
    e->crc = crc;
}

// Writes the entries for the plan's files (the others are gone or old)
static void write_index(const UpdatePlan *plan, IndexEntry *index, int count)
{
    FILE *f = fopen(plan->index_path, "w");
    if (f == NULL)
        return;
    fprintf(f, "%s\n", INDEX_MAGIC);
    for (int i = 0; i < plan->count; i++)
    {
        const IndexEntry *e = find_entry(index, count, plan->files[i].path);
        if (e != NULL)
            fprintf(f, "%08X %u %lld %s\n", (unsigned)e->crc, (unsigned)e->size, e->mtime, e->path);
    }
    fclose(f);
}

// The file's CRC32: update.idx's while its size and time are the same as
// then, else read now (and noted).
static bool local_crc(IndexEntry *index, int *count, bool *changed, const char *path, const struct stat *st,
                      uint32_t *crc)
{
    IndexEntry *e = find_entry(index, *count, path);
    if (e != NULL && e->size == (uint32_t)st->st_size && e->mtime == (long long)st->st_mtime)
    {
        *crc = e->crc;
        return true;
    }
    if (!file_crc(path, crc))
        return false;
    note(index, count, path, *crc);
    *changed = true;
    return true;
}

// ---------------------------------------------------------------------------
// The exchange

static void request(uint8_t *p, const uint8_t mac[6], int model, uint8_t op, uint8_t file)
{
    memset(p, 0, REQUEST_SIZE);
    memcpy(p, "DRUP", 4);
    put16(p + 4, PROTO_VERSION);
    memcpy(p + 6, mac, 6);
    p[12] = (uint8_t)model;
    p[13] = op;
    p[14] = file;
}

int update_check(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                 const char *launcher_path, const char *bootstrap_path, const char *index_dir,
                 UpdatePlan *plan, char *msg, size_t msgsz)
{
    memset(plan, 0, sizeof(*plan));
    msg[0] = '\0';
    join_path(plan->index_path, sizeof(plan->index_path), index_dir, UPDATE_INDEX);

    uint8_t req[REQUEST_SIZE];
    request(req, mac, model, OP_LIST, 0);
    int sock;
    int r = sync_open(job, server, &sock, msg, msgsz);
    uint8_t head[7];
    if (r > 0)
        r = sync_send(job, sock, req, sizeof(req), msg, msgsz);
    if (r > 0)
        r = sync_recv(job, sock, head, sizeof(head), msg, msgsz);
    if (r <= 0 || memcmp(head, "DRUA", 4) != 0 || get16(head + 4) != 0)
    {
        // A DSiRPC from before updates answers with its offline sync's
        // refusal; one with console updates off says so
        sync_close(sock);
        return r < 0 ? r : 0;
    }

    int n = head[6];
    for (int i = 0; i < n; i++)
    {
        uint8_t e[ENTRY_SIZE];
        if ((r = sync_recv(job, sock, e, sizeof(e), msg, msgsz)) <= 0)
        {
            sync_close(sock);
            return r;
        }
        uint8_t id = e[0];
        uint32_t size = get32(e + 1);
        const char *local = id == UPDATE_LAUNCHER ? launcher_path : id == UPDATE_BOOTSTRAP ? bootstrap_path : NULL;
        bool listed = false;
        for (int k = 0; k < plan->count; k++)
            listed = listed || plan->files[k].id == id;
        // One this launcher doesn't know, or has nowhere to put
        if (local == NULL || local[0] == '\0' || size == 0 || size > MAX_FILE || listed ||
            plan->count >= UPDATE_MAX_FILES)
            continue;
        UpdateFile *f = &plan->files[plan->count++];
        f->id = id;
        f->size = size;
        f->crc = get32(e + 5);
        snprintf(f->path, sizeof(f->path), "%s", local);
    }
    uint8_t len = 0;
    char label[256];
    if ((r = sync_recv(job, sock, &len, 1, msg, msgsz)) > 0 && len > 0)
        r = sync_recv(job, sock, label, len, msg, msgsz);
    sync_close(sock);
    if (r <= 0)
        return r;
    for (int i = 0; i < len && i < UPDATE_LABEL_LEN - 1; i++)
        plan->label[i] = label[i] >= ' ' && label[i] <= '~' ? label[i] : '?';

    // What differs here: the size says so, else the CRC
    IndexEntry *index = index_buf;
    int count = load_index(plan->index_path, index, UPDATE_MAX_FILES);
    bool changed = false;
    for (int i = 0; i < plan->count; i++)
    {
        UpdateFile *f = &plan->files[i];
        struct stat st;
        uint32_t crc;
        if (stat(f->path, &st) != 0 || !S_ISREG(st.st_mode))
            f->needed = f->id != UPDATE_LAUNCHER;   // a missing nds-bootstrap goes there
        else if ((uint32_t)st.st_size != f->size)
            f->needed = true;
        else
            f->needed = !local_crc(index, &count, &changed, f->path, &st, &crc) || crc != f->crc;
        if (f->needed)
        {
            plan->needed++;
            plan->total += f->size;
        }
    }
    if (changed)
        write_index(plan, index, count);
    return plan->needed > 0 ? 1 : 0;
}

// Takes one file into its .tmp and checks it. 1: done, 0: cancelled,
// -1: failed (msg; the .tmp removed).
static int download_one(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                        UpdateFile *f, const UpdatePlan *plan, uint32_t *done, UpdateProgress progress,
                        char *msg, size_t msgsz)
{
    const char *what = update_file_name(f->id);
    char tmp[UPDATE_PATH_LEN + 8];
    snprintf(tmp, sizeof(tmp), "%s.tmp", f->path);

    uint8_t req[REQUEST_SIZE];
    request(req, mac, model, OP_GET, f->id);
    int sock;
    int r = sync_open(job, server, &sock, msg, msgsz);
    uint8_t head[14];
    if (r > 0)
        r = sync_send(job, sock, req, sizeof(req), msg, msgsz);
    if (r > 0)
        r = sync_recv(job, sock, head, sizeof(head), msg, msgsz);
    if (r <= 0)
    {
        sync_close(sock);
        again = r < 0;
        return r;
    }
    if (memcmp(head, "DRUF", 4) != 0 || get16(head + 4) != 0)
    {
        snprintf(msg, msgsz, "DSiRPC didn't send\n%s", what);
        sync_close(sock);
        return -1;
    }
    uint32_t size = get32(head + 6), want = get32(head + 10);
    if (size != f->size || want != f->crc)
    {
        snprintf(msg, msgsz, "DSiRPC's files changed while\nupdating. Start the launcher\nagain to try again.");
        sync_close(sock);
        return -1;
    }

    // Received whole into memory...
    uint8_t *data = memalign(32, size);
    if (data == NULL)
    {
        snprintf(msg, msgsz, "Not enough memory for\n%s", what);
        sync_close(sock);
        return -1;
    }
    uint32_t got = 0;
    while (got < size)
    {
        size_t n = size - got < BUF_SIZE ? size - got : BUF_SIZE;
        r = sync_recv(job, sock, data + got, n, msg, msgsz);
        if (r <= 0)
            break;
        got += n;
        *done += n;
        if (progress != NULL)
            progress(what, *done, plan->total);
    }
    sync_close(sock);
    if (r <= 0)
    {
        free(data);
        again = r < 0;
        return r;
    }
    if (crc_update(0, data, size) != want || !nds_header_ok(data, size))
    {
        free(data);
        again = true;
        snprintf(msg, msgsz, "%s arrived damaged", what);
        return -1;
    }

    // ...then written with the Wi-Fi idle, and read back: what the SD card kept
    bool written = false, kept = false;
    for (int i = 0; i < TRIES && !kept; i++)
    {
        FILE *out = fopen(tmp, "wb");
        written = out != NULL && fwrite(data, 1, size, out) == size;
        if (out != NULL && fclose(out) != 0)
            written = false;
        if (!written)
            break;
        uint32_t back;
        kept = file_crc(tmp, &back) && back == want;
    }
    free(data);
    if (!kept)
    {
        remove(tmp);
        snprintf(msg, msgsz, written ? "The SD card didn't keep\n%s whole" : "Can't write %s\n(is the SD card full?)",
                 what);
        return -1;
    }
    f->downloaded = true;
    return 1;
}

int update_download(const SyncJob *job, const uint8_t mac[6], int model, const struct sockaddr_in *server,
                    UpdatePlan *plan, UpdateProgress progress, char *msg, size_t msgsz)
{
    msg[0] = '\0';
    uint32_t done = 0;
    for (int i = 0; i < plan->count; i++)
    {
        UpdateFile *f = &plan->files[i];
        f->downloaded = false;
        if (!f->needed)
            continue;
        int r;
        uint32_t before = done;
        for (int attempt = 1; ; attempt++)
        {
            again = false;
            done = before;
            r = download_one(job, mac, model, server, f, plan, &done, progress, msg, msgsz);
            if (r >= 0 || !again || attempt >= TRIES)
                break;
        }
        if (r <= 0)
        {
            update_discard(plan);
            return r;
        }
    }
    return 1;
}

void update_discard(UpdatePlan *plan)
{
    for (int i = 0; i < plan->count; i++)
    {
        char tmp[UPDATE_PATH_LEN + 8];
        snprintf(tmp, sizeof(tmp), "%s.tmp", plan->files[i].path);
        remove(tmp);
        plan->files[i].downloaded = false;
    }
}

bool update_install(UpdatePlan *plan, char *msg, size_t msgsz)
{
    static char tmp[UPDATE_MAX_FILES][UPDATE_PATH_LEN + 8], bak[UPDATE_MAX_FILES][UPDATE_PATH_LEN + 8];
    bool had[UPDATE_MAX_FILES] = { false }, swapped[UPDATE_MAX_FILES] = { false };
    bool all_back = true;
    int failed = -1;
    msg[0] = '\0';

    for (int i = 0; i < plan->count; i++)
    {
        UpdateFile *f = &plan->files[i];
        if (!f->downloaded)
            continue;
        snprintf(tmp[i], sizeof(tmp[i]), "%s.tmp", f->path);
        snprintf(bak[i], sizeof(bak[i]), "%s.bak", f->path);
        remove(bak[i]);
        had[i] = file_exists(f->path);
        if (had[i] && rename(f->path, bak[i]) != 0)
        {
            failed = i;
            break;
        }
        if (rename(tmp[i], f->path) != 0)
        {
            if (had[i] && rename(bak[i], f->path) != 0)
                all_back = false;
            failed = i;
            break;
        }
        swapped[i] = true;
    }

    if (failed >= 0)
    {
        // Every file back as it was
        for (int i = plan->count - 1; i >= 0; i--)
        {
            if (!swapped[i])
                continue;
            remove(plan->files[i].path);
            if (had[i] && rename(bak[i], plan->files[i].path) != 0)
                all_back = false;
        }
        update_discard(plan);
        snprintf(msg, msgsz, all_back ? "Can't replace %s\n(is the SD card locked?).\nThe old files are back."
                                      : "Can't replace %s.\nThe old files are in the\nlauncher's folder, as .bak.",
                 update_file_name(plan->files[failed].id));
        return false;
    }

    IndexEntry *index = index_buf;
    int count = load_index(plan->index_path, index, UPDATE_MAX_FILES);
    for (int i = 0; i < plan->count; i++)
    {
        if (!swapped[i])
            continue;
        if (had[i])
            remove(bak[i]);
        plan->files[i].downloaded = false;
        note(index, &count, plan->files[i].path, plan->files[i].crc);
    }
    write_index(plan, index, count);
    return true;
}

// ---------------------------------------------------------------------------
// The screens

#ifdef __NDS__
#include <nds.h>
#include <dswifi9.h>

#include "topscreen.h"
#include "ui.h"

static bool b_pressed(void)
{
    scanKeys();
    return ((keysDown() | ui_footer_key()) & KEY_B) != 0;
}

static void release_keys(void)
{
    do
    {
        sync_frame();
        scanKeys();
    } while (keysHeld() & (KEY_A | KEY_B | KEY_START));
}

static u32 wait_keys(u32 keys)
{
    while (1)
    {
        sync_frame();
        scanKeys();
        u32 down = (keysDown() | ui_footer_key()) & keys;
        if (down)
            return down;
    }
}

// The modern look's card, under the connecting screen's steps: a title, a
// line, and more lines (dimmer, split at '\n')
static void card(const char *title, uint8_t accent, const char *line, const char *more, const UiKey *keys, int n)
{
    Canvas *c = ui_screen();
    ui_fill(c, 0, 96, UI_W, UI_FOOT_Y - 96, UI_BG);
    ui_panel(8, 98, UI_W - 16, 70, accent);
    ui_text(c, 16, 106, title, accent);
    if (line != NULL)
        ui_text_fit(c, 16, 120, line, UI_W - 32, UI_SOFT);
    if (more != NULL)
        ui_text_wrap(c, 16, 132, more, UI_W - 32, 3, UI_DIM);
    ui_footer(keys, n);
    ui_present();
}

// "The launcher and nds-bootstrap"
static void needed_names(const UpdatePlan *plan, char *out, size_t outsz)
{
    out[0] = '\0';
    int done = 0;
    for (int i = 0; i < plan->count; i++)
    {
        if (!plan->files[i].needed)
            continue;
        size_t n = strlen(out);
        const char *name = update_file_name(plan->files[i].id);
        snprintf(out + n, outsz - n, "%s%s", done ? " and " : "", name);
        done++;
    }
    if (out[0] >= 'a' && out[0] <= 'z')
        out[0] = (char)(out[0] - 'a' + 'A');
}

static void title(const char *text)
{
    consoleClear();
    printf("%s\n-------------------------------\n", text);
}

static void progress(const char *what, uint32_t done, uint32_t total)
{
    static int last_pct = -1;
    int pct = total ? (int)((uint64_t)done * 100 / total) : 0;
    if (pct == last_pct && done != 0)
        return;
    last_pct = pct;
    if (ui_on())
    {
        Canvas *c = ui_screen();
        char line[48], num[8];
        ui_fill(c, 12, 118, UI_W - 24, 30, UI_PANEL);
        snprintf(line, sizeof(line), "Downloading %s", what);
        snprintf(num, sizeof(num), "%d%%", pct);
        ui_text_fit(c, 16, 120, line, UI_W - 32 - 30, UI_SOFT);
        ui_text_right(c, UI_W - 16, 120, num, UI_TEXT);
        ui_bar(c, 16, 134, UI_W - 32, 10, pct, UI_CYAN);
        ui_present();
        return;
    }
    char bar[25];
    int fill = pct * 24 / 100;
    for (int i = 0; i < 24; i++)
        bar[i] = i < fill ? '#' : '-';
    bar[24] = '\0';
    printf("\x1b[3;0HDownloading %-19.19s\n", what);
    printf("\x1b[4;0H[%s] %3d%%\n", bar, pct);
}

static void list_files(const UpdatePlan *plan, bool sizes)
{
    for (int i = 0; i < plan->count; i++)
    {
        const UpdateFile *f = &plan->files[i];
        if (!f->needed)
            continue;
        if (sizes)
            printf("  %-18s %5u KB\n", update_file_name(f->id), (unsigned)((f->size + 1023) / 1024));
        else
            printf("  %s\n", update_file_name(f->id));
    }
}

UpdateOutcome update_offer(const UpdateUi *ui)
{
    static UpdatePlan plan;
    char msg[160];
    SyncJob job = {
        .console_model = ui->console_model,
        .cancelled = b_pressed,
    };
    struct sockaddr_in server;
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_port = htons(ui->server_port);
    server.sin_addr.s_addr = ui->server_addr;

    if (update_check(&job, ui->mac, ui->console_model, &server, ui->launcher_path, ui->bootstrap_path,
                     ui->index_dir, &plan, msg, sizeof(msg)) != 1)
        return UPDATE_NONE;

    if (ui_on())
    {
        static const UiKey keys[] = { { "A", "Update", KEY_A }, { "B", "Later", KEY_B } };
        char names[64], more[160];
        needed_names(&plan, names, sizeof(names));
        snprintf(more, sizeof(more), "%s%s%sEach file is checked before it replaces the old one.",
                 plan.label[0] != '\0' ? "From DSiRPC " : "", plan.label, plan.label[0] != '\0' ? ". " : "");
        ui_sound(SND_TOGGLE);
        card("Update available", UI_CYAN, names, more, keys, 2);
    }
    else
    {
        title("Update available");
        printf("DSiRPC on the PC has other\nversions of:\n\n");
        list_files(&plan, true);
        if (plan.label[0] != '\0')
            printf("\nFrom DSiRPC %.18s.\n", plan.label);
        printf("\nEach file is downloaded and\nchecked before it replaces the\nold one. Keep the console on\n"
               "until it's done.\n");
        printf("\x1b[23;0HA: update   B: not now");
    }
    release_keys();
    if (wait_keys(KEY_A | KEY_B) & KEY_B)
    {
        ui_sound(SND_BACK);
        return UPDATE_SHOWN;
    }
    ui_sound(SND_SELECT);

    if (ui_on())
    {
        static const UiKey keys[] = { { "B", "Cancel", KEY_B } };
        card("Updating", UI_CYAN, NULL, NULL, keys, 1);
    }
    else
    {
        title("Updating");
        printf("\x1b[6;0HB: cancel\n");
    }
    int r = update_download(&job, ui->mac, ui->console_model, &server, &plan, progress, msg, sizeof(msg));
    if (r <= 0)
    {
        if (ui_on())
        {
            static const UiKey keys[] = { { "A", "Back", KEY_A } };
            char more[200];
            snprintf(more, sizeof(more), "%s\nNothing on the SD card changed.", r == 0 ? "Cancelled." : msg);
            ui_sound(SND_ERROR);
            card("The update didn't finish", UI_RED, NULL, more, keys, 1);
        }
        else
        {
            title("The update didn't finish");
            printf("%s\n\nNothing on the SD card changed.\n", r == 0 ? "Cancelled." : msg);
            printf("\x1b[23;0HA: go back");
        }
        release_keys();
        wait_keys(KEY_A | KEY_B);
        return UPDATE_SHOWN;
    }

    // Everything's here and checked: the Wi-Fi goes off (DSiRPC is told the
    // launcher's leaving), and with no file open, the files are swapped in
    if (ui_on())
    {
        card("Updating", UI_CYAN, "Swapping the files in...", NULL, NULL, 0);
    }
    else
    {
        title("Updating");
        printf("Swapping the files in...\n");
    }
    sync_bye();
    Wifi_DisconnectAP();
    Wifi_DisableWifi();
    top_set(TOP_OFFLINE);
    for (int i = 0; i < 30; i++)
        cothread_yield_irq(IRQ_VBLANK);

    bool installed = update_install(&plan, msg, sizeof(msg));
    if (ui_on())
    {
        static const UiKey keys[] = { { "START", "Exit", KEY_START } };
        char names[64];
        needed_names(&plan, names, sizeof(names));
        ui_sound(installed ? SND_DONE : SND_ERROR);
        if (installed)
            card("Update complete", UI_GREEN, names,
                 "The Wi-Fi is off now. Press START to exit, then open the launcher again.", keys, 1);
        else
            card("The update didn't finish", UI_RED, NULL, msg, keys, 1);
    }
    else if (installed)
    {
        title("Update complete");
        printf("Updated from DSiRPC%s%.30s:\n", plan.label[0] != '\0' ? "\n" : "", plan.label);
        list_files(&plan, false);
        printf("\nThe Wi-Fi is off now. Press\nSTART to exit, then open the\nlauncher again.\n");
    }
    else
    {
        title("The update didn't finish");
        printf("%s\n", msg);
    }
    if (!ui_on())
        printf("\x1b[23;0HSTART: exit");
    release_keys();
    wait_keys(KEY_START);
    return UPDATE_EXIT;
}
#endif
