# Makefile for the Himax touchscreen drivers.

obj-$(CONFIG_TOUCHSCREEN_HIMAX_COMMON)		+= himax_831xx.o
himax_831xx-y					:= himax_common.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_I2C)	+= himax_platform.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_SPI)	+= himax_platform_SPI.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_INCELL_CORE)	+= himax_ic_incell_core.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_IC_HX83102)	+= himax_ic_HX83102.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_IC_HX83108)	+= himax_ic_HX83108.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_IC_HX83112)	+= himax_ic_HX83112.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_IC_HX83121)	+= himax_ic_HX83121.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_DEBUG)	+= himax_debug.o
himax_831xx-$(CONFIG_TOUCHSCREEN_HIMAX_INSPECT)	+= himax_inspection.o

ccflags-$(CONFIG_SAMSUNG_TUI)	+= -Idrivers/misc/tui
