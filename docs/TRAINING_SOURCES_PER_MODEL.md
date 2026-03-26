# Mascarade Training Data Sources - All 28+ Mini-Models

> Exhaustive real-world training data sources research - March 2026
> For each source: Name, URL, Stars/Size, License, Format, Quality (1-10)

---

## CROSS-CUTTING DATASETS (applicable to multiple models)

### StackExchange Dumps (CC BY-SA 3.0/4.0)
| Source | URL | Size | Format | Applicable Models | Quality |
|--------|-----|------|--------|-------------------|---------|
| electronics.stackexchange.com | https://hf.co/datasets/bshada/electronics.stackexchange.com | 10K-100K entries | JSON | spice, analog, power, emc, embedded, stm32 | 9/10 |
| arduino.stackexchange.com | https://hf.co/datasets/bshada/arduino.stackexchange.com | 10K-100K entries | JSON | embedded, platformio, iot | 8/10 |
| The Pile StackExchange | https://hf.co/datasets/defunct-datasets/the_pile_stack_exchange | 1M-10M entries | Text | ALL (filter by tag) | 8/10 |
| StackExchange Paired (Q&A pairs) | https://hf.co/datasets/lvwerra/stack-exchange-paired | 10M+ entries | Parquet | ALL (filter electronics/EE/embedded tags) | 9/10 |
| StackExchange Title+BestAnswer | https://hf.co/datasets/flax-sentence-embeddings/stackexchange_titlebody_best_voted_answer_jsonl | 1M-10M | JSONL | ALL | 8/10 |
| StackExchange Full XML Dump | https://hf.co/datasets/flax-sentence-embeddings/stackexchange_xml | GB-scale | XML | ALL | 9/10 |
| Archive.org SE Data Dump | https://archive.org/details/stackexchange | Multi-GB | 7z/XML | ALL (electronics, arduino, signal processing, iot) | 9/10 |

### BigCode The Stack v2 (Filter by Language)
| Source | URL | Languages | Size | Quality |
|--------|-----|-----------|------|---------|
| The Stack v2 | https://hf.co/datasets/bigcode/the-stack-v2 | C, Assembly, Verilog, VHDL, Python, Makefile | 3B+ files, 600+ langs | 9/10 |
| The Stack v2 (dedup) | https://hf.co/datasets/bigcode/the-stack-v2-dedup | Filtered subset | Deduplicated | 9/10 |

**Filter languages for**: C (embedded/spice/dsp), Assembly (asm-*), Verilog/VHDL (verilog), Python (kicad/freecad), Makefile/CMake (platformio/embedded)

### Arduino Datasets (HuggingFace)
| Source | URL | Size | Format | Quality |
|--------|-----|------|--------|---------|
| Arduino Docs | https://hf.co/datasets/gavmac00/arduino-docs | 10K-100K | JSON | 7/10 |
| Arduino Code Dataset (467MB binary) | https://hf.co/datasets/g4lihru/arduino-dataset | 100M-1B tokens | Binary | 7/10 |
| Arduino Programming Dataset | https://hf.co/datasets/suneeldk/arduino-code-dataset | <1K | JSON | 6/10 |
| Arduino-1000 | https://hf.co/datasets/Telles1974/Arduino-1000 | <1K | Parquet | 5/10 |

---

## ELECTRONICS CORE (14 models)

---

### 1. mascarade-spice

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | SPICEPilot (benchmark dataset) | https://github.com/acadlab/spicepilot | ~50 | MIT | SPICE netlists + Python | ~500 examples | 9/10 |
| 2 | PySpice (Python-ngspice interface) | https://github.com/PySpice-org/PySpice | ~600 | GPL-3.0 | Python + SPICE | 100+ examples | 8/10 |
| 3 | KiCad-Simulations (ngspice) | https://github.com/labtroll/KiCad-Simulations | 67 | N/A | KiCad + ngspice | 50+ circuits | 7/10 |
| 4 | SkyWater PDK SPICE models | https://github.com/google/skywater-pdk-libs-sky130_fd_pr_reram | 44 | Apache-2.0 | SPICE models | Process library | 8/10 |
| 5 | opensrc_analog (xschem+ngspice) | https://github.com/eescottie/opensrc_analog | 15 | MIT | xschem + ngspice | Analog examples | 7/10 |
| 6 | ngspice-examples | https://github.com/danielrioslinares/ngspice-examples | 4 | GPL-3.0 | ngspice netlists | ~20 circuits | 6/10 |
| 7 | Analog Devices LTspice Demo Circuits | https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator/lt-spice-demo-circuits.html | N/A | Proprietary (free) | LTspice .asc | 1000+ circuits | 9/10 |
| 8 | ngspice built-in examples | https://github.com/ngspice/ngspice (examples/ dir) | ~300 | BSD | SPICE netlists | 100+ | 8/10 |
| 9 | ngspice-cmos (CMOS circuits) | https://github.com/Teddy-van-Jerry/ngspice-cmos | ~10 | N/A | ngspice | CMOS gates | 6/10 |

**Also scrape**: electronics.stackexchange.com filtered for [spice], [ltspice], [ngspice], [simulation] tags

---

