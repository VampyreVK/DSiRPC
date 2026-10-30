# SPDX-License-Identifier: CC0-1.0
#
# The launcher's ARM7 core (see source/main.c): BlocksDS's default one with
# DSWiFi and maxmod, built here for its Wifi_Update() guard. The launcher's
# Makefile builds it first.

BLOCKSDS	?= /opt/blocksds/core

SOURCEDIRS	:= source
# arm7watch.h, shared with the ARM9
INCLUDEDIRS	:= ../source
DEFINES		:= -DUSE_DSWIFI=1 -DUSE_MAXMOD=1 -DPICOLIBC_LONG_LONG_PRINTF_SCANF
LIBS		:= -lmm7 -ldswifi7 -lnds7
LIBDIRS		:= $(BLOCKSDS)/libs/maxmod \
		   $(BLOCKSDS)/libs/dswifi
LDFLAGS		:= -Wl,--wrap=Wifi_Update,--wrap=irqSet,--wrap=irqSetAUX

include $(BLOCKSDS)/sys/default_makefiles/rom_arm9arm7/Makefile.arm7
