# Electronics AI Training - Real Data Sources Catalog

> Exhaustive research conducted 2026-03-26. Only REAL data (not synthetic/generated).

---

## 1. ASSEMBLY LANGUAGE

### 1.1 GitHub Repos (High Stars)

| Source | URL | Stars | License | Format | Size Est. | Quality |
|--------|-----|-------|---------|--------|-----------|---------|
| **Dozens of minimal OSes (x86)** | github.com/topics/assembly (top) | ~5.1k | Various | ASM code | ~50MB | 9/10 |
| **ARM64 ASM on Apple Silicon** | github.com (top ARM asm) | ~4.7k | MIT | Tutorial+code | ~20MB | 8/10 |
| **pkivolowitz/asm_book** | github.com/pkivolowitz/asm_book | ~1k+ | MIT | Book+exercises | ~30MB | 9/10 |
| **diffstorm/extended_asm** | github.com/diffstorm/extended_asm | ~200+ | MIT | ARM/MIPS/x86/x64 | ~5MB | 7/10 |

**Conversion**: Clone repos, extract .asm/.s files, pair with README explanations for instruction-tuning pairs.

### 1.2 OS Kernels with ASM

| Source | URL | Stars | License | Format | Size Est. | Quality |
|--------|-----|-------|---------|--------|-----------|---------|
| **Linux kernel** (arch/) | github.com/torvalds/linux | 195k+ | GPL-2.0 | ASM+C | ~200MB asm only | 10/10 |
| **xv6 (MIT)** | github.com/mit-pdos/xv6-public | ~7k+ | MIT | x86 ASM+C | ~2MB | 10/10 |
| **xv6-riscv** | github.com/mit-pdos/xv6-riscv | ~7k+ | MIT | RISC-V ASM+C | ~2MB | 10/10 |
| **seL4 microkernel** | github.com/seL4/seL4 | ~5k+ | GPL-2.0 | ARM/x86/RISC-V ASM | ~15MB | 10/10 |

**Conversion**: Extract arch-specific ASM, pair with commit messages and documentation for context.

### 1.3 Reverse Engineering / CTF

| Source | URL | License | Format | Size Est. | Quality |
|--------|-----|---------|--------|-----------|---------|
| **Nightmare (guyinatuxedo)** | guyinatuxedo.github.io | Free | 90+ RE challenges+writeups | ~100MB | 9/10 |
| **OpenToAllCTF/REsources** | github.com/OpenToAllCTF/REsources | Free | Curated RE challenges | ~50MB | 8/10 |
| **PUXSY/Reverse-Engineering-CTF** | github.com/PUXSY/Reverse-Engineering-CTF | Free | 10 levels binaries | ~10MB | 7/10 |
| **crackmes.de archive** | (via REsources) | Free | Binary challenges | ~500MB+ | 8/10 |

**Conversion**: Extract challenge binaries + solutions as (binary->disassembly->explanation) triples.

### 1.4 University Courses

| Source | URL | Format | Quality |
|--------|-----|--------|---------|
| **MIT 6.828 OS Engineering** | ocw.mit.edu/courses/6-828* | Lectures+labs+ASM | 10/10 |
| **Nand2Tetris** | nand2tetris.org / GitHub topics | Hack ASM exercises | 9/10 |
| **CMU Embedded Systems** | users.ece.cmu.edu/~koopman/lectures | Lecture notes | 8/10 |

### 1.5 Mega Datasets

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **The Stack v2** (assembly subset) | huggingface.co/datasets/bigcode/the-stack-v2 | Permissive | ASM code from GitHub | ~GB-scale | 8/10 |
| **NVIDIA Nemotron Code v2** | huggingface.co/datasets/nvidia/Nemotron-Pretraining-Code-v2 | CC-BY-4.0 | Code incl. ASM | 427.9B tokens total | 8/10 |

**Conversion**: Filter by language='assembly' from the full dataset.

---

## 2. KiCad / PCB DESIGN

### 2.1 Real KiCad Project Repos