### 2. mascarade-kicad

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | KiCad Official Examples | https://gitlab.com/kicad/kicad/-/tree/master/demos | N/A | GPL-3.0 | .kicad_sch/.kicad_pcb | 20+ projects | 9/10 |
| 2 | SparkFun KiCad Libraries | https://github.com/sparkfun/SparkFun-KiCad-Libraries | ~200 | CC-BY-4.0 | KiCad libs | Thousands of parts | 9/10 |
| 3 | OLIMEX KiCad Libraries + Projects | https://github.com/OLIMEX/KiCAD | ~100 | OSHW | KiCad | Libs + projects | 8/10 |
| 4 | OLIMEX ESP32-DevKit-LiPo | https://github.com/OLIMEX/ESP32-DevKit-LiPo | ~50 | OSHW | KiCad | Full board | 8/10 |
| 5 | Adafruit PCB Design Files (Eagle, importable) | https://github.com/adafruit (500+ -PCB repos) | Varies | OSHW | Eagle/KiCad | 500+ boards | 9/10 |
| 6 | KiKit (KiCad automation) | https://github.com/yaqwsx/KiKit | ~800 | MIT | Python + KiCad | Panelization tool | 8/10 |
| 7 | kicad-automation-scripts | https://github.com/productize/kicad-automation-scripts | ~200 | N/A | Python | Automation scripts | 7/10 |
| 8 | KiCad Python API (official) | https://github.com/KiCad/kicad-python | N/A | GPL | Python | API examples | 8/10 |
| 9 | kicad-action-scripts (plugins) | https://github.com/jsreynaud/kicad-action-scripts | ~100 | N/A | Python | Via stitching, etc. | 7/10 |
| 10 | KiCad forum (forum.kicad.info) | https://forum.kicad.info/ | N/A | CC-BY-SA | HTML (scrape) | 100K+ posts | 8/10 |
| 11 | OSHWA Certified Projects List | https://certification.oshwa.org/list.html | N/A | Various OSHW | Mixed | 2000+ certified | 7/10 |

---

### 3. mascarade-emc

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | TI EMC Design Guide (SZZA009) | https://www.ti.com/lit/an/szza009/szza009.pdf | N/A | Free | PDF | 30+ pages | 9/10 |
| 2 | NXP AN2321 Board-Level EMC | https://www.nxp.com/docs/en/application-note/AN2321.pdf | N/A | Free | PDF | 40+ pages | 9/10 |
| 3 | Microchip AN2587 EMI/EMC/EFT/ESD | https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ApplicationNotes/ApplicationNotes/00002587A.pdf | N/A | Free | PDF | Comprehensive | 8/10 |
| 4 | Silicon Labs AN895 ESD Protection | https://www.silabs.com/documents/public/application-notes/AN895.pdf | N/A | Free | PDF | IEC 61000-4-2 | 8/10 |
| 5 | LearnEMC.com PCB Layout for EMC | https://learnemc.com/pcb-layout | N/A | Free | HTML | Tutorial series | 8/10 |
| 6 | Academy of EMC Design Guidelines | https://www.academyofemc.com/emc-design-guidelines | N/A | Free | HTML | Guidelines collection | 7/10 |
| 7 | JLCPCB DFM/EMC PCB Rules | https://jlcpcb.com/blog/pcb-design-rules-best-practices | N/A | Free | HTML | 40+ rules | 7/10 |
| 8 | PCB EMC design (Schemalyzer 40+ rules) | https://www.schemalyzer.com/en/blog/pcb-design/basics/pcb-design-rules-every-engineer | N/A | Free | HTML | 40+ guidelines | 7/10 |

**Note**: EMC is heavily standards-based. Scrape publicly available summaries/app notes from TI, NXP, ADI, ST, Infineon, Microchip.

---

### 4. mascarade-power

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | SimpleFOC (Arduino FOC motor control) | https://github.com/simplefoc/Arduino-FOC | 2722 | MIT | C++/Arduino | 16MB repo | 10/10 |
| 2 | ODrive (high-perf motor control) | https://github.com/odriverobotics/ODrive | ~3000 | MIT | C/C++ | Full firmware | 9/10 |
| 3 | Libre Solar MPPT Charge Controllers | https://github.com/LibreSolar/mppt-2420-lc | ~100 | CERN-OHL | KiCad + C | HW + FW | 9/10 |
| 4 | Libre Solar BMS (16s/100A) | https://github.com/LibreSolar | ~50 ea | CERN-OHL | KiCad + C | Multiple boards | 9/10 |
| 5 | diyBMS (DIY Battery Management) | https://github.com/stuartpittaway/diyBMS | ~1500 | N/A | C++/KiCad | Full project | 8/10 |
| 6 | Fugu MPPT Firmware (ESP32) | https://github.com/fl4p/fugu-mppt-firmware | ~200 | N/A | C++/Arduino | MPPT firmware | 8/10 |
| 7 | bms-to-inverter | https://github.com/ai-republic/bms-to-inverter | ~300 | N/A | Java | BMS protocols | 7/10 |
| 8 | LTspice Demo Circuits (power) | https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator/lt-spice-demo-circuits.html | N/A | Free | .asc | 200+ power circuits | 9/10 |
| 9 | TI Power Design Reference Library | https://www.ti.com/tool/POWERSTAGE-DESIGNER | N/A | Free | Mixed | Hundreds of designs | 8/10 |

---

### 5. mascarade-dsp

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | CMSIS-DSP (ARM official) | https://github.com/ARM-software/CMSIS-DSP | ~500 | Apache-2.0 | C | Full library + examples | 10/10 |
| 2 | liquid-dsp | https://github.com/jgaeddert/liquid-dsp | ~2100 | MIT | C | SDR DSP library | 9/10 |
| 3 | DaisySP (Electrosmith) | https://github.com/electro-smith/DaisySP | ~2100 | MIT | C++ | Audio DSP algorithms | 9/10 |
| 4 | JUCE Framework | https://github.com/juce-framework/JUCE | ~6000+ | Dual (GPL/commercial) | C++ | Audio plugin framework | 9/10 |
| 5 | Faust (functional audio DSP) | https://github.com/grame-cncm/faust | ~2500+ | GPL-2.0 | Faust/C++ | DSP language + compiler | 9/10 |
| 6 | CMSIS_5 (full suite) | https://github.com/ARM-software/CMSIS_5 | ~1300 | Apache-2.0 | C/ASM | DSP + NN + Core | 9/10 |
| 7 | STM32 Audio DSP (I2S+EQ+DRC) | GitHub topic: stm32-audio-dsp | Various | Various | C | Real-time audio on STM32 | 7/10 |
| 8 | awesome-musicdsp (curated list) | https://github.com/olilarkin/awesome-musicdsp | ~800 | N/A | Links | Resource collection | 8/10 |

---

