// saveui.c's screens: the list, a conflict, the versions, progress, the summary

#include <stdlib.h>

#include "saveui.c"

#include "ui_host.h"

static void fill_list(void)
{
    static const char *const names[] = { "Pokemon Black", "Mario Kart DS", "Pokemon Platinum", "Tetris DS",
                                         "Animal Crossing WW" };
    static const SaveAction actions[] = { SA_CONFLICT, SA_UPLOAD, SA_DOWNLOAD, SA_UPLOAD, SA_IN_SYNC };
    console.model = 2;
    console.backup_only = false;
    list.count = 5;
    list.items = calloc(5, sizeof(SaveItem));
    for (int i = 0; i < 5; i++)
    {
        SaveItem *it = &list.items[i];
        snprintf(it->name, sizeof(it->name), "%s", names[i]);
        it->action = actions[i];
        it->present = true;
        it->size = i == 1 ? 512 : 524288;
        it->mtime = 946684800 + 815443200;
        it->pc_time = 815400000;
        it->pc_size = 524288;
        it->base = 1;
        it->versions = 4;
        snprintf(it->pc_source, sizeof(it->pc_source), "DSi 3F21");
    }
    build_shown();
}

static void empty_list(void)
{
    free(shown);
    shown = NULL;
    free(list.items);
    list.items = NULL;
    list.count = 0;
}

void host_save_screens(void)
{
    fill_list();
    draw_list_modern(1, 0);
    host_shot("saves");
    ask_conflict(&list.items[0]);       // (B: decide later)
    host_shot("saves_conflict");

    SaveVersion v[3] = {
        { 0, 815400000, 524288, 1, "DSi 3F21" },
        { 1, 815300000, 524288, 2, "3DS CC5D" },
        { 2, 815000000, 524288, 3, "External" },
    };
    draw_versions_modern(&list.items[0], v, 3, 1, 0);
    host_shot("saves_versions");
    begin("Syncing saves (2 of 4)");
    progress("Downloading Pokemon Black\nfrom: DSi 3F21", 300, 1000);
    host_shot("saves_progress");
    message_tone("Saves synced", "3 uploaded\n1 downloaded\n\nEverything else is in sync.",
                 UI_GREEN);
    host_shot("saves_done");
    empty_list();
}

// The demo's (ui_host.c): the list with a row picked, a sync pct% done, and
// its summary
void host_demo_saves(int row)
{
    fill_list();
    draw_list_modern(row, 0);
    empty_list();
}

void host_demo_saves_progress(int pct)
{
    begin("Syncing saves (2 of 4)");
    progress("Downloading Pokemon Black\nfrom: DSi 3F21", (uint32_t)pct * 10, 1000);
}

void host_demo_saves_done(void)
{
    message_tone("Saves synced", "3 uploaded\n1 downloaded\n\nEverything else is in sync.",
                 UI_GREEN);
}

// A sync's bar across its saves (saveui.c's batch): each step's done of
// total as the batch's, printed in turn ("batch 0,256,...")
void host_save_batch(void)
{
    static const struct { const char *what; uint32_t done, total; } steps[] = {
        { "Uploading Pokemon Black", 0, 512 }, { "Uploading Pokemon Black", 256, 512 },
        { "Uploading Pokemon Black", 512, 512 },
        { "Backing up Platinum first", 0, 256 }, { "Backing up Platinum first", 256, 256 },
        { "Downloading Platinum", 0, 1024 }, { "Downloading Platinum", 512, 1024 },
        { "Trying again (2 of 3)", 0, 1 },                  // (a retry's wait)
        { "Downloading Platinum", 0, 1024 }, { "Downloading Platinum", 512, 1024 },
        { "Downloading Platinum", 1024, 1024 },
    };
    memset(&batch, 0, sizeof(batch));
    batch.on = true;
    batch.total = 512 + 256 + 1024;
    printf("batch ");
    for (size_t i = 0; i < sizeof(steps) / sizeof(steps[0]); i++)
    {
        uint32_t of;
        uint32_t done = batch_done(steps[i].what, steps[i].done, steps[i].total, &of);
        printf("%s%u", i ? "," : "", (unsigned)done);
        if (of != batch.total)
            printf("!");
    }
    printf("\n");
    batch.on = false;
}
