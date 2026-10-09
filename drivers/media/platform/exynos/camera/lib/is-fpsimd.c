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
	int			depth;
};

static struct is_fpsimd_stack fpsimd_stack[NUM_OF_MAX_CORE];

static int is_fpsimd_push(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	int idx = s->depth;

	if (WARN_ONCE(idx >= IS_FPSIMD_MAX_DEPTH, "is_fpsimd: depth %d overflow\n", idx))
		return -1;

	s->depth = idx + 1;
	barrier();
	is_fpsimd_save_state(&s->state[idx]);

	return idx;
}

static void is_fpsimd_pop(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	int idx = s->depth - 1;

	if (WARN_ONCE(idx < 0, "is_fpsimd: unbalanced put\n"))
		return;

	is_fpsimd_load_state(&s->state[idx]);
	barrier();
	s->depth = idx;
}

void is_fpsimd_get_isr(void)
{
	is_fpsimd_push();
}

void is_fpsimd_put_isr(void)
{
	is_fpsimd_pop();
}

void is_fpsimd_get_func(void)
{
	unsigned long flags;
	int idx;

	local_irq_save(flags);
	preempt_disable();

	idx = is_fpsimd_push();
	if (idx >= 0)
		fpsimd_stack[smp_processor_id()].irq_flags[idx] = flags;
}

void is_fpsimd_put_func(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	unsigned long flags = s->depth > 0 ? s->irq_flags[s->depth - 1] : 0;

	WARN_ONCE(!irqs_disabled(), "is_fpsimd: DDK returned with IRQs enabled\n");

	is_fpsimd_pop();

	preempt_enable();
	local_irq_restore(flags);
}

void is_fpsimd_get_task(void)
{
	preempt_disable();

	is_fpsimd_push();
}

void is_fpsimd_put_task(void)
{
	is_fpsimd_pop();

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
