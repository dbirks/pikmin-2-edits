# Pikmin 2 AI Lab — Original GameCube Hardware Options

**Revision:** 1.0 research notes, 2026-10-09  
**Status:** independent, optional future project. **Not a dependency of the local Dolphin AI Lab.**  
**Owner's known facts:** GameCube model not yet checked; owner can solder and likes agent-assisted firmware development; owns a Raspberry Pi board described as “W2” (exactly which type is still unknown); wants Linux → modified ISO → original GameCube, preferably with no SD-card swapping. ISO already exists locally.

## Executive decision

The hardware decision depends on which success criterion you care about:

1. **Fastest, established game boot:** cheap boot method (PicoBoot or PicoLoader) + Swiss + SD adapter. You copy the ISO to removable storage. This does not need a new GameCube boot ROM.
2. **Fewest manual steps / wireless game upload:** FlippyDrive Standard; transfer to device microSD using vendor network mechanisms, then launch. Wired version optional. Hardware/firmware availability must be checked at purchase time.
3. **Established network game streaming through Swiss:** PicoBoot/PicoLoader + USB Dolphin **SP1** + known-compatible USB Ethernet adapter + Linux FSP server. Benchmark particular game/network, do not assume every USB NIC works.
4. **Open-source USB or Wi-Fi storage experiment:** PicoBoot/PicoLoader + Swiss + USB Dolphin **Slot A/B** + a Pi Zero 2 W as USB mass-storage gadget; image contents updated from Linux via SSH and presented read-only as a USB drive. Needs USB gadget capable Pi and a careful offline disk-image-swap protocol. **Not yet verified as a complete combination here.**
5. **No bootloader modification and original stock-disc illusion:** optical drive emulator (ODE) connected to the drive port. FlippyDrive and GC Loader prove the category; HyperDrive is a historical FPGA+host-source reference, *not* a validated, purchasable modern build kit. Building your own is a hardware/software R&D project.

A memory-card-slot SD or USB adapter **cannot boot an arbitrary GameCube ISO on stock firmware by itself**. It provides storage to Swiss *after Swiss has been launched* by PicoBoot, PicoLoader, save exploit or another method. “USB Dolphin” is a physical EXI-to-USB-storage peripheral, **not** the Dolphin emulator and not a straight USB cable to a GameCube.

## Architecture decision tree

```text
Must retain original firmware and boot the ISO like a physical disc?
  YES -> Full optical-drive emulator (commercial FlippyDrive / GC Loader; experimental HyperDrive-inspired DIY)
  NO  -> Boot Swiss using PicoBoot, PicoLoader, or compatible game-save exploit
           |-- okay swapping microSD? -> SD Gecko / SD2SP2 / equivalent
           |-- want direct LAN ISO reading? -> USB Dolphin SP1 + USB Ethernet + FSP
           |-- want USB storage over USB? -> USB Dolphin Slot A/B + USB stick or Pi Zero gadget
           |-- want custom low-cost Wi-Fi bridge? -> EXI/SD emulation experiment (substantial firmware risk)
```

## Options matrix

