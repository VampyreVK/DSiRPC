// rpcprobe_build.h - build-wide switches for rpcprobe. Every rpcprobe .c
// file that has a switch includes this, so it means the same thing everywhere.

#ifndef RPCPROBE_BUILD_H
#define RPCPROBE_BUILD_H

// 1 = answer memory read requests from the PC (probe_req.c).
// 0 = send hello packets only (handy for ruling the receive path out when
//     something goes wrong).
#define RPCPROBE_REQUESTS 1

#endif // RPCPROBE_BUILD_H
