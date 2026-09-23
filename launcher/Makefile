# SPDX-License-Identifier: CC0-1.0
#
# Based on BlocksDS's examples/dswifi/connection_info Makefile.

BLOCKSDS	?= /opt/blocksds/core

# User config

NAME		:= dsirpc-launcher
GAME_TITLE	:= DSiRPC Launcher
GAME_SUBTITLE	:= DSWiFi DSi mode

# Libraries
# ---------

ARM7ELF		:= $(BLOCKSDS)/sys/arm7/main_core/arm7_dswifi_maxmod.elf

LIBS		:= -ldswifi9 -lnds9
LIBDIRS		:= $(BLOCKSDS)/libs/dswifi \
			   $(BLOCKSDS)/libs/libnds

include $(BLOCKSDS)/sys/default_makefiles/rom_arm9/Makefile