| Source | URL | Stars | License | Format | Size Est. | Quality |
|--------|-----|-------|---------|--------|-----------|---------|
| **LibreSolar** (full ecosystem) | github.com/LibreSolar | ~500+ total | CERN-OHL-W | KiCad + firmware | ~200MB | 10/10 |
| **Antmicro hardware-components** | github.com/antmicro/hardware-components | ~200+ | Apache-2.0 | KiCad symbols+FP+3D | ~500MB | 9/10 |
| **System76 Launch keyboard** | github.com/system76/launch | ~1k+ | GPL-3.0 | KiCad PCB | ~50MB | 9/10 |
| **QMK keyboard designs** | github.com/qmk (ecosystem) | 20k+ | GPL-2.0 | KiCad schematics | ~1GB+ | 8/10 |
| **placa_lorawan** | github.com/phfbertoleti/placa_lorawan | ~100+ | MIT | KiCad LoRaWAN dev board | ~10MB | 7/10 |
| **Dragino LoRa hardware** | github.com/dragino/Lora | ~300+ | Various | KiCad + Eagle | ~100MB | 8/10 |
| **Olimex open hardware** | github.com/OLIMEX (many repos) | Various | CERN-OHL | KiCad schematics | ~500MB | 9/10 |

**Conversion**: Parse .kicad_sch and .kicad_pcb (text-based S-expression format) directly. Extract component lists, net connections, design rules.

### 2.2 KiCad Datasets (HuggingFace)

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **bshada/open-schematics** | huggingface.co/datasets/bshada/open-schematics | CC-BY-4.0 | 84k KiCad schematics + PNG + metadata | ~10GB+ | 9/10 |
| **STEM-AI-mtl/Electrical-engineering** | huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering | Open | Q&A (65% EE, 25% KiCad, 10% Python scripting) | ~50MB | 8/10 |

**open-schematics is the single best KiCad training resource available.**

### 2.3 KiCad Forum (forum.kicad.info)

- **Platform**: Discourse-based, publicly accessible
- **Content**: 100k+ posts on design review, troubleshooting, scripting
- **Format**: Q&A, discussion threads
- **License**: CC-BY-SA (Discourse default)
- **Size**: ~500MB+ text
- **Quality**: 8/10
- **Conversion**: Discourse API to extract threads, filter by tag (schematic, PCB, scripting). Pair question+accepted answer.

### 2.4 OSHWA Certified Projects

- **URL**: certification.oshwa.org/list.html
- **Content**: 2000+ certified open hardware projects, many with KiCad files on GitHub
- **License**: Various open licenses
- **Conversion**: Scrape certification list, follow GitHub links, clone KiCad repos
- **Quality**: 9/10 (verified open hardware)

### 2.5 JLCPCB / EasyEDA Open Projects

- **URL**: oshwlab.com (EasyEDA open projects)
- **Content**: 100k+ public PCB designs
- **Format**: EasyEDA JSON (convertible)
- **Quality**: 6/10 (variable quality, many hobby projects)

---

## 3. SPICE / ANALOG SIMULATION

### 3.1 ngspice

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **ngspice source + tests** | github.com/ngspice/ngspice | BSD-3 | SPICE netlists, regression tests | ~100MB | 9/10 |
| **ngspice regression suite** | git clone git://git.code.sf.net/p/ngspice/ngspice | BSD-3 | ~500+ test circuits | ~50MB | 9/10 |
| **Berkeley SPICE3 benchmarks** | (included in ngspice) | BSD | Benchmark circuits | ~10MB | 9/10 |

**Conversion**: Extract .cir/.spice files from tests/ directory. Pair with test descriptions and expected outputs.

### 3.2 LTspice

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **Analog Devices LTspice demos** | analog.com/ltspice | Freeware | .asc schematics + .plt | ~500MB+ | 10/10 |
| **mick001/Circuits-LTSpice** | github.com/mick001/Circuits-LTSpice | Free | LTspice IV circuits | ~20MB | 7/10 |
| **nunobrum/spicelib** | github.com/nunobrum/spicelib | GPL-3.0 | Python + example netlists | ~10MB | 8/10 |

**Conversion**: LTspice .asc files are text-based. Parse into netlist + component values + simulation commands.

### 3.3 Manufacturer Resources

