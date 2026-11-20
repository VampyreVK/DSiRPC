@ DSiRPC: save states' CPU and cache helpers (dsirpc_state.h). ARMv4T
@ instructions only (no blx, no clz), so both CPUs run the context ones:
@ the ARM7 half (dsirpc_state7.c) calls them from the same window. The
@ cache and CP15 ones are the ARM9's alone.

#ifndef B4DS

	.arm
	.align	4
	.global	dss_setjmp
	.type	dss_setjmp, %function
	.global	dss_longjmp
	.type	dss_longjmp, %function
	.global	dss_call_on_stack
	.type	dss_call_on_stack, %function
	.global	dss_swap_svc_sp
	.type	dss_swap_svc_sp, %function
	.global	dss_copy32
	.type	dss_copy32, %function
	.global	dss_dc_flush_all
	.type	dss_dc_flush_all, %function
	.global	dss_ic_invalidate_all
	.type	dss_ic_invalidate_all, %function
	.global	dss_cp15_read
	.type	dss_cp15_read, %function
	.global	dss_cp15_write_mpu
	.type	dss_cp15_write_mpu, %function

#define MODE_FIQ 0x11
#define MODE_IRQ 0x12
#define MODE_SVC 0x13
#define MODE_ABT 0x17
#define MODE_UND 0x1B
#define MODE_SYS 0x1F

@ The context (DSS_CTX_WORDS words):
@  0-9 r4-r11, sp, lr   10 cpsr   11-12 SYS sp, lr
@  13-20 FIQ r8-r12, sp, lr, spsr   21-23 IRQ sp, lr, spsr
@  24-26 SVC sp, lr, spsr   27-29 ABT   30-32 UND

