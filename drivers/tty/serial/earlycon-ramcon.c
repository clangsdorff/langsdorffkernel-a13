// SPDX-License-Identifier: GPL-2.0
#include <linux/console.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/serial_core.h>

/* persistent_ram_buffer layout, so a pstore ramoops zone at the same address reads it back after a warm reset */
#define RAMCON_SIG	0x43474244
#define RAMCON_HDR	12
#define RAMCON_CAP	(PAGE_SIZE - RAMCON_HDR)

static u32 ramcon_start, ramcon_size;

static void ramcon_write(struct console *con, const char *s, unsigned int n)
{
	struct earlycon_device *dev = con->data;
	void __iomem *base = dev->port.membase;

	while (n--) {
		writeb_relaxed(*s++, base + RAMCON_HDR + ramcon_start);
		if (++ramcon_start == RAMCON_CAP)
			ramcon_start = 0;
		if (ramcon_size < RAMCON_CAP)
			ramcon_size++;
	}
	writel_relaxed(ramcon_start, base + 4);
	writel(ramcon_size, base + 8);
}

static int __init early_ramcon_setup(struct earlycon_device *device, const char *opt)
{
	void __iomem *base = device->port.membase;

	/* earlycon_map() maps a single page */
	if (!base || (device->port.mapbase & ~PAGE_MASK))
		return -EINVAL;

	writel_relaxed(0, base + 4);
	writel_relaxed(0, base + 8);
	writel(RAMCON_SIG, base);
	device->con->write = ramcon_write;
	return 0;
}
EARLYCON_DECLARE(ramcon, early_ramcon_setup);