| Track | GameCube startup | Data source | Local laptop push | Maturity | Ballpark parts, *before* tax/tools/shipping |
|---|---|---|---|---|---|
| A. PicoBoot + SD Gecko/SD2SP2 | Boot modification → Swiss | microSD | Remove/copy card | Established | often ~$15–35 total if solder tools exist |
| B. PicoLoader + SD adapter | Drive-intercept bootloader → Swiss | microSD | Remove/copy card | Established | DIY kit €16 or solderless €24 **plus** SD hardware |
| C. FlippyDrive Standard | ODE, stock console IPL preserved | On-device microSD; optional network | Vendor remote FTP/SMB / companion app | Established local, network conditional | previously listed **$65** |
| D. FlippyDrive Deluxe Ethernet | ODE, stock IPL preserved | On-device microSD; Ethernet | Vendor network transfer | Established local, network conditional | previously listed **$99** |
| E. USB Dolphin Slot A/B + Pi Zero 2 W | Swiss required | USB mass-storage gadget backed by Pi file | `scp`/SSH update → gadget detach/reattach | **Composite experiment** | €35 adapter + boot mod; Pi if already owned |
| F. USB Dolphin SP1 + USB NIC | Swiss required | ISO streamed from FSP service | Build on laptop/server share | Product feature documented | €48 adapter + compatible Ethernet NIC + boot mod |
| G. DIY EXI SD/USB emulator with RP2350/ESP32 | Swiss required | microcontroller simulates storage | Custom transport | **Research project** | Unknown until design/timing validated |
| H. DIY full ODE inspired by HyperDrive | Original IPL, drive emulated | FPGA/MCU+host ISO | USB/host program | **Historical prototype** | Unknown; legacy FPGA/toolchain risk |
| I. Burned mini-DVD-R + drive mod | Disc boot from altered optical path | optical disc | Burn new disc every build | Legacy/fragile iteration | Burner/media/mod vary; **not recommended for dev loop** |

Prices are **planning observations**, not live purchase quotes. No option is endorsed as available at a particular local Micro Center. Note that GameCube **DOL-001/DOL-101, rear ports and bottom Serial Port 2 connector** can affect adapter/kit selection. Inspect hardware before ordering.

## Track A — PicoBoot + Swiss + SD (lowest-risk DIY)

**Mechanism:** Install PicoBoot on a compatible Raspberry Pi Pico/Pico 2 board and wire to GameCube motherboard. It launches gekkoboot/Swiss; Swiss reads ISO files on SD Gecko (memory-card-slot) or SD2SP2 (bottom SP2) where present. The source and installation guides exist: <https://github.com/webhdx/PicoBoot>, <https://github.com/redolution/gekkoboot>, <https://github.com/emukidid/swiss-gc>.

**Specific note:** PicoBoot v0.5.0 release lists Pico W, Pico 2 and Pico 2 W support, **with reports of some consoles falling back to stock menu**; confirm board type and test boot reliability. v0.3.1 fallback may not support Pico 2 W. Release: <https://github.com/webhdx/PicoBoot/releases>.

**Minimum extra parts:** Pico if not already owned, appropriate 4.5-mm Gamebit screwdriver, short insulated wire, solder/flux and skill, SD Gecko or SD2SP2 if supported, microSD, reader. Choose only after checking motherboard/port revision and verified wiring. **Deployment:** shut down/quit game, update microSD from laptop, reinsert, boot Swiss and select image.

**Good for:** proving real hardware loading tomorrow. **Does not solve:** Wi-Fi push without removing storage.

## Track B — PicoLoader bootloader + SD

**Mechanism:** Soldered flex-board or solderless optical-drive-interceptor boots a **small homebrew DOL**, such as Swiss, and hands optical-drive control back to original hardware. It is **not** a full disc image ODE. Needs separate game storage. Open source: <https://github.com/makeo/PicoLoader>. Store: <https://store.makstech.io/>.

**Good for:** avoiding permanent motherboard solder. **Does not solve:** remote transfer by itself. PicoLoader's use of 'ODE' describes startup interception, not whole-ISO optical-drive emulation.

## Track C — FlippyDrive (simplest remote deployment)

**Mechanism:** An optical-drive-emulation interposer; can retain original optical drive, present local microSD image and expose remote storage access via its companion application. Standard has Wi-Fi; Deluxe adds Ethernet and revision-specific rear panel. Shop: <https://www.crowdsupply.com/team-offbroadway/flippydrive>; manual: <https://docs.flippydrive.com/>; remote: <https://docs.flippydrive.com/remote-access.html>.

**Expected Linux workflow:** generate ISO; on compatible firmware start the `remote` helper (via bootloader) and host companion app; upload over documented FTP/SMB interface to microSD, return from remote to menu, launch. Initial network FTP release had fixes in later firmware, so first transfer should be a disposable small file with readback/checksum if possible. Booting while same file is being replaced is prohibited; stage immutable filename, then select.