### 6. mascarade-ipc

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | JLCPCB Capabilities & DFM Rules | https://jlcpcb.com/capabilities/pcb-capabilities | N/A | Free | HTML | Complete specs | 9/10 |
| 2 | JLCPCB Design Rules Guide | https://jlcpcb.com/blog/pcb-design-rules-best-practices | N/A | Free | HTML | 30+ rules | 8/10 |
| 3 | JLCPCB IPC Standards Guide | https://jlcpcb.com/blog/ipc-standards-to-optimize-pcb-layout | N/A | Free | HTML | IPC-2221/7351 | 8/10 |
| 4 | Schemalyzer 40+ PCB Design Rules | https://www.schemalyzer.com/en/blog/pcb-design/basics/pcb-design-rules-every-engineer | N/A | Free | HTML | Comprehensive | 8/10 |
| 5 | PCBWay DFM Guidelines | https://www.pcbway.com/blog/PCB_Design_Layout/ | N/A | Free | HTML | Multiple articles | 7/10 |
| 6 | Sierra Circuits DFM Issues | https://www.protoexpress.com/blog/dfm-issues-pcb-manufacturing/ | N/A | Free | HTML | Manufacturing guide | 7/10 |
| 7 | KiCad DRC Rule Collections | KiCad built-in + JLCPCB plugin | N/A | GPL | KiCad DRC | Rule files | 7/10 |
| 8 | Wevolver IPC Standards Guide | https://www.wevolver.com/article/mastering-ipc-standards-the-definitive-guide-for-electronics-engineers-and-pcb-designers | N/A | Free | HTML | Definitive guide | 8/10 |

**Strategy**: Scrape manufacturer DFM pages (JLCPCB, PCBWay, OSHPark, Aisler) + IPC public summaries. Convert to Q&A pairs.

---

### 7. mascarade-analog

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | OPAMP-Generator (32 topologies) | https://github.com/jialinlu/OPAMP-Generator | ~50 | N/A | SPICE netlists | 32 op-amp circuits | 8/10 |
| 2 | analog-design (amplifier+VCO) | https://github.com/asterane/analog-design | ~10 | N/A | Schematics + docs | Audio amp + oscillator | 7/10 |
| 3 | LTspice Demo Circuits (amplifiers) | https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator/lt-spice-demo-circuits.html | N/A | Free | .asc | Hundreds | 9/10 |
| 4 | Analog Devices Reference Circuits | https://www.analog.com/en/resources.html | N/A | Free | PDF/Schematics | Thousands | 9/10 |
| 5 | TI Precision Labs (op-amp tutorials) | https://training.ti.com/ti-precision-labs-op-amps | N/A | Free | Video + docs | 50+ modules | 9/10 |
| 6 | Electronics-Tutorials.ws (filters) | https://www.electronics-tutorials.ws/filter/ | N/A | Free | HTML | Active filter theory | 7/10 |
| 7 | Electronics-Notes.com (op-amp) | https://www.electronics-notes.com/articles/analogue_circuits/operational-amplifier-op-amp/ | N/A | Free | HTML | Complete op-amp guide | 7/10 |
| 8 | GitHub topic: analog-circuit-design | https://github.com/topics/analog-circuit-design | Various | Various | Mixed | Community projects | 6/10 |
| 9 | electronics.stackexchange.com [op-amp] | Filter from SE dump | CC-BY-SA | Q&A | Thousands of Q&A | 8/10 |

---

### 8. mascarade-embedded

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ESP-IDF Official Examples | https://github.com/espressif/esp-idf/tree/master/examples | ~14000 (repo) | Apache-2.0 | C | 200+ examples | 10/10 |
| 2 | Zephyr RTOS (samples/) | https://github.com/zephyrproject-rtos/zephyr | ~12000 | Apache-2.0 | C | 500+ samples | 10/10 |
| 3 | FreeRTOS Demos | https://github.com/FreeRTOS/FreeRTOS | ~5500 | MIT | C | Multi-platform demos | 9/10 |
| 4 | STM32CubeF4 HAL Examples | https://github.com/STMicroelectronics/STM32CubeF4 | ~800 | BSD-3 | C | Full peripheral demos | 9/10 |
| 5 | STM32CubeH7 HAL Examples | https://github.com/STMicroelectronics/STM32CubeH7 | ~400 | BSD-3 | C | Advanced peripherals | 9/10 |
| 6 | Mbed OS Examples | https://github.com/ARMmbed/mbed-os | ~4700 | Apache-2.0 | C++ | RTOS + HAL | 8/10 |
| 7 | bare-metal-programming-guide | https://github.com/cpq/bare-metal-programming-guide | ~3000 | MIT | C | Bare-metal ARM guide | 9/10 |
| 8 | FreeRTOS-STM32-HAL-Examples | https://github.com/kowalski100/FreeRTOS-STM32-HAL-Examples | ~200 | N/A | C | STM32F4 + FreeRTOS | 7/10 |
| 9 | Arduino Core Libraries | https://github.com/arduino/ArduinoCore-avr + samd + mbed | ~1000+ | LGPL | C++ | Core implementations | 8/10 |
| 10 | Awesome Embedded Rust | https://github.com/rust-embedded/awesome-embedded-rust | ~6000 | N/A | Links | Resource collection | 8/10 |

---

### 9. mascarade-platformio

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | Tasmota | https://github.com/arendst/Tasmota | ~22000 | GPL-3.0 | C++/PlatformIO | Massive codebase | 10/10 |
| 2 | ESPHome | https://github.com/esphome/esphome | ~8500 | MIT/Apache | Python/C++/YAML | Smart home FW | 9/10 |
| 3 | Marlin Firmware | https://github.com/MarlinFirmware/Marlin | ~16000 | GPL-3.0 | C++/PlatformIO | 3D printer FW | 9/10 |
| 4 | platformio-examples (official) | https://github.com/platformio/platformio-examples | ~400 | Apache-2.0 | C/C++ | Multi-platform | 8/10 |
| 5 | PlatformIO Documentation/Tutorials | https://docs.platformio.org/en/stable/tutorials/ | N/A | Free | HTML | Complete tutorials | 8/10 |
| 6 | WLED (LED controller) | https://github.com/Aircoookie/WLED | ~15000 | MIT | C++/PlatformIO | LED control FW | 8/10 |
| 7 | ESPEasy | https://github.com/letscontrolit/ESPEasy | ~3000 | GPL | C++/PlatformIO | IoT firmware | 7/10 |

