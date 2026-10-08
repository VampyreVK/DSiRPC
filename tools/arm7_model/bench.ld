/* bench.ld - everything in ARM7 WRAM, where nds-bootstrap's cardengine
   (and so the achievement checker's code) runs: CARDENGINEI_ARM7_LOCATION */
MEMORY { wram : ORIGIN = 0x037E0400, LENGTH = 0x1F000 }
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > wram
  .data : { *(.data*) } > wram
  .bss : { *(.bss*) *(COMMON) } > wram
}
