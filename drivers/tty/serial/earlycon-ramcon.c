// SPDX-License-Identifier: GPL-2.0
#include <linux/console.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/printk.h>
#include <linux/serial_core.h>
#include <linux/string.h>
#include <asm/fixmap.h>

/* stock 4.19 debug-snapshot: LK logs from the start of log_kernel and leaves its end address at header + 0x200 */
#define DSS_LAST_LOGBUF		0x200
#define LOG_KERNEL_BASE		0xf0010000UL
#define LOG_KERNEL_END		(LOG_KERNEL_BASE + 0x200000 - 8)
/* "Full\n" at the last 8 bytes makes stock last_kmsg dump the whole ring instead of only up to LK's end */
#define LKMSG_FULL_MAGIC	0x0000000a6c6c7546ULL

/* persistent_ram_buffer in stock recovery's ramoops pmsg zone */
#define PMSG_BASE		0xf0f14000UL
#define PMSG_SIG		0x43474244
#define PMSG_HDR		12
#define PMSG_CAP		(PAGE_SIZE - PMSG_HDR)

static phys_addr_t hdr_phys, mapped_page, log_pos;
static u32 pmsg_start, pmsg_size;

/* earlycon owns a single fixmap page, so it is moved to whichever page is written next */
static void __iomem *ramcon_map(phys_addr_t phys)
{
	if ((phys & PAGE_MASK) != mapped_page) {
		clear_fixmap(FIX_EARLYCON_MEM_BASE);
		set_fixmap_io(FIX_EARLYCON_MEM_BASE, phys & PAGE_MASK);
		mapped_page = phys & PAGE_MASK;
	}
	return (void __iomem *)__fix_to_virt(FIX_EARLYCON_MEM_BASE) + (phys & ~PAGE_MASK);
}

static void log_write(const char *s, unsigned int n)
{
	while (n) {
		unsigned int len = min_t(phys_addr_t, n,
					 min_t(phys_addr_t, PAGE_SIZE - (log_pos & ~PAGE_MASK),
					       LOG_KERNEL_END - log_pos));

		memcpy_toio(ramcon_map(log_pos), s, len);
		s += len;
		n -= len;
		log_pos += len;
		if (log_pos == LOG_KERNEL_END)
			log_pos = LOG_KERNEL_BASE;
	}
	writel(log_pos, ramcon_map(hdr_phys + DSS_LAST_LOGBUF));
}

static void pmsg_write(const char *s, unsigned int n)
{
	void __iomem *base = ramcon_map(PMSG_BASE);

	while (n--) {
		writeb_relaxed(*s++, base + PMSG_HDR + pmsg_start);
		if (++pmsg_start == PMSG_CAP)
			pmsg_start = 0;
		if (pmsg_size < PMSG_CAP)
			pmsg_size++;
	}
	writel_relaxed(pmsg_start, base + 4);
	writel(pmsg_size, base + 8);
}

static void ramcon_write(struct console *con, const char *s, unsigned int n)
{
	log_write(s, n);
	pmsg_write(s, n);
}

static int __init early_ramcon_setup(struct earlycon_device *device, const char *opt)
{
	static const char mark[] = "\n==== ramcon: 5.10 earlycon ====\n";
	void __iomem *base = device->port.membase;
	u32 last;

	/* earlycon=ramcon,<dss header>; earlycon_map() mapped exactly that page */
	if (!base || (device->port.mapbase & ~PAGE_MASK))
		return -EINVAL;

	hdr_phys = device->port.mapbase;
	mapped_page = hdr_phys;
	last = readl(base + DSS_LAST_LOGBUF);
	log_pos = (last >= LOG_KERNEL_BASE && last < LOG_KERNEL_END) ? last : LOG_KERNEL_BASE;
	writeq(LKMSG_FULL_MAGIC, ramcon_map(LOG_KERNEL_END));

	base = ramcon_map(PMSG_BASE);
	writel_relaxed(0, base + 4);
	writel_relaxed(0, base + 8);
	writel(PMSG_SIG, base);

	log_write(mark, sizeof(mark) - 1);
	log_write(linux_banner, strlen(linux_banner));
	device->con->write = ramcon_write;
	return 0;
}
EARLYCON_DECLARE(ramcon, early_ramcon_setup);