---

### 10. mascarade-freecad

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | FreeCAD Official Macro Repository | https://github.com/FreeCAD/FreeCAD-macros | ~200 | LGPL | Python | 100+ macros | 9/10 |
| 2 | FreeCAD Sketches Dataset (3000 files) | https://hf.co/datasets/Yas1n/FreeCAD_Sketches | 70 DL | CC-BY-4.0 | Python | 3000 parametric sketches | 9/10 |
| 3 | FreeCAD Sketches + Images | https://hf.co/datasets/Yas1n/FreeCAD_Sketches_Pics | 27 DL | CC-BY-4.0 | Python + PNG | 1000 sketch+image pairs | 8/10 |
| 4 | BOSL2 (OpenSCAD library) | https://github.com/BelfrySCAD/BOSL2 | ~800 | BSD | OpenSCAD | Massive parts library | 9/10 |
| 5 | NopSCADlib | https://github.com/nophead/NopSCADlib | ~1000 | GPL-3.0 | OpenSCAD | Parts + BOM framework | 9/10 |
| 6 | FreeCAD-Python (automation scripts) | https://github.com/paulcobbaut/FreeCAD-Python | ~50 | N/A | Python | Scripting examples | 7/10 |
| 7 | GPT4FreeCAD (AI + FreeCAD) | https://github.com/revhappy/GPT4FreeCAD | ~50 | N/A | Python | AI script generation | 7/10 |
| 8 | awesome-openscad | https://github.com/elasticdotventures/awesome-openscad | ~100 | N/A | Links | Curated collection | 7/10 |

---

### 11. mascarade-iot

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ESP-IDF Examples (WiFi/BLE/MQTT) | https://github.com/espressif/esp-idf/tree/master/examples | ~14000 | Apache-2.0 | C | 200+ examples | 10/10 |
| 2 | ESPHome Configs/Components | https://github.com/esphome/esphome | ~8500 | MIT | YAML/C++ | IoT configs | 9/10 |
| 3 | AWS IoT Embedded C SDK | https://github.com/aws/aws-iot-device-sdk-embedded-C | ~1000 | MIT | C | MQTT/HTTP/Shadow | 9/10 |
| 4 | Azure IoT SDK C | https://github.com/Azure/azure-iot-sdk-c | ~600 | MIT | C99 | IoT Hub client | 8/10 |
| 5 | Tasmota (MQTT IoT) | https://github.com/arendst/Tasmota | ~22000 | GPL-3.0 | C++ | Full IoT firmware | 9/10 |
| 6 | awesome-lora-lorawan | https://github.com/mcicolella/awesome-lora-lorawan | ~300 | N/A | Links | LoRa resources | 7/10 |
| 7 | TheThingsNetwork lorawan-devices | https://github.com/TheThingsNetwork/lorawan-devices | ~800 | Apache-2.0 | JSON/YAML | Device profiles | 7/10 |
| 8 | ChirpStack (LoRaWAN server) | https://github.com/chirpstack | ~4000+ | MIT | Go/Rust | LoRaWAN stack | 8/10 |

---

### 12. mascarade-stm32

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | stm32-rs (Rust PACs for all STM32) | https://github.com/stm32-rs/stm32-rs | ~1200 | MIT/Apache | Rust/SVD | All STM32 families | 10/10 |
| 2 | stm32f4xx-hal (Rust HAL) | https://github.com/stm32-rs/stm32f4xx-hal | ~700 | MIT/Apache | Rust | Full peripheral HAL | 9/10 |
| 3 | stm32f1xx-hal (Rust HAL) | https://github.com/stm32-rs/stm32f1xx-hal | ~500 | MIT/Apache | Rust | F1 HAL | 9/10 |
| 4 | stm32-eth (Ethernet in Rust) | https://github.com/stm32-rs/stm32-eth | ~100 | MIT | Rust | Ethernet driver | 8/10 |
| 5 | STM32CubeF4 (ST official) | https://github.com/STMicroelectronics/STM32CubeF4 | ~800 | BSD-3 | C | USB/CAN/ETH/all periph | 9/10 |
| 6 | STM32CubeH7 (ST official) | https://github.com/STMicroelectronics/STM32CubeH7 | ~400 | BSD-3 | C | Advanced peripherals | 9/10 |
| 7 | STM32 bare-metal blog | https://vivonomicon.com/category/stm32_baremetal_examples/ | N/A | Free | HTML + C | Tutorial series | 8/10 |
| 8 | STM32 HAL Ethernet BareMetal | https://github.com/stm32-hotspot/CKB-STM32-HAL-Ethernet-BareMetal | ~50 | N/A | C | H5/H7 Ethernet | 7/10 |

---