| Source | URL | Format | Size | Quality |
|--------|-----|--------|------|---------|
| **Analog Devices SPICE models** | analog.com/en/resources/simulation-models.html | SPICE subcircuits | ~1GB | 10/10 |
| **TI PSpice models** | ti.com/tool/PSPICE-FOR-TI | PSpice netlists | ~2GB+ | 10/10 |
| **TI Reference Designs** | ti.com reference designs | Schematics + sim files | ~5GB+ | 10/10 |
| **AD Circuits from the Lab** | analog.com reference designs | Complete circuits | ~2GB | 10/10 |

**Conversion**: Download SPICE model libraries, parse .lib/.sub files. TI reference designs include full simulation netlists.

### 3.4 University Courses

| Source | URL | Format | Quality |
|--------|-----|--------|---------|
| **Cornell ECE 5745 SPICE Tutorial** | cornell-ece5745.github.io/ece5745-tut10-spice | Tutorial + examples | 8/10 |
| **ADI University Program** | wiki.analog.com/university | Courses + lab circuits | 9/10 |

---

## 4. EMBEDDED / FIRMWARE

### 4.1 Official SDK Examples

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **ESP-IDF examples** | github.com/espressif/esp-idf/tree/master/examples | 14k+ | Apache-2.0 | C code, ~100+ examples | ~500MB | 10/10 |
| **STM32CubeF4** | github.com/STMicroelectronics/STM32CubeF4 | ~1k+ | BSD-3 | HAL+LL+examples | ~1GB | 10/10 |
| **STM32CubeH7** | github.com/STMicroelectronics/STM32CubeH7 | ~500+ | BSD-3 | HAL+LL+examples | ~1.5GB | 10/10 |
| **STM32CubeG4** | github.com/STMicroelectronics/STM32CubeG4 | ~300+ | BSD-3 | HAL+LL+examples | ~800MB | 10/10 |
| **Zephyr RTOS samples** | github.com/zephyrproject-rtos/zephyr/tree/main/samples | 12k+ | Apache-2.0 | C code, 200+ samples | ~2GB | 10/10 |
| **FreeRTOS** | github.com/FreeRTOS/FreeRTOS | 7.1k+ | MIT | C code, multi-platform demos | ~500MB | 10/10 |
| **FreeRTOS-Kernel** | github.com/FreeRTOS/FreeRTOS-Kernel | ~3k+ | MIT | Kernel only | ~50MB | 10/10 |
| **ARM Mbed OS** | github.com/ARMmbed/mbed-os | ~4.7k+ | Apache-2.0 | C++ code, drivers, RTOS | ~1GB | 9/10 |
| **ESP-IoT-Solution** | github.com/espressif/esp-iot-solution | ~2k+ | Apache-2.0 | IoT drivers + solutions | ~300MB | 9/10 |

**Conversion**: Each example has main.c + README + CMakeLists.txt. Extract (description, code, build config) tuples.

### 4.2 Arduino Ecosystem

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **Arduino core** | github.com/arduino/ArduinoCore-avr | ~1k+ | LGPL-2.1 | C++ core + examples | ~50MB | 9/10 |
| **Arduino-FOC (SimpleFOC)** | github.com/simplefoc/Arduino-FOC | ~2k+ | MIT | Motor control lib | ~20MB | 9/10 |
| **Adafruit libraries** (ecosystem) | github.com/adafruit | 1k+ repos | MIT/BSD | Sensor drivers + examples | ~5GB+ | 9/10 |
| **SparkFun libraries** | github.com/sparkfun | 500+ repos | Various | Sensor drivers + examples | ~3GB+ | 8/10 |
| **gavmac00/arduino-docs** | huggingface.co/datasets/gavmac00/arduino-docs | - | Open | 14.3k rows documentation | 10.5MB | 7/10 |
| **arduinolibraries.info** | arduinolibraries.info/libraries | - | Various | 7000+ library index | Index only | 7/10 |

**Conversion**: Arduino .ino files + library examples are self-contained. Extract with associated comments and README.

### 4.3 Community Collections

| Source | URL | Stars | License | Format | Quality |
|--------|-----|-------|---------|--------|---------|
| **Awesome-Embedded (nhivp)** | github.com/nhivp/Awesome-Embedded | ~2k+ | Free | Curated link list | 8/10 |
| **awesome-embedded-software (iDoka)** | github.com/iDoka/awesome-embedded-software | ~1k+ | Free | Libs for 8/16/32-bit MCUs | 8/10 |
| **awesome-electronics (kitspace)** | github.com/kitspace/awesome-electronics | ~6k+ | Free | Complete EE resource list | 9/10 |
| **memfault/awesome-embedded** | github.com/memfault/awesome-embedded | ~1k+ | Free | Frameworks + libs | 8/10 |

