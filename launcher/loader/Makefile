# SPDX-License-Identifier: CC0-1.0
#
# Builds the two pieces the launcher installs to start nds-bootstrap with
# (see ../CHAINLOAD.md), with BlocksDS's toolchain:
#
#   build/load.bin      devkitPro's nds-bootloader (GPLv2+, source/): ARM7
#                       code that runs from VRAM C, reads an .nds off the SD
#                       card and boots it with argv
#   build/bootstub.bin  NDS Homebrew Menu's bootstub (GPLv2+, bootstub.s):
#                       what exit() jumps to; it hands the ARM7 the loader
#
# The launcher's Makefile runs this first.

BLOCKSDS		?= /opt/blocksds/core
WONDERFUL_TOOLCHAIN	?= /opt/wonderful
PREFIX			:= $(WONDERFUL_TOOLCHAIN)/toolchain/gcc-arm-none-eabi/bin/arm-none-eabi-
CC			:= $(PREFIX)gcc
OBJCOPY			:= $(PREFIX)objcopy

BUILD			:= build
ARCH			:= -mthumb -mthumb-interwork -march=armv4t -mtune=arm7tdmi
INCLUDE			:= -I$(BUILD) -Isource -I$(BLOCKSDS)/libs/libnds/include
CFLAGS			:= -Wall -Os -ffunction-sections -fdata-sections $(ARCH) $(INCLUDE) -DARM7
ASFLAGS			:= -x assembler-with-cpp $(ARCH) $(INCLUDE)
LDFLAGS			:= -nostartfiles -nostdlib -T load.ld -Wl,--no-warn-rwx-segments,--gc-sections \
			   -Wl,-Map,$(BUILD)/load.map $(ARCH)

SOURCES_C		:= $(filter-out %.arm.c,$(wildcard source/*.c))
SOURCES_ARM		:= $(wildcard source/*.arm.c)
SOURCES_S		:= $(wildcard source/*.s)
OBJS			:= $(patsubst source/%.c,$(BUILD)/%.o,$(SOURCES_C)) \
			   $(patsubst source/%.arm.c,$(BUILD)/%.arm.o,$(SOURCES_ARM)) \
			   $(patsubst source/%.s,$(BUILD)/%.o,$(SOURCES_S))

.PHONY: all clean

all: $(BUILD)/load.bin $(BUILD)/bootstub.bin

$(BUILD)/load.bin: $(BUILD)/load.elf
	@echo "  OBJCOPY $@"
	@$(OBJCOPY) -O binary $< $@

$(BUILD)/load.elf: $(OBJS) load.ld
	@echo "  LD      $@"
	@$(CC) $(LDFLAGS) $(OBJS) -lgcc -o $@

$(BUILD)/%.o: source/%.c | $(BUILD)
	@echo "  CC      $<"
	@$(CC) $(CFLAGS) -MMD -MP -c $< -o $@

$(BUILD)/%.arm.o: source/%.arm.c | $(BUILD)
	@echo "  CC      $<"
	@$(CC) $(CFLAGS) -marm -MMD -MP -c $< -o $@

$(BUILD)/%.o: source/%.s | $(BUILD)
	@echo "  AS      $<"
	@$(CC) $(ASFLAGS) -MMD -MP -c $< -o $@

# The ARM9 MPU setup the loader copies to main RAM for the ARM9 to run
$(BUILD)/arm9mpu_reset.o: $(BUILD)/mpu_reset.bin

$(BUILD)/mpu_reset.bin: arm9code/mpu_reset.s | $(BUILD)
	@echo "  AS      $<"
	@$(CC) -x assembler-with-cpp $(INCLUDE) -DARM9 -Wl,-Ttext=0 -nostartfiles -nostdlib $< -o $(BUILD)/mpu_reset.elf
	@$(OBJCOPY) -O binary $(BUILD)/mpu_reset.elf $@

$(BUILD)/bootstub.bin: bootstub.s | $(BUILD)
	@echo "  AS      $<"
	@$(CC) -x assembler-with-cpp -Wl,-Ttext=0 -nostartfiles -nostdlib $< -o $(BUILD)/bootstub.elf
	@$(OBJCOPY) -O binary $(BUILD)/bootstub.elf $@

$(BUILD):
	@mkdir -p $@

clean:
	@echo "  CLEAN   loader"
	@rm -rf $(BUILD)

-include $(wildcard $(BUILD)/*.d)