@---------------------------------------------------------------------------------
@ int dss_setjmp(u32 *ctx): 0 now, 1 when dss_longjmp() comes back here.
@ Every mode's banked registers too, so a load gets back the stacks of the
@ modes the game wasn't in. Needs a privileged mode (the menu runs in one).
dss_setjmp:
@---------------------------------------------------------------------------------
	stmia	r0, {r4-r11, sp, lr}
	mrs	r1, cpsr
	str	r1, [r0, #40]
	orr	r2, r1, #0xC0
	bic	r2, r2, #0x1F

	orr	r3, r2, #MODE_SYS
	msr	cpsr_c, r3
	str	sp, [r0, #44]
	str	lr, [r0, #48]

	orr	r3, r2, #MODE_FIQ
	msr	cpsr_c, r3
	add	r3, r0, #52
	stmia	r3, {r8-r12, sp, lr}
	mrs	r3, spsr
	str	r3, [r0, #80]

	orr	r3, r2, #MODE_IRQ
	msr	cpsr_c, r3
	str	sp, [r0, #84]
	str	lr, [r0, #88]
	mrs	r3, spsr
	str	r3, [r0, #92]

	orr	r3, r2, #MODE_SVC
	msr	cpsr_c, r3
	str	sp, [r0, #96]
	str	lr, [r0, #100]
	mrs	r3, spsr
	str	r3, [r0, #104]

	orr	r3, r2, #MODE_ABT
	msr	cpsr_c, r3
	str	sp, [r0, #108]
	str	lr, [r0, #112]
	mrs	r3, spsr
	str	r3, [r0, #116]

	orr	r3, r2, #MODE_UND
	msr	cpsr_c, r3
	str	sp, [r0, #120]
	str	lr, [r0, #124]
	mrs	r3, spsr
	str	r3, [r0, #128]

	msr	cpsr_c, r1
	mov	r0, #0
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_longjmp(const u32 *ctx): back into the dss_setjmp() that took ctx,
@ which returns 1. Its stacks have to be back in memory first.
dss_longjmp:
@---------------------------------------------------------------------------------
	mrs	r1, cpsr
	orr	r2, r1, #0xC0
	bic	r2, r2, #0x1F

	orr	r3, r2, #MODE_SYS
	msr	cpsr_c, r3
	ldr	sp, [r0, #44]
	ldr	lr, [r0, #48]

	orr	r3, r2, #MODE_FIQ
	msr	cpsr_c, r3
	add	r3, r0, #52
	ldmia	r3, {r8-r12, sp, lr}
	ldr	r3, [r0, #80]
	msr	spsr_cxsf, r3

	orr	r3, r2, #MODE_IRQ
	msr	cpsr_c, r3
	ldr	sp, [r0, #84]
	ldr	lr, [r0, #88]
	ldr	r3, [r0, #92]
	msr	spsr_cxsf, r3

	orr	r3, r2, #MODE_SVC
	msr	cpsr_c, r3
	ldr	sp, [r0, #96]
	ldr	lr, [r0, #100]
	ldr	r3, [r0, #104]
	msr	spsr_cxsf, r3

	orr	r3, r2, #MODE_ABT
	msr	cpsr_c, r3
	ldr	sp, [r0, #108]
	ldr	lr, [r0, #112]
	ldr	r3, [r0, #116]
	msr	spsr_cxsf, r3

	orr	r3, r2, #MODE_UND
	msr	cpsr_c, r3
	ldr	sp, [r0, #120]
	ldr	lr, [r0, #124]
	ldr	r3, [r0, #128]
	msr	spsr_cxsf, r3

	@ the saved mode, with IRQs and FIQs off until its own bits are back
	ldr	r1, [r0, #40]
	orr	r2, r1, #0xC0
	msr	cpsr_c, r2
	ldmia	r0, {r4-r11, sp, lr}
	msr	cpsr_c, r1
	mov	r0, #1
	bx	lr

@---------------------------------------------------------------------------------
@ u32 dss_call_on_stack(u32 (*fn)(u32), u32 arg, void *stackTop): fn(arg) on
@ another stack (the current mode's sp), back on this one after
dss_call_on_stack:
@---------------------------------------------------------------------------------
	stmfd	sp!, {r4, lr}
	mov	r4, sp
	mov	sp, r2
	mov	r3, r0
	mov	r0, r1
	mov	lr, pc
	bx	r3
	mov	sp, r4
	ldmfd	sp!, {r4, lr}
	bx	lr

@---------------------------------------------------------------------------------
@ void *dss_swap_svc_sp(void *sp): SVC mode's sp to sp; returns the old one
@ (the BIOS calls push on it). Nothing in SVC mode itself (returns 0).
dss_swap_svc_sp:
@---------------------------------------------------------------------------------
	mrs	r1, cpsr
	and	r3, r1, #0x1F
	cmp	r3, #MODE_SVC
	moveq	r0, #0
	bxeq	lr
	orr	r2, r1, #0xC0
	bic	r2, r2, #0x1F
	orr	r2, r2, #MODE_SVC
	msr	cpsr_c, r2
	mov	r3, sp
	mov	sp, r0
	msr	cpsr_c, r1
	mov	r0, r3
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_copy32(u32 *dst, const u32 *src, u32 bytes): words, any address
@ (address 0 is the ARM9's ITCM), bytes a multiple of 32
dss_copy32:
@---------------------------------------------------------------------------------
	cmp	r2, #0
	bxeq	lr
	stmfd	sp!, {r4-r10}
1:
	ldmia	r1!, {r3-r10}
	stmia	r0!, {r3-r10}
	subs	r2, r2, #32
	bgt	1b
	ldmfd	sp!, {r4-r10}
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_dc_flush_all(void): ARM9: clean and invalidate the whole data
@ cache (4 KB, 4 ways of 32-byte lines), then drain the write buffer
dss_dc_flush_all:
@---------------------------------------------------------------------------------
	mov	r1, #0
2:
	mov	r0, #0
3:
	orr	r2, r1, r0
	mcr	p15, 0, r2, c7, c14, 2
	add	r0, r0, #32
	cmp	r0, #(0x1000 / 4)
	bne	3b
	adds	r1, r1, #0x40000000
	bne	2b
	mov	r0, #0
	mcr	p15, 0, r0, c7, c10, 4
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_ic_invalidate_all(void): ARM9
dss_ic_invalidate_all:
@---------------------------------------------------------------------------------
	mov	r0, #0
	mcr	p15, 0, r0, c7, c5, 0
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_cp15_read(u32 out[16]): ARM9: c1; c2 data, instruction; c3;
@ c5 data, instruction (extended); c6 regions 0-7; c9 DTCM, ITCM
dss_cp15_read:
@---------------------------------------------------------------------------------
	mrc	p15, 0, r1, c1, c0, 0
	str	r1, [r0, #0]
	mrc	p15, 0, r1, c2, c0, 0
	str	r1, [r0, #4]
	mrc	p15, 0, r1, c2, c0, 1
	str	r1, [r0, #8]
	mrc	p15, 0, r1, c3, c0, 0
	str	r1, [r0, #12]
	mrc	p15, 0, r1, c5, c0, 2
	str	r1, [r0, #16]
	mrc	p15, 0, r1, c5, c0, 3
	str	r1, [r0, #20]
	mrc	p15, 0, r1, c6, c0, 0
	str	r1, [r0, #24]
	mrc	p15, 0, r1, c6, c1, 0
	str	r1, [r0, #28]
	mrc	p15, 0, r1, c6, c2, 0
	str	r1, [r0, #32]
	mrc	p15, 0, r1, c6, c3, 0
	str	r1, [r0, #36]
	mrc	p15, 0, r1, c6, c4, 0
	str	r1, [r0, #40]
	mrc	p15, 0, r1, c6, c5, 0
	str	r1, [r0, #44]
	mrc	p15, 0, r1, c6, c6, 0
	str	r1, [r0, #48]
	mrc	p15, 0, r1, c6, c7, 0
	str	r1, [r0, #52]
	mrc	p15, 0, r1, c9, c1, 0
	str	r1, [r0, #56]
	mrc	p15, 0, r1, c9, c1, 1
	str	r1, [r0, #60]
	bx	lr

@---------------------------------------------------------------------------------
@ void dss_cp15_write_mpu(const u32 in[16]): ARM9: dss_cp15_read()'s c2, c3,
@ c5 and c6 back (not c1 or the TCMs: the load checks those are the same).
@ The caches have to be clean first.
dss_cp15_write_mpu:
@---------------------------------------------------------------------------------
	ldr	r1, [r0, #24]
	mcr	p15, 0, r1, c6, c0, 0
	ldr	r1, [r0, #28]
	mcr	p15, 0, r1, c6, c1, 0
	ldr	r1, [r0, #32]
	mcr	p15, 0, r1, c6, c2, 0
	ldr	r1, [r0, #36]
	mcr	p15, 0, r1, c6, c3, 0
	ldr	r1, [r0, #40]
	mcr	p15, 0, r1, c6, c4, 0
	ldr	r1, [r0, #44]
	mcr	p15, 0, r1, c6, c5, 0
	ldr	r1, [r0, #48]
	mcr	p15, 0, r1, c6, c6, 0
	ldr	r1, [r0, #52]
	mcr	p15, 0, r1, c6, c7, 0
	ldr	r1, [r0, #4]
	mcr	p15, 0, r1, c2, c0, 0
	ldr	r1, [r0, #8]
	mcr	p15, 0, r1, c2, c0, 1
	ldr	r1, [r0, #12]
	mcr	p15, 0, r1, c3, c0, 0
	ldr	r1, [r0, #16]
	mcr	p15, 0, r1, c5, c0, 2
	ldr	r1, [r0, #20]
	mcr	p15, 0, r1, c5, c0, 3
	bx	lr

#endif // B4DS
