// update.c's screens: the update's card under the connecting screen

#include "update.c"

#include "ui_host.h"

void host_update_screens(void)
{
    static UpdatePlan plan;
    plan.count = 2;
    plan.files[0] = (UpdateFile){ .id = UPDATE_LAUNCHER, .needed = true, .size = 400000 };
    plan.files[1] = (UpdateFile){ .id = UPDATE_BOOTSTRAP, .needed = true, .size = 1700000 };
    snprintf(plan.label, sizeof(plan.label), "v0.9.0");
    char names[64], more[160];
    needed_names(&plan, names, sizeof(names));
    snprintf(more, sizeof(more), "From DSiRPC %s. Each file is checked before it replaces the old one.", plan.label);

    host_connected();
    static const UiKey offer[] = { { "A", "Update", KEY_A }, { "B", "Later", KEY_B } };
    card("Update available", UI_CYAN, names, more, offer, 2);
    host_shot("update");

    static const UiKey cancel[] = { { "B", "Cancel", KEY_B } };
    card("Updating", UI_CYAN, NULL, NULL, cancel, 1);
    progress("the launcher", 45, 100);
    host_shot("update_progress");

    static const UiKey done[] = { { "START", "Exit", KEY_START } };
    card("Update complete", UI_GREEN, names, "The Wi-Fi is off now. Press START to exit, then open the launcher again.",
         done, 1);
    host_shot("update_done");
}
