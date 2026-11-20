#ifndef DSIRPC_STATE_MENU_H
#define DSIRPC_STATE_MENU_H

// DSiRPC: what the in-game menu calls for save states (dsirpc_state.c).
// State_Save() and State_Load() run after the menu has put the game's
// screens back (inGameMenu()'s runStateOp()).

#include <nds/ndstypes.h>
#include "dsirpc_state.h"

void State_Init(s32 *mainScreen, u32 readBusy); // each time the menu opens
int State_Slots(void);                         // 0: no save states for this game
int State_Busy(void);                          // a ROM read was part way through when the menu opened
s32 State_List(void);                          // every slot's summary (State_Info())
const DssSlotInfo *State_Info(int slot);
s32 State_Usable(int slot);                    // DSS_OK: this game's, from this build
s32 State_Check(int slot);                     // the whole header, against this game and setup
s32 State_Save(int slot);                      // DSS_OK; DSS_RESUMED when a load comes back here
s32 State_Load(int slot);                      // returns only if it failed

#endif // DSIRPC_STATE_MENU_H
