// SPDX-License-Identifier: MIT
//
// The bootstub and loader built in loader/ (see source/chainload.c). The
// Makefile builds them before this file.

    .section .rodata.loader_blobs, "a"

    .balign 4
    .global bootstub_bin
bootstub_bin:
    .incbin "loader/build/bootstub.bin"
bootstub_bin_end:

    .balign 4
    .global load_bin
load_bin:
    .incbin "loader/build/load.bin"
load_bin_end:

    .balign 4
    .global bootstub_bin_size
bootstub_bin_size:
    .word bootstub_bin_end - bootstub_bin

    .global load_bin_size
load_bin_size:
    .word load_bin_end - load_bin