### 13. mascarade-verilog

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | PicoRV32 (RISC-V CPU) | https://github.com/YosysHQ/picorv32 | ~3000 | ISC | Verilog | RISC-V core + SoC | 10/10 |
| 2 | VexRiscv (SpinalHDL RISC-V) | https://github.com/SpinalHDL/VexRiscv | ~2500 | MIT | SpinalHDL/Verilog | Configurable core | 9/10 |
| 3 | cocotb (Python verification) | https://github.com/cocotb/cocotb | ~2100 | BSD | Python | Testbench framework | 9/10 |
| 4 | DarkRISCV | https://github.com/darklife/darkriscv | ~2000 | BSD | Verilog | One-night RISC-V | 8/10 |
| 5 | Vivado Design Tutorials (Xilinx) | https://github.com/Xilinx/Vivado-Design-Tutorials | ~300 | N/A | Verilog/VHDL | Official tutorials | 9/10 |
| 6 | Nandland FPGA tutorials | https://github.com/nandland/getting-started-with-fpgas | ~400 | N/A | Verilog/VHDL | Book code + examples | 9/10 |
| 7 | openFPGALoader | https://github.com/trabucayre/openFPGALoader | ~1000 | Apache | C++ | Universal FPGA loader | 7/10 |
| 8 | Analog Devices HDL | https://github.com/analogdevicesinc/hdl | ~600 | Mixed | Verilog/VHDL | Reference designs | 9/10 |
| 9 | NEORV32 (RISC-V SoC on OpenCores) | https://opencores.org/projects/neorv32 | N/A | BSD | VHDL | Full SoC | 8/10 |
| **HuggingFace Datasets** | | | | | | | |
| 10 | Verilog_GitHub (VeriGen) | https://hf.co/datasets/shailja/Verilog_GitHub | 337 DL, 30 likes | MIT | CSV | 100K-1M entries | 9/10 |
| 11 | Verilog_data | https://hf.co/datasets/wangxinze/Verilog_data | 44 DL | Apache-2.0 | CSV | 100K-1M | 8/10 |
| 12 | verilog-dataset-v2 | https://hf.co/datasets/emilgoh/verilog-dataset-v2 | 68 DL | Apache-2.0 | CSV | 10K-100K | 7/10 |
| 13 | verilog-dataset-v3 | https://hf.co/datasets/emilgoh/verilog-dataset-v3 | 18 DL | Apache-2.0 | CSV | 10K-100K | 7/10 |
| 14 | Verilogdata4pretrainCODET5 | https://hf.co/datasets/JayZhang1/Verilogdata4pretrainCODET5 | 54 DL | N/A | CSV | 100K-1M | 7/10 |

---

### 14. mascarade-missing (RF, safety, battery, thermal, eurorack, guitar FX)

#### RF / SDR
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | HackRF | https://github.com/greatscottgadgets/hackrf | ~6500 | GPL-2.0 | C/firmware | SDR platform | 9/10 |
| 2 | GNURadio | https://github.com/gnuradio/gnuradio | ~5000 | GPL-3.0 | C++/Python | SDR framework | 10/10 |
| 3 | gr-lora (LoRa GNU Radio) | https://github.com/rpp0/gr-lora | ~200 | MIT | C++/Python | LoRa SDR | 8/10 |
| 4 | gr-lora_sdr (EPFL LoRa) | https://github.com/tapparelj/gr-lora_sdr | ~300 | N/A | C++/Python | Full transceiver | 9/10 |
| 5 | gqrx (SDR receiver) | https://github.com/gqrx-sdr/gqrx | ~3000 | GPL | C++ | SDR receiver app | 8/10 |

#### Eurorack / Audio Synthesis
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 6 | Mutable Instruments (full catalog) | https://github.com/pichenettes/eurorack | ~3000 | MIT/GPL | C++/STM32 | 15+ module firmwares | 10/10 |
| 7 | eurorack-awesome (curated list) | https://github.com/newdigate/eurorack-awesome | ~100 | N/A | Links | DIY eurorack resources | 7/10 |
| 8 | MI Alternative Firmware Catalogue | https://github.com/timchurches/Mutable-Instruments-alternative-firmware-catalogue | ~200 | N/A | Links | Alt firmwares collection | 7/10 |

#### Guitar FX / Pedals
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 9 | pedalSHIELD (Electrosmash) | https://github.com/ElectroSmash/pedalshield | ~300 | N/A | C/Arduino/KiCad | Pedal platform | 9/10 |
| 10 | Electrosmash (full site) | https://www.electrosmash.com/ | N/A | Free | HTML + schematics | Pedal analyses | 9/10 |

#### Battery / BMS
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 11 | diyBMS | https://github.com/stuartpittaway/diyBMS | ~1500 | N/A | C++/KiCad | Full BMS project | 8/10 |
| 12 | Libre Solar BMS | https://github.com/LibreSolar | Various | CERN-OHL | KiCad + C | Multiple BMS boards | 9/10 |

#### Thermal
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 13 | PACT (Parallel Compact Thermal Sim) | https://github.com/peaclab/PACT | ~50 | N/A | Python | Thermal solver | 7/10 |
| 14 | Antmicro Open Source Thermal Sim | https://antmicro.com/blog/2025/03/open-source-thermal-simulation-analysis-and-visualization | N/A | Open | KiCad+ElmerFEM | PCB thermal | 8/10 |
| 15 | OpenFOAM (PCB cooling CFD) | https://www.openfoam.com/ | N/A | GPL | C++ | CFD simulation | 7/10 |

#### Antenna
| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 16 | LoRaWAN-antenna (868MHz design) | https://github.com/vives-projectwerk-2-2020/LoRaWAN-antenna | ~10 | N/A | Eagle + docs | Antenna design | 6/10 |
| 17 | SparkFun IoT Node LoRaWAN | https://github.com/sparkfun/SparkFun_IoT_Node_LoRaWAN | ~30 | OSHW | KiCad | RF board design | 7/10 |

---

## ASM (5 models)

---

### 15. mascarade-asm-arm

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | CMSIS Startup Files (all vendors) | https://github.com/STMicroelectronics/cmsis-core | ~50 | Apache-2.0 | ASM (.s) + C | All STM32 startup | 10/10 |
| 2 | CMSIS_5 (startup + DSP) | https://github.com/ARM-software/CMSIS_5 | ~1300 | Apache-2.0 | ASM/C | Core + DSP + NN | 10/10 |
| 3 | bare-metal-programming-guide | https://github.com/cpq/bare-metal-programming-guide | ~3000 | MIT | C + ASM | ARM bare-metal guide | 9/10 |
| 4 | cortexm/baremetal | https://github.com/cortexm/baremetal | ~50 | N/A | C++/ASM | ARM Cortex-M examples | 7/10 |
| 5 | The Stack v2 (filter: Assembly) | https://hf.co/datasets/bigcode/the-stack-v2 | Massive | Various | ASM | ARM .s files | 8/10 |
| 6 | STM32 vendor startup files (all CubeXX) | https://github.com/STMicroelectronics | Varies | BSD-3 | ASM | .s startup files | 9/10 |