---

## 5. VERILOG / FPGA

### 5.1 RISC-V Core Implementations

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **PicoRV32** | github.com/YosysHQ/picorv32 | ~3k+ | ISC | Verilog RV32 CPU | ~5MB | 10/10 |
| **VexRiscv** | github.com/SpinalHDL/VexRiscv | ~2.5k+ | MIT | SpinalHDL->Verilog | ~20MB | 10/10 |
| **DarkRISCV** | github.com/darklife/darkriscv | ~2k+ | BSD-3 | Verilog RV32I in 1 night | ~2MB | 9/10 |
| **NEORV32** | github.com/stnolting/neorv32 | ~2k+ | BSD-3 | VHDL RV32 SoC | ~30MB | 10/10 |
| **Ibex (lowRISC)** | github.com/lowRISC/ibex | ~1.5k+ | Apache-2.0 | SystemVerilog RV32 | ~20MB | 10/10 |

### 5.2 OpenCores Archive

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **fabriziotappero/ip-cores** | github.com/fabriziotappero/ip-cores | Various OSS | VHDL+Verilog IP cores (each branch = project) | ~2GB+ | 8/10 |
| **FreeCores mirror** | github.com/freecores | Various | Verilog/VHDL cores | ~1GB+ | 7/10 |
| **OpenCores.org** | opencores.org/projects | Various OSS | UART, SPI, I2C, processors | ~5GB+ | 8/10 |

**Conversion**: Each IP core is a self-contained project with RTL + testbench + docs. Extract (spec, RTL, testbench) triples.

### 5.3 Educational FPGA Repos

| Source | URL | Stars | License | Format | Quality |
|--------|-----|-------|---------|--------|---------|
| **BrunoLevy/learn-fpga** | github.com/BrunoLevy/learn-fpga | ~3k+ | MIT | Verilog tutorials + RISC-V | 10/10 |
| **nandland/getting-started-with-fpgas** | github.com/nandland/getting-started-with-fpgas | ~1k+ | Free | Verilog+VHDL tutorials | 9/10 |
| **Obijuan/open-fpga-verilog-tutorial** | github.com/Obijuan/open-fpga-verilog-tutorial | ~700+ | GPL | 30+ Verilog examples | 8/10 |
| **Xilinx/Vivado-Design-Tutorials** | github.com/Xilinx/Vivado-Design-Tutorials | ~500+ | Various | Official AMD tutorials | 9/10 |
| **FPGAcademy tutorials** | fpgacademy.org/tutorials.html | - | Free | Intel/Altera Quartus labs | 8/10 |
| **Analog Devices HDL** | github.com/analogdevicesinc/hdl | ~1.5k+ | Various | FPGA reference designs | 9/10 |

### 5.4 HuggingFace Verilog Datasets

| Source | URL | Downloads | License | Format | Size | Quality |
|--------|-----|-----------|---------|--------|------|---------|
| **shailja/Verilog_GitHub** | huggingface.co/datasets/shailja/Verilog_GitHub | 337 | MIT | 100k-1M Verilog modules from GitHub | ~500MB | 8/10 |
| **bnadimi/PyraNet-Verilog** | huggingface.co/datasets/bnadimi/PyraNet-Verilog | 282 | CC-BY-NC-SA-4.0 | 100k-1M hierarchical Verilog | ~500MB | 9/10 |
| **GaTech-EIC/MG-Verilog** | huggingface.co/datasets/GaTech-EIC/MG-Verilog | 224 | MIT | Multi-grained desc+code pairs | ~200MB | 9/10 |
| **dakies/nvlabs-verilogeval** | huggingface.co/datasets/dakies/nvlabs-verilogeval | 1.3k | MIT | 156 eval problems from HDLBits | ~5MB | 9/10 |
| **Ani-DNN/Verify-Verilog** | huggingface.co/datasets/Ani-DNN/Verify-Verilog | 6 | MIT | 1,192 bench problems + testbenches | ~50MB | 9/10 |
| **rtl-llm/chisel-verilog-pairs** | huggingface.co/datasets/rtl-llm/chisel-verilog-pairs | 18 | Open | 10k-100k Chisel->Verilog pairs | ~100MB | 8/10 |
| **vkenbeek/verilog-wavedrom** | huggingface.co/datasets/vkenbeek/verilog-wavedrom | 24 | MIT | Verilog + timing diagrams (PNG) | ~200MB | 8/10 |
| **wangxinze/Verilog_data** | huggingface.co/datasets/wangxinze/Verilog_data | 44 | Apache-2.0 | 100k-1M entries | ~500MB | 7/10 |

