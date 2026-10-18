// SPDX-License-Identifier: GPL-2.0
/*
 * Samsung Exynos SoC series Pablo driver
 *
 * Copyright (c) 2020 Samsung Electronics Co., Ltd
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 */

#include <asm/fpsimd.h>
#include <asm/neon.h>

#include "is-hw.h"
#include "is-config.h"

#if defined(ENABLE_FPSIMD_FOR_USER)
#if defined(LOCAL_FPSIMD_API)
#define NUM_OF_MAX_CORE		8
/* task -> func -> isr, plus one spare for a DDK that re-enables IRQs inside a call */
#define IS_FPSIMD_MAX_DEPTH	4

struct is_fpsimd_stack {
	struct is_fpsimd_state	state[IS_FPSIMD_MAX_DEPTH];
	unsigned long		irq_flags[IS_FPSIMD_MAX_DEPTH];
	bool			saved[IS_FPSIMD_MAX_DEPTH];
	bool			bh[IS_FPSIMD_MAX_DEPTH];
	int			depth;
};

static struct is_fpsimd_stack fpsimd_stack[NUM_OF_MAX_CORE];

/* Outside IRQ context the user state goes to the task, so a DDK that sleeps cannot leak its registers */
static bool is_fpsimd_flush(void)
{
	if (in_interrupt() || irqs_disabled())
		return false;

	local_bh_disable();
	fpsimd_save_and_flush_cpu_state();
	local_bh_enable();
	return true;
}

/* A softirq kernel_neon_begin() would see the CPU state as free and clobber the DDK registers */
static bool is_fpsimd_bh_disable(void)
{
	if (in_interrupt())
		return false;

	local_bh_disable();
	return true;
}

static void is_fpsimd_bh_enable(bool bh)
{
	if (!bh)
		return;

	if (irqs_disabled())
		_local_bh_enable();
	else
		local_bh_enable();
}

static int is_fpsimd_push(bool flushed)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	int idx = s->depth;

	if (WARN_ONCE(idx >= IS_FPSIMD_MAX_DEPTH, "is_fpsimd: depth %d overflow\n", idx))
		return -1;

	s->depth = idx + 1;
	barrier();
	s->saved[idx] = !flushed;
	if (!flushed)
		is_fpsimd_save_state(&s->state[idx]);

	return idx;
}

static void is_fpsimd_pop(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	int idx = s->depth - 1;

	if (WARN_ONCE(idx < 0, "is_fpsimd: unbalanced put\n"))
		return;

	if (s->saved[idx])
		is_fpsimd_load_state(&s->state[idx]);
	barrier();
	s->depth = idx;
}

void is_fpsimd_get_isr(void)
{
	is_fpsimd_push(false);
}

void is_fpsimd_put_isr(void)
{
	is_fpsimd_pop();
}

void is_fpsimd_get_func(void)
{
	struct is_fpsimd_stack *s;
	unsigned long flags;
	bool flushed, bh;
	int idx;

	preempt_disable();
	flushed = is_fpsimd_flush();
	bh = is_fpsimd_bh_disable();
	local_irq_save(flags);

	s = &fpsimd_stack[smp_processor_id()];
	idx = is_fpsimd_push(flushed);
	if (idx >= 0) {
		s->irq_flags[idx] = flags;
		s->bh[idx] = bh;
	}
}

void is_fpsimd_put_func(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	unsigned long flags = s->depth > 0 ? s->irq_flags[s->depth - 1] : 0;
	bool bh = s->depth > 0 && s->bh[s->depth - 1];

	WARN_ONCE(!irqs_disabled(), "is_fpsimd: DDK returned with IRQs enabled\n");

	is_fpsimd_pop();

	local_irq_restore(flags);
	is_fpsimd_bh_enable(bh);
	preempt_enable();
}

void is_fpsimd_get_task(void)
{
	bool flushed, bh;
	int idx;

	preempt_disable();
	flushed = is_fpsimd_flush();
	bh = is_fpsimd_bh_disable();

	idx = is_fpsimd_push(flushed);
	if (idx >= 0)
		fpsimd_stack[smp_processor_id()].bh[idx] = bh;
}

void is_fpsimd_put_task(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	bool bh = s->depth > 0 && s->bh[s->depth - 1];

	is_fpsimd_pop();

	is_fpsimd_bh_enable(bh);
	preempt_enable();
}

void is_fpsimd_set_task_using(struct task_struct *t)
{
	return;
}
#else
void is_fpsimd_get_isr(void)
{
	kernel_neon_begin();
}

void is_fpsimd_put_isr(void)
{
	kernel_neon_end();
}

void is_fpsimd_get_func(void)
{
	fpsimd_get();
}

void is_fpsimd_put_func(void)
{
	fpsimd_put();
}

void is_fpsimd_get_task(void)
{
}

void is_fpsimd_put_task(void)
{
}

void is_fpsimd_set_task_using(struct task_struct *t)
{
	fpsimd_set_task_using(t);
}
#endif
#endif