**Alternative:** experimental live game loading from a server over network, but the project's own docs cite stringent latency and throughput (<5 ms latency, roughly 39 Mbit/s sustained Wi-Fi requirement); don't make it the only play path. <https://docs.flippydrive.com/network.html>.

**Best:** dependable product-oriented Wi-Fi workflow; **less attractive:** you want to design the electronics yourself.

## Track D — USB Dolphin hardware: what it *actually* supplies

**Slot A/B:** memory-card-slot USB host; Swiss can see USB mass storage, presented to homebrew as an SDXC or IDE-EXI device. Official shop states no USB optical CD/DVD drives and possible device incompatibilities. Price listing €35. <https://store.makstech.io/products/usb-dolphin-slot-a-b>.

**SP1:** USB host through expansion Serial Port 1, plus emulation of Broadband Adapter with a compatible USB Ethernet adapter; developer documents Swiss/FSP network game streaming. Listing €48 (excluding NIC). <https://store.makstech.io/products/usb-dolphin-sp1>.

Both require an independent way to boot Swiss. **Slot A/B does not create a direct GameCube-to-PC USB data cable automatically.** It creates a USB *host* socket into which storage hardware can be plugged.

**Pi USB-gadget idea:** A genuine **Raspberry Pi Zero 2 W** can act as a USB *device* and expose a read-only FAT filesystem image via Linux USB mass-storage gadget; upload new ISO into a replacement FAT image over Wi-Fi, detach gadget, atomically replace image and reattach. Need storage capacity greater than image+filesystem overhead. An **RP2350 Pico 2 W is not a Linux SBC** and can't run `g_mass_storage`; custom TinyUSB firmware and backing storage are needed. User's board type remains unknown. Explicitly prevent simultaneous filesystem writes while GameCube reads the gadget image.

A safer prototype progression is USB Dolphin + ordinary flash drive first, then Pi's mass-storage gadget, then remote update automation.

## Track E — DIY Wi-Fi EXI/SD device using RP2350, ESP32, or Pico W

This approach aims to impersonate an SD card (or recognized EXI storage protocol) while sourcing blocks from Wi-Fi, USB, or attached storage. It requires protocol compatibility, 3.3-V electrical design, chip-select/timing response, buffering/cache, and correct reset/disconnect semantics. Firmware possibility is **not** demonstrated by mere ability to run TCP/Wi-Fi on an ESP32. A Pi Pico's onboard USB connector does not turn PicoBoot itself into a mass-storage bridge.

**Bench gates:** implement emulator protocol against software harness → logic analyzer capture, verified low-voltage I/O → Swiss enumerates tiny test volume → immutable test file reads correctly across random seeks → raw ISO loads → 30-minute stress gameplay → remote update and rollback. Use a purchased SD Gecko/USB Dolphin as oracle for expected bus behavior. The question is *response latency and protocol correctness*, not source code length.

Never connect a 5-V memory card connector rail directly to 3.3-V MCU inputs or SPI SD card. Use verified connector mapping, appropriate translators/regulation as designed, current limiting and scoped probes.

## Track F — Full ODE and 'stock console none the wiser'

**Correct mental model:** the original GameCube IPL talks to an optical-drive controller through a digital DI interface; a **full ODE** can respond to disc-status/authentication-equivalent commands and data reads from a selected ISO. This can be done without replacing the motherboard boot ROM, though it **does** physically intercept/replace the optical-drive electrical connection. Commercial examples: FlippyDrive (interposer) and GC Loader (replaces drive): <https://gc-loader.com/>.

**Experimental source:** <https://github.com/9ary/hyperdrive> contains VHDL (`fpga/src/*.vhd`), a board pin constraints file `fpga/mimas.ucf`, Xilinx ISE build script `fpga/synthesize.sh`, and a Python ISO serving process `hyperd.py`. It targets **Numato Mimas / Xilinx XC6SLX9 TQG144** and external FTDI MPSSE SPI for host→FPGA data; USB on the legacy board is not automatically the required host data path. The host script reads ISO chunks in response to DI commands. **No complete verified connector harness, assembly guide, modern FPGA port or current release was established here.**