---

### 16. mascarade-asm-avr

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | AVRFreaks Projects Archive | https://github.com/MicrochipTech/avrfreaks-projects | ~100 | Various | ASM/C | Hundreds of projects | 9/10 |
| 2 | AVR Assembly Examples | https://github.com/matthew-macgregor/avr-assembly-examples | ~30 | N/A | ASM (ATmega168p) | Tutorial examples | 8/10 |
| 3 | AVR Programming with Assembly | https://github.com/Dentrax/AVR-Programming-with-Assembly | ~50 | N/A | ASM | Learning guide | 7/10 |
| 4 | AVR BareMetal Firmwares | https://github.com/gkunalupta/AVR_BareMetal_Firmwares | ~20 | N/A | C/ASM | ATmega2560/328 | 7/10 |
| 5 | Baremetal AVR Processors | https://github.com/danaolcott/atmel | ~10 | N/A | C/ASM | Multi-processor | 6/10 |
| 6 | The Stack v2 (filter: AVR Assembly) | https://hf.co/datasets/bigcode/the-stack-v2 | Massive | Various | ASM | AVR .asm files | 8/10 |

---

### 17. mascarade-asm-riscv

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | riscv-tests (ISA test suite) | https://github.com/riscv-software-src/riscv-tests | ~800 | BSD | ASM | Official ISA tests | 10/10 |
| 2 | xv6-riscv (MIT OS course) | https://github.com/mit-pdos/xv6-riscv | ~7000 | MIT | C/ASM | Teaching OS | 10/10 |
| 3 | RISC-V ISA Manual | https://github.com/riscv/riscv-isa-manual | ~3500 | CC-BY-4.0 | LaTeX/docs | Full ISA spec | 9/10 |
| 4 | riscv-bare-metal | https://github.com/s094392/riscv-bare-metal | ~20 | N/A | ASM/C | UART/interrupt/kvmmap | 7/10 |
| 5 | riscv-bareboot | https://github.com/rejunity/riscv-bareboot | ~20 | N/A | ASM | Boot loader education | 7/10 |
| 6 | riscv-asm (assembler) | https://github.com/jbroll/riscv-asm | ~30 | N/A | ASM | rv32/rv64 assembler | 6/10 |
| 7 | RISC-V Guide | https://github.com/mikeroyal/RISC-V-Guide | ~1500 | N/A | Links | Comprehensive guide | 8/10 |
| 8 | riscv/learn (official education) | https://github.com/riscv/learn | ~400 | N/A | Tutorials | Official tutorials | 8/10 |

---

### 18. mascarade-asm-x86

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ecnivs/nasm-os (barebones x86 OS) | https://github.com/ecnivs/nasm-os | ~50 | N/A | NASM | Bootloader + kernel | 7/10 |
| 2 | Learning x86 Assembly with NASM | https://github.com/0xMalCore/Learning-x86-Assembly-with-NASM | ~20 | N/A | NASM | System calls, loops | 6/10 |
| 3 | x86-nasm (simple programs) | https://github.com/7h3w4lk3r/x86-nasm | ~30 | N/A | NASM | Basic programs | 6/10 |
| 4 | x86 Bootloader projects | https://github.com/lukearend/x86-bootloader | ~50 | N/A | NASM | Bootloader tutorial | 7/10 |
| 5 | OSDev Wiki (code examples) | https://wiki.osdev.org/ | N/A | PD/CC | ASM/C | OS development wiki | 9/10 |
| 6 | GitHub topic: x86-64-assembly-nasm | https://github.com/topics/x86-64-assembly-nasm | Various | Various | NASM | Community projects | 7/10 |
| 7 | The Stack v2 (filter: Assembly/NASM) | https://hf.co/datasets/bigcode/the-stack-v2 | Massive | Various | ASM | x86 .asm/.s files | 8/10 |

---

### 19. mascarade-asm-xtensa

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ulptool (ESP32 ULP Arduino) | https://github.com/duff2013/ulptool | ~200 | N/A | ASM/Arduino | ULP coprocessor | 8/10 |
| 2 | micropython-esp32-ulp | https://github.com/micropython/micropython-esp32-ulp | ~100 | MIT | Python/ASM | ULP assembler in uPy | 8/10 |
| 3 | ESP-IDF ULP Examples | https://github.com/espressif/esp-idf/tree/master/examples/system/ulp | N/A | Apache-2.0 | ASM | Official ULP examples | 9/10 |
| 4 | arduino_ulp | https://github.com/cnc4less/arduino_ulp | ~100 | N/A | ASM | ULP for Arduino | 7/10 |
| 5 | ulptool-pio (PlatformIO wrapper) | https://github.com/likeablob/ulptool-pio | ~30 | N/A | ASM/Python | PlatformIO integration | 6/10 |
| 6 | ESP-IoT-Solution ULP guide | https://espressif-docs.readthedocs-hosted.com/projects/espressif-esp-iot-solution/en/latest/low_power_solution/ | N/A | Free | HTML | 24 assembly instructions | 8/10 |

**Note**: Xtensa assembly is niche. The ESP32 ULP uses a simplified instruction set (24 instructions). Combine with ESP-IDF Xtensa-specific startup code and low-level driver implementations.

---

## AI ON-CHIP (9 models)

---

### 20. mascarade-max78000

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ai8x-training (model training) | https://github.com/analogdevicesinc/ai8x-training | ~300 | Apache-2.0 | Python/PyTorch | Training scripts + models | 10/10 |
| 2 | ai8x-synthesis (code generation) | https://github.com/analogdevicesinc/ai8x-synthesis | ~200 | Apache-2.0 | Python/C | Synthesis "izer" tool | 10/10 |
| 3 | MaximAI_Documentation | https://github.com/analogdevicesinc/MaximAI_Documentation | ~100 | N/A | Markdown | Complete documentation | 9/10 |
| 4 | MAX78000 MSDK Examples | https://github.com/analogdevicesinc/msdk | ~200 | Apache-2.0 | C | Drivers + ML examples | 9/10 |
| 5 | ADI Developer Resources | https://developer.analog.com/solutions/max78000 | N/A | Free | Mixed | Official tutorials | 8/10 |