### 5.5 EDA / Chip Design Datasets

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **CircuitNet** | github.com/circuitnet/CircuitNet | Open | 20k+ chip design samples (14nm, 28nm) | ~50GB+ | 10/10 |
| **CircuitNet 3.0** | (openreview.net) | Open | 15,000+ instances, timing+power | ~100GB | 10/10 |

---

## 6. AI ON CHIP / TinyML

### 6.1 Official Frameworks

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **MAX78000 ai8x-training** | github.com/analogdevicesinc/ai8x-training | ~500+ | Apache-2.0 | PyTorch training for CNN accelerator | ~200MB | 10/10 |
| **MAX78000 ai8x-synthesis** | github.com/analogdevicesinc/ai8x-synthesis | ~400+ | Apache-2.0 | Model->C code generator | ~100MB | 10/10 |
| **ESP-WHO** | github.com/espressif/esp-who | ~2k+ | Apache-2.0 | Face detection/recognition | ~100MB | 9/10 |
| **ESP-DL** | github.com/espressif/esp-dl | ~600+ | Apache-2.0 | Neural network inference | ~200MB | 9/10 |
| **STM32AI_Overall_Offer** | github.com/STMicroelectronics/STM32AI_Overall_Offer | ~200+ | Various | AI model zoo for STM32 | ~500MB | 9/10 |
| **TFLite Micro** | github.com/tensorflow/tflite-micro | ~2k+ | Apache-2.0 | Reference implementations | ~300MB | 10/10 |

### 6.2 Edge Impulse

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **Edge Impulse Datasets** | docs.edgeimpulse.com/datasets | Apache-2.0 | Audio/image/sensor datasets | ~10GB+ | 9/10 |
| **expert-projects** | github.com/edgeimpulse/expert-projects | Apache-2.0 | Project tutorials + code | ~100MB | 8/10 |
| **KWS dataset** | (Edge Impulse) | Apache-2.0 | 2,062 audio items, 34min | ~500MB | 9/10 |

### 6.3 TinyML Education

| Source | URL | License | Format | Quality |
|--------|-----|---------|--------|---------|
| **UNIFEI-IESTI01-TinyML** | github.com/Mjrovai/UNIFEI-IESTI01-TinyML | Free | Full university course | 9/10 |
| **awesome-tinyml** | github.com/umitkacar/awesome-tinyml | Free | Curated resources | 8/10 |
| **SiliconWit/edge-ai-tinyml** | github.com/SiliconWit/edge-ai-tinyml | Free | Hands-on course | 8/10 |

---

## 7. POWER ELECTRONICS

### 7.1 Solar / MPPT

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **LibreSolar mppt-2420-lc** | github.com/LibreSolar/mppt-2420-lc | ~200+ | CERN-OHL-W | KiCad + firmware | ~30MB | 10/10 |
| **LibreSolar mppt-2420-hc** | github.com/LibreSolar/mppt-2420-hc | ~100+ | CERN-OHL-W | KiCad + firmware | ~30MB | 10/10 |
| **fugu-mppt-firmware** | github.com/fl4p/fugu-mppt-firmware | ~500+ | GPL-3.0 | ESP32 MPPT firmware | ~20MB | 8/10 |

### 7.2 Motor Control (FOC/BLDC)

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **SimpleFOC (Arduino-FOC)** | github.com/simplefoc/Arduino-FOC | ~2k+ | MIT | Arduino FOC library | ~20MB | 10/10 |
| **ODrive (v3.5 open)** | github.com/odriverobotics/ODrive | ~3k+ | MIT* | STM32 motor control | ~100MB | 9/10 |
| **ODriveHardware** | github.com/odriverobotics/ODriveHardware | ~1k+ | CC-BY-SA | KiCad schematics | ~50MB | 9/10 |
| **EasyController3** | github.com/pgrady3/EasyController3 | ~200+ | MIT | Simple BLDC controller | ~10MB | 7/10 |