**Reproduction track:** simulate host protocol + FPGA in a testbench → port/test to maintained FPGA toolchain *or* carefully reproduce old hardware → design verified 32-pin optical-drive interposer with electrical and direction checks → low-level identification/boot homebrew → random ISO read coverage → full Pikmin 2 gameplay → remote host updates → (later) pass-through of original optical drive. Need logic analyzer, oscilloscope, ESD/voltage precautions and a recovery plan. This is plausibly a multi-week/month R&D project, not 'buy parts tomorrow and follow repo instructions.'

`PicoLoader` is useful *reference* for boot-time limited DI interception, not proof it already implements full ODE. `HyperDrive` is a code/reference base, not an off-the-shelf board or installation guide.

## Track G — ETH2GC and cheap networking caveats

<https://github.com/webhdx/ETH2GC> makes GameCube LAN available to Swiss through an inexpensive adapter, but **ENC28J60-based versions are not fast enough to stream ISOs**, per developer FAQ: <https://support.webhdx.dev/gc/eth2gc/faq>. ETH2GC commonly shares the bottom SP2 connector with SD2SP2, requiring a memory-card-slot SD adapter instead. Browsing a share or copying files is not the same as supported streaming game read performance; don't list network ISO boot as a proven function for these cheap adapters.

## Before purchasing anything

- Confirm GameCube underside model DOL-001 vs DOL-101 and physical **SP1 and SP2** port presence, not only stickers or generic model assumptions.
- Confirm Pi board silk screen: **Pico 2 W** microcontroller vs **Zero 2 W** Linux computer (or other).
- Confirm objective: next-day game play from SD; wireless file push; streaming over network; USB host connection; or long-term open-source ODE.
- Check soldering skill, 4.5-mm Gamebit, safe power and 3.3-V test setup; photograph/review connectors before soldering.
- Check current stock and shipping and revision support, especially model-matched external panels. Avoid buying a Nintendo Broadband Adapter unless a selected design genuinely requires it.

## Recommended staged engineering strategy

- **H0 (no purchase):** start local Dolphin AI Lab and run the existing Pikmin 2 ISO; prove mod/build/testing.
- **H1 (cheap guaranteed baseline):** PicoBoot/PicoLoader + Swiss + microSD; launch a known-good ISO. If no parts, keep H0 productive.
- **H2 (remove SD swapping):** choose FlippyDrive Wi-Fi *or* USB Dolphin SP1/FSP; establish laptop→console transfer/play loop with hashes and rollback.
- **H3 (agent electronics R&D):** implement Wi-Fi storage bridge or HyperDrive-inspired ODE, with hardware safety gates, tests and a publishable open-source schematic/firmware/repro guide.

**Recommended decision:** for fun firmware work, clone existing protocols after you have a dependable H1 reference setup; don't make unproven custom electronics the only route to play a new Pikmin cave.

## First-party and primary links

- PicoBoot: <https://github.com/webhdx/PicoBoot> / <https://github.com/webhdx/PicoBoot/releases>
- PicoLoader: <https://github.com/makeo/PicoLoader>
- Swiss: <https://github.com/emukidid/swiss-gc>
- gekkoboot: <https://github.com/redolution/gekkoboot>
- FlippyDrive: <https://www.crowdsupply.com/team-offbroadway/flippydrive> / <https://docs.flippydrive.com/>
- USB Dolphin Slot A/B: <https://store.makstech.io/products/usb-dolphin-slot-a-b>
- USB Dolphin SP1: <https://store.makstech.io/products/usb-dolphin-sp1>
- ETH2GC limitations: <https://support.webhdx.dev/gc/eth2gc/faq>
- HyperDrive source: <https://github.com/9ary/hyperdrive>
- GC Loader: <https://gc-loader.com/>