---

### 21. mascarade-syntiant

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | Edge Impulse Syntiant Firmware | https://github.com/edgeimpulse/firmware-syntiant-tinyml | ~50 | Apache-2.0 | C/Arduino | NDP101 firmware | 8/10 |
| 2 | Edge Impulse Expert Projects (Syntiant) | https://github.com/edgeimpulse/expert-projects | ~100 | N/A | Mixed | Audio classification | 8/10 |
| 3 | Arduino Nicla Voice Examples | https://docs.arduino.cc/tutorials/nicla-voice/getting-started-ml | N/A | Free | Arduino/C++ | NDP120 ML audio | 8/10 |
| 4 | Edge Impulse Syntiant Docs | https://docs.edgeimpulse.com/docs/edge-ai-hardware/mcu-+-ai-accelerators/syntiant-tinyml-board | N/A | Free | HTML | Deployment guides | 7/10 |
| 5 | Voice Controlled Power Plug (Nicla Voice) | https://github.com/Jallson/Voice_Controlled_PowerPlug | ~10 | N/A | Arduino | Keyword recognition | 6/10 |

---

### 22. mascarade-ethos-u55

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ARM ML-examples | https://github.com/ARM-software/ML-examples | ~500 | Apache-2.0 | Python/C | Ethos-U pruning/clustering | 9/10 |
| 2 | Ethos-U Vela Compiler | https://review.mlplatform.org/plugins/gitiles/ml/ethos-u/ethos-u-vela | N/A | Apache-2.0 | Python | TFLite-to-NPU compiler | 9/10 |
| 3 | mlek-cmsis-pack-examples | https://github.com/Arm-Examples/mlek-cmsis-pack-examples | ~50 | Apache-2.0 | C | KWS + object detection | 8/10 |
| 4 | Corstone-300 Quickstart | https://github.com/jasonrandrews/corstone-300-quickstart | ~10 | N/A | C | Corstone-300 setup | 7/10 |
| 5 | CMSIS-NN (neural network kernels) | https://github.com/ARM-software/CMSIS-NN | ~300 | Apache-2.0 | C | Optimized NN kernels | 9/10 |
| 6 | ARM ML Developer Guide | https://documentation-service.arm.com (Ethos-U guide) | N/A | Free | PDF | Comprehensive guide | 8/10 |

---

### 23. mascarade-kendryte

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | nncase (deep learning compiler) | https://github.com/kendryte/nncase | ~500 | Apache-2.0 | C++/Python | K210/K230 compiler | 9/10 |
| 2 | CanMV (MicroPython for K210/K230) | https://github.com/kendryte/canmv | ~200 | Apache-2.0 | Python/C | MicroPython + AI | 8/10 |
| 3 | CanMV Examples | https://github.com/kendryte/canmv_examples | ~100 | Apache-2.0 | Python | K210/K230 examples | 8/10 |
| 4 | Sipeed MaixPy examples | https://github.com/sipeed/LicheeDan_K210_examples | ~100 | N/A | Python | K210 demos | 7/10 |
| 5 | Sipeed maix_train (model training) | https://github.com/sipeed/maix_train | ~200 | N/A | Python | MobileNet + YOLOv2 | 8/10 |
| 6 | awesome-k210 | https://github.com/elloza/awesome-k210 | ~100 | N/A | Links | Curated list | 7/10 |

---

### 24. mascarade-nxp-neutron

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | NXP eIQ Apps (i.MX ML) | https://github.com/nxp-imx/eiq-apps-imx | ~50 | BSD-3 | C/Python | ML applications | 8/10 |
| 2 | eIQ Neutron NPU Lab Guides | https://community.nxp.com/t5/MCX-Microcontrollers-Knowledge/eIQ-Neutron-NPU-Lab-Guides/ta-p/1799233 | N/A | Free | HTML | MobileNet + Face Detect | 8/10 |
| 3 | MCUXpresso SDK (ML examples) | https://mcuxpresso.nxp.com | N/A | BSD-3 | C | TFLM + Neutron backend | 8/10 |
| 4 | NXP Application Notes (ML) | https://www.nxp.com/docs/en/application-note/AN14700.pdf | N/A | Free | PDF | RT700 Ethos-U NPU perf | 7/10 |
| 5 | NXP Application Code Hub | https://community.nxp.com/t5/MCX-Microcontrollers-Knowledge/How-to-get-started-with-NPU-and-ML-in-MCX-Microcontrollers/ta-p/1788440 | N/A | Free | HTML | Getting started guide | 7/10 |

---

### 25. mascarade-stm32-ai

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | STM32 AI Model Zoo | https://github.com/STMicroelectronics/stm32ai-modelzoo | ~300 | BSD-3 | Python/C | 36+ model families | 10/10 |
| 2 | STM32 AI Model Zoo Services | https://github.com/STMicroelectronics/stm32ai-modelzoo-services | ~100 | BSD-3 | Python | Training/quantization | 9/10 |
| 3 | STM32AI Overall Offer (entry point) | https://github.com/STMicroelectronics/STM32AI_Overall_Offer | ~200 | N/A | Links | All ST AI repos | 9/10 |
| 4 | X-CUBE-AI (STM32CubeMX plugin) | https://stm32ai.st.com/stm32-cube-ai/ | N/A | ST proprietary | C | NN runtime library | 8/10 |
| 5 | GitHub topic: x-cube-ai | https://github.com/topics/x-cube-ai | Various | Various | C/Python | Community projects | 7/10 |

---