### 7.3 Battery BMS

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **LibreSolar bms-c1** | github.com/LibreSolar/bms-c1 | ~100+ | CERN-OHL-W | 16s/100A BMS KiCad | ~20MB | 10/10 |
| **LibreSolar bms-firmware** | github.com/LibreSolar/bms-firmware | ~200+ | Apache-2.0 | Zephyr-based BMS firmware | ~30MB | 10/10 |
| **bms-to-inverter** | github.com/ai-republic/bms-to-inverter | ~500+ | Apache-2.0 | BMS<->inverter bridge | ~20MB | 8/10 |

### 7.4 IEEE DataPort

| Source | URL | License | Format | Quality |
|--------|-----|---------|--------|---------|
| **SiC-MOSFET/Si-IGBT Dataset** | ieee-dataport.org | CC-BY-4.0 | Component specs + pricing | 8/10 |
| **Power Electronics Modeling** | ieee-dataport.org | Various | Matlab state-space models | 7/10 |

---

## 8. EMC / RF

### 8.1 SDR Projects

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **gr-lora_sdr (EPFL)** | github.com/tapparelj/gr-lora_sdr | ~500+ | GPL-3.0 | GNU Radio LoRa SDR | ~50MB | 10/10 |
| **gr-lora (rpp0)** | github.com/rpp0/gr-lora | ~700+ | GPL-3.0 | GNU Radio LoRa receiver | ~20MB | 9/10 |
| **gr-osmosdr** | github.com/gqrx-sdr/gr-osmosdr | ~500+ | GPL-3.0 | Multi-hardware SDR block | ~10MB | 8/10 |
| **awesome-gnuradio** | github.com/ysk256/awesome-gnuradio | ~200+ | Free | SDR resources list | ~1MB | 8/10 |
| **sdr-examples** | github.com/argilo/sdr-examples | ~100+ | GPL-3.0 | GNU Radio flow graphs | ~5MB | 7/10 |

### 8.2 LoRa/LoRaWAN Hardware

| Source | URL | Stars | License | Format | Size | Quality |
|--------|-----|-------|---------|--------|------|---------|
| **Lora-net (Semtech)** | github.com/Lora-net | ~1k+ (various) | BSD-3 | Reference firmware | ~200MB | 10/10 |
| **Meshtastic** | github.com/meshtastic | ~5k+ | GPL-3.0 | Complete mesh firmware | ~200MB | 9/10 |
| **Dragino LoRa** | github.com/dragino/Lora | ~300+ | Various | HW+SW source | ~100MB | 8/10 |
| **Olimex LoRa868** | olimex.com/Products/IoT/LoRa/LoRa868 | - | CERN-OHL | KiCad + SX1276 | ~20MB | 8/10 |

### 8.3 Antenna Design

- **NEC2 antenna models**: Public domain antenna simulation files (thousands available)
- **RF calculator tools**: Various GitHub repos for impedance matching, filter design
- **Qucs-S**: Open source circuit simulator with RF capabilities (ra3xdh.github.io)

---

## 9. DATASHEETS / COMPONENTS

### 9.1 Component Databases & Tools

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **Part-DB** | docs.part-db.de | AGPL-3.0 | Component management (LCSC, Mouser, DigiKey APIs) | ~50MB | 9/10 |
| **PartPilot** | github.com/PartPilotLab/PartPilot | GPL-3.0 | LCSC integration, barcode scanning | ~20MB | 8/10 |
| **KiCAD-Part-Search** | github.com/ivixiz/KiCAD-Part-Search | MIT | KiCad plugin (LCSC, RS, Farnell) | ~5MB | 8/10 |
| **Octopart** | octopart.com | API access | Component search API | Unlimited | 9/10 |

### 9.2 Datasheet Parsing Tools

