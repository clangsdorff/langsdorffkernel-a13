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
/* func -> isr, plus spares for a DDK that re-enables IRQs inside a call */
#define IS_FPSIMD_MAX_DEPTH	4

struct is_fpsimd_stack {
	struct is_fpsimd_state	state[IS_FPSIMD_MAX_DEPTH];
	unsigned long		irq_flags[IS_FPSIMD_MAX_DEPTH];
	bool			saved[IS_FPSIMD_MAX_DEPTH];
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
	unsigned long flags;
	bool flushed;
	int idx;

	preempt_disable();
	flushed = is_fpsimd_flush();
	local_irq_save(flags);

	idx = is_fpsimd_push(flushed);
	if (idx >= 0)
		fpsimd_stack[smp_processor_id()].irq_flags[idx] = flags;
}

void is_fpsimd_put_func(void)
{
	struct is_fpsimd_stack *s = &fpsimd_stack[smp_processor_id()];
	unsigned long flags = s->depth > 0 ? s->irq_flags[s->depth - 1] : 0;

	WARN_ONCE(!irqs_disabled(), "is_fpsimd: DDK returned with IRQs enabled\n");

	is_fpsimd_pop();

	local_irq_restore(flags);
	preempt_enable();
}

/* The DDK sleeps in task context, so its registers follow the thread across switches like 4.19 fpsimd_set_task_using() */
static void is_fpsimd_task_sched_in(struct preempt_notifier *pn, int cpu)
{
	struct is_fpsimd_task *t = container_of(pn, struct is_fpsimd_task, pn);
	unsigned long flags;

	local_irq_save(flags);
	fpsimd_save_and_flush_cpu_state();
	is_fpsimd_load_state(&t->state);
	local_irq_restore(flags);
}

static void is_fpsimd_task_sched_out(struct preempt_notifier *pn,
				     struct task_struct *next)
{
	struct is_fpsimd_task *t = container_of(pn, struct is_fpsimd_task, pn);

	is_fpsimd_save_state(&t->state);
}

static struct preempt_ops is_fpsimd_task_ops = {
	.sched_in	= is_fpsimd_task_sched_in,
	.sched_out	= is_fpsimd_task_sched_out,
};

void is_fpsimd_get_task(struct is_fpsimd_task *t)
{
	preempt_disable();
	is_fpsimd_flush();
	preempt_notifier_init(&t->pn, &is_fpsimd_task_ops);
	preempt_notifier_register(&t->pn);
	preempt_enable();
}

void is_fpsimd_put_task(struct is_fpsimd_task *t)
{
	preempt_disable();
	preempt_notifier_unregister(&t->pn);
	preempt_enable();
}

void is_fpsimd_set_task_using(struct task_struct *t)
{
	static atomic_t notifier_on = ATOMIC_INIT(0);

	if (!atomic_xchg(&notifier_on, 1))
		preempt_notifier_inc();
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

void is_fpsimd_get_task(struct is_fpsimd_task *t)
{
}

void is_fpsimd_put_task(struct is_fpsimd_task *t)
{
}

void is_fpsimd_set_task_using(struct task_struct *t)
{
	fpsimd_set_task_using(t);
}
#endif
#endif