### 26. mascarade-apple-npu

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | MLX (array framework) | https://github.com/ml-explore/mlx | ~18000 | MIT | C++/Python | ML framework | 10/10 |
| 2 | MLX Examples (LoRA, LLMs) | https://github.com/ml-explore/mlx-examples | ~6000 | MIT | Python | Fine-tuning + inference | 10/10 |
| 3 | MLX-LM (LLM fine-tuning) | https://github.com/ml-explore/mlx-lm | ~4000 | MIT | Python | LoRA/QLoRA fine-tuning | 10/10 |
| 4 | coremltools | https://github.com/apple/coremltools | ~4500 | BSD-3 | Python | Model conversion toolkit | 9/10 |
| 5 | Core ML Documentation | https://developer.apple.com/documentation/coreml | N/A | Free | HTML | Apple official docs | 9/10 |
| 6 | Apple ML Research | https://machinelearning.apple.com/ | N/A | Free | HTML | Papers + tools | 8/10 |
| 7 | Foundation Models Framework | https://developer.apple.com/machine-learning/ | N/A | Free | HTML | On-device LLM API | 8/10 |

---

### 27. mascarade-tinyml

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | TFLite Micro | https://github.com/tensorflow/tflite-micro | ~2000 | Apache-2.0 | C++ | ML inference engine | 10/10 |
| 2 | TFLite Micro Arduino Examples | https://github.com/tensorflow/tflite-micro-arduino-examples | ~500 | Apache-2.0 | C++ | Arduino examples | 9/10 |
| 3 | MCUNet (MIT, NeurIPS 2020) | https://github.com/mit-han-lab/mcunet | ~800 | MIT | Python | Tiny deep learning | 9/10 |
| 4 | TinyEngine (MIT, NeurIPS 2022) | https://github.com/mit-han-lab/tinyengine | ~1000 | MIT | C/Python | Inference engine MCU | 9/10 |
| 5 | emlearn | https://github.com/emlearn/emlearn | ~400 | MIT | C99/Python | sklearn -> C99 | 8/10 |
| 6 | emlearn-micropython | https://github.com/emlearn/emlearn-micropython | ~100 | MIT | MicroPython | ML for MicroPython | 7/10 |
| 7 | MLPerf Tiny | https://github.com/mlcommons/tiny | ~500 | Apache-2.0 | C/Python | 4 benchmarks + ref impl | 9/10 |
| 8 | Edge Impulse Courseware | https://github.com/edgeimpulse/courseware-embedded-machine-learning | ~100 | N/A | Mixed | Training materials | 8/10 |
| 9 | Edge Impulse Public Datasets | https://docs.edgeimpulse.com/datasets | N/A | Various | Mixed | Audio/vision/anomaly | 8/10 |
| 10 | tinyml-papers-and-projects | https://github.com/gigwegbe/tinyml-papers-and-projects | ~600 | N/A | Links | Curated collection | 7/10 |

---

### 28. mascarade-esp-ai (NEW)

| # | Source | URL | Stars | License | Format | Size Est. | Quality |
|---|--------|-----|-------|---------|--------|-----------|---------|
| 1 | ESP-DL (deep learning library) | https://github.com/espressif/esp-dl | ~500 | Apache-2.0 | C | ESP AI library | 9/10 |
| 2 | ESP-SR (WakeNet + MultiNet) | https://github.com/espressif/esp-sr | ~800 | Espressif | C | Speech recognition | 9/10 |
| 3 | ESP-WHO (face detection/recognition) | https://github.com/espressif/esp-who | ~1700 | Apache-2.0 | C | Vision AI | 9/10 |
| 4 | esp-tflite-micro | https://github.com/espressif/esp-tflite-micro | ~400 | Apache-2.0 | C++ | TFLite for ESP | 9/10 |
| 5 | ESP-Skainet (voice assistant) | https://github.com/espressif/esp-skainet | ~500 | Espressif | C | Voice assistant framework | 8/10 |
| 6 | Edge Impulse ESP32 Examples | Edge Impulse Studio -> ESP32 deployment | N/A | Various | C | Model deployment | 7/10 |
| 7 | ESP-IDF examples/AI | https://github.com/espressif/esp-idf (examples/) | ~14000 | Apache-2.0 | C | ESP32-P4 AI examples | 8/10 |

---

## SUMMARY STATISTICS

| Category | Models | Total Sources Found | High Quality (8+) | HuggingFace Datasets |
|----------|--------|--------------------|--------------------|---------------------|
| Electronics Core | 14 | 130+ | 85+ | 8 |
| ASM | 5 | 35+ | 20+ | 1 (The Stack v2) |
| AI On-Chip | 9 | 55+ | 40+ | 0 direct (use curated) |
| **TOTAL** | **28** | **220+** | **145+** | **9+** |

## KEY CROSS-MODEL DATASETS TO DOWNLOAD FIRST

1. **electronics.stackexchange.com** (HF) - filters for spice/analog/power/emc/embedded
2. **arduino.stackexchange.com** (HF) - filters for embedded/platformio/iot
3. **The Stack v2** (HF) - filter C, Assembly, Verilog, VHDL, Python, Makefile
4. **Verilog_GitHub** (HF) - direct use for mascarade-verilog
5. **FreeCAD_Sketches** (HF) - direct use for mascarade-freecad
6. **StackExchange Full XML Dump** (archive.org) - filter signal processing, EE, embedded

## RECOMMENDED SCRAPING TARGETS (not yet datasets)

| Target | URL | Format | Priority | Models |
|--------|-----|--------|----------|--------|
| KiCad Forum | forum.kicad.info | Discourse API | HIGH | kicad |
| Electrosmash articles | electrosmash.com | HTML scrape | HIGH | analog, missing |
| LearnEMC.com | learnemc.com | HTML scrape | MEDIUM | emc |
| Electronics-Tutorials.ws | electronics-tutorials.ws | HTML scrape | MEDIUM | analog |
| TI App Notes (public) | ti.com/lit/ | PDF download | HIGH | spice, power, emc, analog |
| ADI App Notes (public) | analog.com/en/resources | PDF download | HIGH | spice, analog |
| OSDev Wiki | wiki.osdev.org | HTML scrape | MEDIUM | asm-x86 |
| Nandland tutorials | nandland.com | HTML scrape | MEDIUM | verilog |
| PlatformIO docs | docs.platformio.org | HTML scrape | MEDIUM | platformio |

---

*Research conducted March 2026. Star counts are approximate and may have changed since last check.*