| Source | URL | Stars | License | Format | Quality |
|--------|-----|-------|---------|--------|---------|
| **MinerU** | github.com/opendatalab/MinerU | ~30k+ | AGPL-3.0 | PDF->Markdown/JSON | 10/10 |
| **PDF-Extract-Kit** | github.com/opendatalab/PDF-Extract-Kit | ~5k+ | Apache-2.0 | Layout + OCR + tables | 9/10 |
| **OCRmyPDF** | github.com/ocrmypdf/OCRmyPDF | ~14k+ | MPL-2.0 | OCR layer for PDFs | 9/10 |

**Strategy**: Use MinerU/PDF-Extract-Kit to bulk-convert datasheets from manufacturer sites into structured text.

### 9.3 Kaggle Datasets

| Source | URL | Format | Size | Quality |
|--------|-----|--------|------|---------|
| **Electronic Components** | kaggle.com/datasets/aryaminus/electronic-components | Images | ~1GB | 7/10 |
| **PCB-AoI** | kaggle.com/datasets/kubeedgeianvs/pcb-aoi | PCB inspection images | ~5GB | 8/10 |
| **SolDef_AI** | kaggle.com/datasets/mauriziocalabrese/soldef-ai-pcb-dataset-for-defect-detection | Defect images | ~2GB | 8/10 |
| **Hand-drawn Schematics** | kaggle.com/datasets/moodrammer/handdrawn-circuit-schematic-components | Sketch images | ~500MB | 7/10 |
| **PCB Component Detection** | kaggle.com/datasets/aryanstein/pcb-component-detection-consolidated-dataset | Detection images | ~3GB | 8/10 |

---

## 10. CAD / MECHANICAL

### 10.1 FreeCAD

| Source | URL | Stars | License | Format | Quality |
|--------|-----|-------|---------|--------|---------|
| **FreeCAD main repo** | github.com/FreeCAD/FreeCAD | ~22k+ | LGPL-2.0 | Python + C++ + examples | 10/10 |
| **ParametricEnclosureBase** | github.com/brodiefairhall/ParametricEnclosureBase | ~50+ | MIT | FreeCAD parametric enclosure | 7/10 |

### 10.2 OpenSCAD

| Source | URL | Stars | License | Format | Quality |
|--------|-----|-------|---------|--------|---------|
| **awesome-openscad** | github.com/elasticdotventures/awesome-openscad | ~200+ | Free | Curated project list | 8/10 |
| **BOSL2 library** | github.com/BelfrySCAD/BOSL2 | ~700+ | BSD-2 | Parametric OpenSCAD library | 9/10 |
| **NopSCADlib** | github.com/nophead/NopSCADlib | ~1k+ | GPL-3.0 | Vitamins + printed parts | 9/10 |
| **OpenSCAD-DIN43880_enclosure** | github.com/baradhili/OpenSCAD-DIN43880_enclosure | ~50+ | GPL-3.0 | DIN rail enclosure | 7/10 |
| **project_box** | github.com/gregmarra/project_box | ~100+ | MIT | Parametric project box | 7/10 |

### 10.3 3D Printable Electronics Enclosures

- **Thingiverse** / **Printables**: Thousands of electronics enclosures (search "electronics enclosure", "Raspberry Pi case", "Arduino case")
- **GrabCAD**: Engineering-grade enclosure models
- **Conversion**: Download .scad files (code-based, directly parseable) or STL+metadata

---

## CROSS-CUTTING: Q&A DATASETS

### StackExchange Dumps

| Source | URL | License | Format | Size | Quality |
|--------|-----|---------|--------|------|---------|
| **electronics.stackexchange.com** | archive.org/details/stack-exchange-data-dump-2023-09-12 | CC-BY-SA-3.0 | XML dump (Q&A) | ~512MB | 10/10 |
| **bshada/electronics.stackexchange.com** (HF) | huggingface.co/datasets/bshada/electronics.stackexchange.com | CC-BY-SA-3.0 | Pre-processed JSON | ~200MB | 9/10 |
| **EleutherAI/stackexchange-dataset** | github.com/EleutherAI/stackexchange-dataset | MIT (tool) | Python processor for dumps | Tool only | 9/10 |

**This is arguably the single most valuable Q&A source for electronics AI training.**

### Reddit Archives (Pushshift)

