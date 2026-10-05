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

# The loader the launcher starts nds-bootstrap with (loader/, see
# CHAINLOAD.md). It's built first and embedded by source/loader_blobs.s.

LOADER_BINS	:= loader/build/load.bin loader/build/bootstub.bin

$(BUILDDIR)/source/loader_blobs.s.o: $(LOADER_BINS)

loader/build/load.bin: $(wildcard loader/source/*) loader/arm9code/mpu_reset.s \
		       loader/bootstub.s loader/load.ld loader/Makefile
	@$(MAKE) --no-print-directory -C loader

loader/build/bootstub.bin: loader/build/load.bin

.PHONY: clean-loader
clean: clean-loader
clean-loader:
	@$(MAKE) --no-print-directory -C loader clean
