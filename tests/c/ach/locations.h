// Stands in for nds-bootstrap's locations.h in the offline checker test: the
// checker's memory is a buffer of ach_host.c's.
#pragma once
#include <stdint.h>
extern uint8_t hostAch[0x40000];
#define DSIRPC_ACH_LOCATION ((uintptr_t)hostAch)
#define DSIRPC_ACH_SIZE 0x40000
#define DSIRPC_WATCH_RING_SIZE 0x800
#define DSIRPC_WATCH_RING_LOCATION (DSIRPC_ACH_LOCATION + DSIRPC_ACH_SIZE - DSIRPC_WATCH_RING_SIZE)