| Subreddit | Size Est. | Quality | Notes |
|-----------|-----------|---------|-------|
| r/electronics | ~500MB | 8/10 | General electronics |
| r/AskElectronics | ~1GB | 9/10 | Q&A format, very valuable |
| r/embedded | ~300MB | 8/10 | Firmware/MCU focused |
| r/FPGA | ~200MB | 8/10 | FPGA/HDL focused |
| r/PCBDesign | ~100MB | 7/10 | PCB layout tips |
| r/arduino | ~2GB | 7/10 | Beginner-heavy but large |
| r/esp32 | ~500MB | 8/10 | ESP32 ecosystem |
| r/rfelectronics | ~100MB | 8/10 | RF/EMC niche |
| r/KiCad | ~100MB | 8/10 | KiCad specific |

- **Access**: Academic Torrents (academictorrents.com), filtered by subreddit
- **License**: Reddit TOS (research use)
- **Format**: NDJSON (zstandard compressed)

---

## PRIORITY RANKING FOR TRAINING

### Tier 1 (Must-have, high quality, real data)

1. **The Stack v2** (assembly/C/Verilog/VHDL subsets) - Massive, permissive, pre-cleaned
2. **electronics.stackexchange.com dump** - 500MB+ real Q&A, CC-BY-SA
3. **bshada/open-schematics** - 84k real KiCad schematics
4. **ESP-IDF + STM32Cube + Zephyr examples** - Official, production-quality firmware
5. **shailja/Verilog_GitHub + PyraNet-Verilog** - Real Verilog from GitHub
6. **ngspice regression tests + LTspice demos** - Real analog circuits
7. **CircuitNet** - Real chip design data
8. **LibreSolar full ecosystem** - Complete open hardware (KiCad + firmware)
9. **PicoRV32 + VexRiscv + learn-fpga** - Real RISC-V implementations
10. **SimpleFOC + ODrive** - Real motor control code

### Tier 2 (Valuable supplements)

11. Reddit archives (r/AskElectronics, r/embedded, r/FPGA)
12. fabriziotappero/ip-cores (OpenCores archive)
13. MAX78000 ai8x-training (edge AI)
14. FreeRTOS demos + Arduino ecosystem
15. Edge Impulse datasets
16. Xilinx/Vivado-Design-Tutorials
17. TI/ADI SPICE models and reference designs
18. Kaggle PCB/component detection datasets
19. xv6 + seL4 kernel ASM
20. gr-lora_sdr + Meshtastic

### Tier 3 (Niche but useful)

21. Nightmare CTF RE course
22. NopSCADlib / BOSL2 OpenSCAD
23. IEEE DataPort power electronics
24. KiCad forum archives
25. OSHWA certified project list
26. Syntiant NDP examples
27. FPGAcademy tutorials
28. Part-DB component data
29. University courses (MIT OCW, Stanford)
30. NVIDIA Nemotron Code (general code with electronics subset)

---

## TOTAL ESTIMATED DATA VOLUME

| Category | Raw Size | After Processing |
|----------|----------|-----------------|
| Code (ASM+C+Verilog+VHDL+Python) | ~50GB | ~20GB |
| Q&A (StackExchange+Reddit+Forums) | ~5GB | ~2GB |
| Schematics (KiCad+SPICE+PCB) | ~15GB | ~5GB |
| Documentation (datasheets, tutorials) | ~20GB | ~8GB |
| Datasets (Kaggle+HF+IEEE) | ~200GB | ~50GB |
| **TOTAL** | **~290GB raw** | **~85GB processed** |

---

## CONVERSION PIPELINE RECOMMENDATIONS

1. **Code files**: Extract with tree-sitter parsers, preserve file structure, pair with README/comments
2. **Q&A data**: Use EleutherAI stackexchange-dataset tool, filter by tag, structure as (question, accepted_answer) pairs
3. **KiCad files**: Parse S-expressions directly (text format), extract netlist + component list + design rules
4. **SPICE netlists**: Parse .cir/.spice files, extract topology + component values + simulation results
5. **Datasheets**: Use MinerU for PDF->Markdown, then structure by sections (pinout, electrical specs, application circuits)
6. **Reddit**: Filter by subreddit, keep only posts with >5 upvotes, extract (title+body, top_comment) pairs
7. **Verilog/VHDL**: Extract module-level (description->code) and (code->testbench) pairs
