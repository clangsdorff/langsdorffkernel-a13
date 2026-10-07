# langsdorffkernel A14 Vendor Port for Samsung Galaxy A13 4G (A135F)
**Features**
- Runs the Galaxy A14 4G (A145F) Android 15 vendor on the A13, replacing the stock 32-bit vendor and the 4.19 kernel.
- Fixed touchscreen compatibility on GSI builds.
- CPU overclocked to 2210 MHz and GPU overclocked to 1196 MHz.
- Boots into the `energy_aware` governor instead of `schedutil`.
- Reworked GPU DVFS: fixed the dead highspeed jump, retuned thresholds, lowered the CPU floors.
- Every GPU clock step reachable and holdable. 1105 MHz opens at 65% utilization, 1196 MHz at 70%.
- Floor under the GPU clock ceiling, default 1001 MHz.
- Runtime tunables for the GPU ceiling floor and the governor redirect.
- Official KernelSU v3.3.0 with SUSFS v2.3.0.
- Dex touchpad support for OneUI ROMs.
- Removed firmware checks from check_connection in novatek touchscreen driver to fix 2 seconds delay for RestlessOS treble patchset based GSI's
- Built-in hook for the `${fps_position}` bug in flagship FOD ports.
- A13 fingerprint (Egis ET528), NFC (NXP PN557) and cameras (S5KJN1, GC08A3, GC5035, GC02M1) on the A14 vendor.
- /data encrypted with the stock A14 FBE flags.
- AVB and some security checks disabled.
- Based on Linux 5.10.236.

**Known Issues**
- USB OTG is not confirmed to work.
- Camera fixes are waiting for test results. Ultra-wide and macro calibration is not read yet.
- Dex touchpad does not work on the OVT TD4150 touchscreen.

# Installation
**Installation — Odin3**
1. Download the latest ".tar" from the build.
2. Power off the device.
3. Boot into Download Mode (connect to PC while holding Volume UP + Volume DOWN).
4. Open Odin3 and place the `.tar` into the `AP` slot.
5. Flash and wait for the device to reboot.

**Installation — TWRP**
1. Download the latest kernel ".zip" and "_vendor.zip" from the build.
2. Boot into Recovery Mode (TWRP).
3. Select `Install` → choose the kernel `.zip` file.
4. Extract "_vendor.zip", select `Install Image` → choose the `.img` and flash it to `Vendor`.
5. Format data (once, when coming from stock or an unencrypted build).
6. Reboot.

**Join / Follow**
- Telegram: https://t.me/a14stuffs

**Credits**
- Base kernel: [Gabriel2392](https://github.com/Gabriel2392)
- CPU & GPU Overclock, `${fps_position}` hook, updated sdfat driver: [Gabriel2392](https://github.com/Gabriel2392)
- Dex touchpad support: [rsuntk](https://github.com/rsuntk)
- KernelSU: [tiann](https://github.com/tiann/)

# Download
- Every push to `a13-port` builds the kernel and the vendor image.
- The gofile link and the SHA256 checksums are in the GitHub Actions run summary.

**Device & Notes**
- Device: A135F (Exynos 850)
- Vendor: A145FXXSEDZF2
