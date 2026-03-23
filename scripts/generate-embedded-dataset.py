"""Generate embedded systems dataset: PlatformIO, STM32, ESP-IDF, Arduino, RTOS, etc."""

import json
import time
import os
import httpx
import random

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
OUTPUT = "finetune/datasets/embedded_systems_full.jsonl"

CATEGORIES = [
    {
        "name": "PlatformIO Configuration",
        "count": 200,
        "topics": [
            "Write platformio.ini for {board} with {framework} and {libs}",
            "PlatformIO multi-environment config for {board1} and {board2}",
            "PlatformIO library dependency management with lib_deps",
            "Custom board definition in PlatformIO for {mcu}",
            "PlatformIO upload protocol configuration for {method}",
            "Build flags and compiler options in platformio.ini for {optimization}",
            "PlatformIO unit testing setup for {board}",
            "Monitor filters and serial configuration in PlatformIO",
            "PlatformIO CI/CD integration with GitHub Actions",
            "Migrating Arduino IDE project to PlatformIO",
        ],
    },
    {
        "name": "STM32 HAL/LL Programming",
        "count": 400,
        "topics": [
            "Configure {peripheral} on {stm32} using STM32 HAL",
            "STM32 {peripheral} DMA transfer configuration",
            "STM32 low-power modes: {mode} with wake-up from {source}",
            "STM32 clock tree configuration: HSE {freq}MHz, PLL to {sysclk}MHz",
            "STM32 ADC {mode} mode with {channels} channels and DMA",
            "STM32 timer PWM generation at {freq} with {resolution}-bit resolution",
            "STM32 I2C master read/write to {device} at {speed}",
            "STM32 SPI full-duplex with DMA for {application}",
            "STM32 UART with DMA circular buffer for {baudrate} baud",
            "STM32 CAN bus configuration for {baudrate} with filters",
            "STM32 USB CDC virtual COM port implementation",
            "STM32 flash memory read/write for parameter storage",
            "STM32 watchdog (IWDG/WWDG) configuration",
            "STM32 RTC alarm and backup register usage",
            "STM32 bootloader jump from application",
            "STM32CubeMX code generation and project setup",
            "STM32 interrupt priority and NVIC configuration",
            "STM32 DMA2D for LCD framebuffer operations",
            "STM32 SDMMC interface for SD card with FatFS",
            "STM32 DAC output with DMA for waveform generation",
        ],
    },
    {
        "name": "ESP-IDF Programming",
        "count": 400,
        "topics": [
            "ESP-IDF project setup with CMake for {chip}",
            "ESP-IDF WiFi station mode with reconnection logic",
            "ESP-IDF WiFi AP mode with captive portal",
            "ESP-IDF BLE GATT server with custom service for {application}",
            "ESP-IDF BLE mesh networking for {node_count} nodes",
            "ESP-IDF MQTT client with TLS and auto-reconnect",
            "ESP-IDF HTTP server with REST API endpoints",
            "ESP-IDF OTA update over HTTPS with rollback",
            "ESP-IDF NVS (Non-Volatile Storage) for config persistence",
            "ESP-IDF SPIFFS/LittleFS filesystem for {application}",
            "ESP-IDF FreeRTOS task creation with {priority} priority",
            "ESP-IDF inter-task communication: queue, semaphore, event group",
            "ESP-IDF deep sleep with {wakeup_source} wake-up",
            "ESP-IDF ADC continuous mode with DMA for {sample_rate}",
            "ESP-IDF I2S audio input/output for {codec}",
            "ESP-IDF SPI master for {display} display driver",
            "ESP-IDF LEDC PWM for LED dimming and motor control",
            "ESP-IDF MCPWM for brushless motor control",
            "ESP-IDF ESP-NOW peer-to-peer communication",
            "ESP-IDF partition table customization for {layout}",
            "ESP-IDF component management with idf_component.yml",
            "ESP-IDF logging system (ESP_LOG) with custom tags",
            "ESP-IDF menuconfig (Kconfig) custom options",
            "ESP-IDF secure boot and flash encryption setup",
            "ESP32-S3 USB Host/Device mode configuration",
        ],
    },
    {
        "name": "Arduino Framework",
        "count": 300,
        "topics": [
            "Arduino {sensor} library usage with {board}",
            "Arduino interrupt handling for {application}",
            "Arduino timer library for precise {freq} timing",
            "Arduino {display} display with {library} library",
            "Arduino WiFi (ESP32/ESP8266) with {protocol} client",
            "Arduino BLE peripheral with characteristic for {data_type}",
            "Arduino I2C scanner and multi-device bus",
            "Arduino SPI communication with {device}",
            "Arduino serial protocol parser for {protocol}",
            "Arduino power optimization: sleep modes on {board}",
            "Arduino OTA update for {board} via WiFi",
            "Arduino state machine implementation for {application}",
            "Arduino PID controller for {application}",
            "Arduino EEPROM/Preferences storage for settings",
            "Arduino millis()-based non-blocking multitasking",
        ],
    },
    {
        "name": "FreeRTOS",
        "count": 300,
        "topics": [
            "FreeRTOS task creation on {mcu} with stack size {stack}",
            "FreeRTOS queue for inter-task communication of {data_type}",
            "FreeRTOS mutex vs semaphore: when to use which",
            "FreeRTOS software timer for periodic {task}",
            "FreeRTOS event group for multi-task synchronization",
            "FreeRTOS task notification as lightweight semaphore",
            "FreeRTOS memory management: heap_1 vs heap_4 vs heap_5",
            "FreeRTOS stack overflow detection and debugging",
            "FreeRTOS idle task hook for power management",
            "FreeRTOS priority inversion and priority inheritance",
            "FreeRTOS stream buffer for {protocol} data",
            "FreeRTOS tickless idle for low-power {mcu}",
            "FreeRTOS task watchdog implementation",
            "FreeRTOS + CMSIS-RTOS v2 abstraction layer",
            "FreeRTOS debugging with SystemView/Tracealyzer",
        ],
    },
    {
        "name": "Zephyr RTOS",
        "count": 200,
        "topics": [
            "Zephyr project setup for {board} with west",
            "Zephyr devicetree overlay for custom {peripheral}",
            "Zephyr Kconfig configuration for {feature}",
            "Zephyr BLE with {profile} profile",
            "Zephyr sensor driver API for {sensor}",
            "Zephyr shell module for debug CLI",
            "Zephyr logging subsystem configuration",
            "Zephyr power management framework",
            "Zephyr thread creation and scheduling",
            "Zephyr networking stack: TCP/UDP socket",
        ],
    },
    {
        "name": "Raspberry Pi Pico / RP2040",
        "count": 200,
        "topics": [
            "RP2040 PIO state machine for {protocol}",
            "Pico SDK GPIO, PWM, ADC basic usage",
            "RP2040 multicore: core0 and core1 with FIFO",
            "RP2040 DMA for high-speed {peripheral} transfer",
            "Pico W WiFi connection with lwIP",
            "RP2040 USB device with TinyUSB",
            "RP2040 flash XIP and execute-in-place optimization",
            "RP2040 PIO for WS2812 LED strip driver",
            "RP2040 PIO for custom UART at {baudrate}",
            "Pico SDK alarm and timer for precise timing",
        ],
    },
    {
        "name": "Communication Protocols",
        "count": 300,
        "topics": [
            "I2C bit-banging implementation for {mcu} without hardware I2C",
            "SPI slave mode implementation on {mcu}",
            "UART DMA ring buffer for reliable serial at {baudrate}",
            "RS-485 half-duplex communication with DE/RE control",
            "CAN bus 2.0A/B message handling on {mcu}",
            "1-Wire protocol (DS18B20) implementation on {mcu}",
            "Modbus RTU master/slave on {mcu} via RS-485",
            "DMX512 transmitter/receiver on {mcu}",
            "MIDI IN/OUT/THRU hardware and software on {mcu}",
            "USB HID keyboard/mouse implementation on {mcu}",
            "Ethernet W5500 SPI driver for {mcu}",
            "LoRa (SX1276/SX1262) communication on {mcu}",
            "NFC (PN532) reader implementation on {mcu}",
            "IR remote transmit/receive (NEC protocol) on {mcu}",
            "I2S audio codec interfacing ({codec}) on {mcu}",
        ],
    },
    {
        "name": "Sensor Interfacing",
        "count": 200,
        "topics": [
            "IMU ({imu}) sensor fusion with Madgwick/Mahony filter",
            "Temperature/humidity ({sensor}) with calibration",
            "Pressure sensor ({pressure}) altitude calculation",
            "Distance sensor ({distance}) measurement and filtering",
            "Current sensor ({current_sensor}) for power monitoring",
            "Load cell with HX711 ADC for weight measurement",
            "Encoder (rotary/linear) with quadrature decoding on {mcu}",
            "GPS (NMEA) parser for {gps_module} on {mcu}",
            "Analog sensor signal conditioning: amplification, filtering, protection",
            "Multi-sensor data fusion with Kalman filter on {mcu}",
        ],
    },
    {
        "name": "Motor Control",
        "count": 200,
        "topics": [
            "DC motor PWM speed control with H-bridge on {mcu}",
            "Stepper motor (A4988/TMC2209) driver on {mcu}",
            "Servo motor control with PWM on {mcu}",
            "BLDC motor FOC (Field Oriented Control) on {mcu}",
            "SimpleFOC library usage for BLDC on {board}",
            "Closed-loop position control with encoder feedback",
            "Motor current limiting and thermal protection",
            "AccelStepper library for acceleration profiles",
            "CNC G-code interpreter on {mcu}",
            "Robotic arm inverse kinematics on {mcu}",
        ],
    },
    {
        "name": "Display and UI",
        "count": 150,
        "topics": [
            "SSD1306 OLED display with {library} on {mcu}",
            "ILI9341/ST7789 TFT display with DMA on {mcu}",
            "LVGL (Light and Versatile Graphics Library) on {mcu}",
            "E-paper (Waveshare) partial refresh on {mcu}",
            "LED matrix (MAX7219) display on {mcu}",
            "WS2812/SK6812 addressable LED strip on {mcu}",
            "Touch screen (resistive/capacitive) input on {mcu}",
            "Menu system implementation for embedded UI",
        ],
    },
    {
        "name": "Debugging and Testing",
        "count": 150,
        "topics": [
            "SWD debugging with {debugger} on {mcu}",
            "JTAG vs SWD: when to use which",
            "GDB remote debugging for {mcu} firmware",
            "OpenOCD configuration for {mcu}",
            "Logic analyzer protocol decoding for {protocol}",
            "Unit testing embedded code with Unity/CeedlingK",
            "Hardware-in-the-loop testing for {mcu}",
            "Power profiling with {tool} for battery life estimation",
            "Fault handler (HardFault) debugging on Cortex-M",
            "Memory leak detection in embedded systems",
        ],
    },
    {
        "name": "Bootloader and OTA",
        "count": 150,
        "topics": [
            "Custom bootloader for {mcu} with dual-bank flash",
            "OTA firmware update over {transport} for {mcu}",
            "MCUboot integration with Zephyr on {mcu}",
            "STM32 IAP (In-Application Programming) bootloader",
            "ESP32 OTA with rollback and version checking",
            "Secure boot chain for {mcu}",
            "Firmware signing and verification for OTA",
            "A/B partition scheme for reliable updates",
            "Delta/differential firmware updates for bandwidth savings",
            "Recovery mode implementation for bricked devices",
        ],
    },
    {
        "name": "Power Management",
        "count": 150,
        "topics": [
            "Battery-powered {mcu} design: sleep modes and wake sources",
            "Solar-powered sensor node with MPPT on {mcu}",
            "Current consumption profiling and optimization on {mcu}",
            "Super capacitor backup power design",
            "Power gating peripheral circuits with MOSFET",
            "Brown-out detection and safe shutdown on {mcu}",
            "Energy harvesting circuit for {source}",
            "Battery fuel gauge (MAX17048) integration on {mcu}",
            "USB PD (Power Delivery) sink implementation",
            "Wireless charging (Qi) receiver integration",
        ],
    },
    {
        "name": "nRF52/nRF53 Nordic",
        "count": 150,
        "topics": [
            "nRF52840 BLE advertising with custom data",
            "nRF52 soft device (S132/S140) integration",
            "nRF Connect SDK (NCS) project setup",
            "nRF52 BLE UART service (NUS) implementation",
            "nRF52 low power optimization: system off vs system on",
            "nRF52 SAADC (ADC) with oversampling",
            "nRF52 PWM with sequence playback",
            "nRF52 QSPI flash external memory",
            "nRF52 mesh networking (Bluetooth Mesh)",
            "nRF53 dual-core (app + network) IPC",
        ],
    },
    {
        "name": "RISC-V Embedded",
        "count": 100,
        "topics": [
            "RISC-V GD32VF103 GPIO and peripheral setup",
            "ESP32-C3 (RISC-V) with ESP-IDF",
            "CH32V003 ultra-low-cost RISC-V programming",
            "BL602/BL616 WiFi+BLE RISC-V development",
            "RISC-V interrupt handling (PLIC/CLIC)",
            "RISC-V bare-metal startup code and linker script",
            "Milk-V Duo embedded Linux + RISC-V",
            "Kendryte K210 AI accelerator programming",
        ],
    },
    {
        "name": "ARM Cortex Architecture",
        "count": 200,
        "topics": [
            "ARM Cortex-M0/M0+ architecture overview and register set",
            "ARM Cortex-M3/M4 exception model and NVIC",
            "ARM Cortex-M4 DSP instructions (SIMD, MAC) for {application}",
            "ARM Cortex-M7 cache (I-cache, D-cache) management",
            "ARM Cortex-M33 TrustZone security partitioning",
            "ARM Cortex-A vs Cortex-M vs Cortex-R comparison",
            "ARM CMSIS-Core API for portable firmware",
            "ARM CMSIS-DSP library: FFT, FIR, IIR on Cortex-M4F",
            "ARM MPU (Memory Protection Unit) configuration on Cortex-M",
            "ARM SysTick timer for RTOS tick and delay",
            "Thumb-2 instruction set optimization for code density",
            "ARM ETM/ITM trace for real-time debugging",
        ],
    },
    {
        "name": "Assembly Language (ARM/RISC-V/AVR)",
        "count": 200,
        "topics": [
            "ARM Thumb assembly: {asm_task} on Cortex-M",
            "ARM inline assembly in C for {asm_task}",
            "AVR assembly: {avr_task} on ATmega328P",
            "RISC-V assembly: {riscv_task} on RV32I",
            "ARM assembly: context switch implementation for RTOS",
            "ARM assembly: DSP FIR filter using MAC instructions",
            "AVR assembly: precise timing loop for {protocol}",
            "RISC-V assembly: CSR (Control Status Register) access",
            "ARM assembly: SVC (Supervisor Call) for OS kernel",
            "Mixing C and assembly: calling conventions ARM AAPCS",
            "ARM assembly: atomic operations (LDREX/STREX) for lock-free",
            "Boot startup code in assembly for {mcu}",
        ],
    },
    {
        "name": "ATtiny/AVR Microchip",
        "count": 200,
        "topics": [
            "ATtiny85 GPIO, PWM, ADC bare-metal programming",
            "ATtiny1614 (new AVR) with UART, SPI, I2C",
            "ATmega328P timer/counter configuration for {application}",
            "ATmega2560 multi-UART communication",
            "AVR fuse bits configuration and programming",
            "AVR sleep modes and wake-up sources for battery operation",
            "AVR watchdog timer for reliability",
            "AVR EEPROM read/write for persistent storage",
            "AVR ADC with noise reduction mode",
            "ATtiny series 0/1/2 modern AVR peripherals (TCB, CCL)",
            "UPDI programming for modern ATtiny/ATmega",
            "AVR bootloader (Optiboot) customization",
        ],
    },
    {
        "name": "Microchip PIC/dsPIC/SAM",
        "count": 150,
        "topics": [
            "PIC18F{variant} UART, SPI, I2C configuration with MPLAB",
            "dsPIC33 motor control with PWM and ADC",
            "SAMD21 (ARM Cortex-M0+) with Atmel START/Harmony",
            "SAME54 Ethernet and USB with MPLAB Harmony 3",
            "PIC32MZ high-performance with DMA and USB",
            "MPLAB X IDE project setup for {pic_family}",
            "Microchip MCC (Code Configurator) peripheral setup",
            "PIC CLC (Configurable Logic Cell) for hardware logic",
            "Microchip Trust Platform secure element integration",
            "dsPIC DSP library: FFT and filter implementations",
        ],
    },
    {
        "name": "Texas Instruments MSP430/CC/TMS",
        "count": 150,
        "topics": [
            "MSP430 ultra-low-power design with LPM modes",
            "MSP430 timer capture/compare for {application}",
            "MSP432 (ARM Cortex-M4F) with DriverLib",
            "CC2640/CC2652 BLE stack (TI SimpleLink)",
            "CC1310/CC1352 Sub-GHz long-range radio",
            "TMS320C28x DSP programming for motor control",
            "TI Code Composer Studio project setup",
            "TI SysConfig tool for peripheral configuration",
            "MSP430 ADC12 with DMA for multi-channel sampling",
            "TI RTOS (SYS/BIOS) task scheduling on CC26xx",
        ],
    },
]

VARS = {
    "board": ["esp32dev", "esp32-s3-devkitc-1", "esp32-c3-devkitm-1", "nucleo_f446re", "nucleo_f103rb", "nucleo_h743zi", "nucleo_l476rg", "pico", "teensy41", "adafruit_feather_nrf52840", "seeed_xiao_esp32s3", "arduino_nano_33_ble"],
    "board1": ["esp32dev", "nucleo_f446re"],
    "board2": ["esp32-s3-devkitc-1", "nucleo_h743zi"],
    "framework": ["arduino", "espidf", "stm32cube", "zephyr", "mbed"],
    "libs": ["WiFi + MQTT + ArduinoJSON", "Adafruit_SSD1306 + Wire", "FastLED + WiFi", "TFT_eSPI + LVGL"],
    "mcu": ["STM32F446RE", "STM32H743", "STM32L476RG", "STM32F103C8", "STM32G431", "ESP32-S3", "ESP32-C3", "nRF52840", "RP2040", "GD32VF103"],
    "stm32": ["STM32F446RE", "STM32H743ZI", "STM32L476RG", "STM32F103C8T6", "STM32G431KB", "STM32F407VG", "STM32L031K6"],
    "chip": ["ESP32", "ESP32-S2", "ESP32-S3", "ESP32-C3", "ESP32-C6", "ESP32-H2"],
    "peripheral": ["USART", "SPI", "I2C", "TIM (timer)", "ADC", "DAC", "DMA", "GPIO EXTI", "CAN", "USB", "SDMMC", "QSPI", "SAI (audio)"],
    "mode": ["Stop 1", "Stop 2", "Standby", "Shutdown"],
    "source": ["RTC alarm", "EXTI pin", "UART", "comparator"],
    "freq": ["8", "16", "25", "32"],
    "sysclk": ["72", "100", "168", "216", "400", "480"],
    "channels": ["2", "4", "8", "16"],
    "speed": ["100kHz standard", "400kHz fast", "1MHz fast-plus"],
    "baudrate": ["9600", "115200", "460800", "921600", "1000000"],
    "device": ["BME280 sensor", "MPU6050 IMU", "ADS1115 ADC", "MCP4725 DAC", "OLED SSD1306", "EEPROM AT24C256"],
    "application": ["data logger", "motor controller", "audio processor", "sensor node", "LED controller", "robot controller"],
    "method": ["ST-Link", "J-Link", "DFU", "serial bootloader", "WiFi OTA"],
    "optimization": ["size (-Os)", "speed (-O2)", "debug (-Og)", "LTO"],
    "display": ["SSD1306 OLED 128x64", "ILI9341 TFT 320x240", "ST7789 TFT 240x240", "SH1106 OLED", "e-paper 2.9in"],
    "library": ["Adafruit_GFX", "TFT_eSPI", "U8g2", "LVGL"],
    "protocol": ["MQTT", "HTTP REST", "WebSocket", "CoAP", "Modbus RTU"],
    "data_type": ["float sensor reading", "uint8_t command", "struct telemetry packet", "char string"],
    "sensor": ["DHT22", "BME280", "BMP390", "SHT40", "AHT20"],
    "pressure": ["BMP280", "BMP390", "LPS22HB", "MS5611"],
    "distance": ["HC-SR04 ultrasonic", "VL53L1X ToF", "TFmini LiDAR"],
    "current_sensor": ["INA219", "INA226", "ACS712", "MAX471"],
    "imu": ["MPU6050", "BMI270", "ICM-20948", "LSM6DSO"],
    "gps_module": ["NEO-6M", "NEO-M8N", "L76K", "PA1010D"],
    "codec": ["MAX98357 I2S DAC", "PCM5102 DAC", "INMP441 MEMS mic", "WM8960 codec"],
    "debugger": ["ST-Link V2", "J-Link", "CMSIS-DAP", "Black Magic Probe"],
    "tool": ["Nordic PPK2", "Joulescope", "Otii Arc"],
    "transport": ["WiFi HTTPS", "BLE", "LoRaWAN", "USB", "UART"],
    "stack": ["512", "1024", "2048", "4096"],
    "task": ["LED blink", "sensor read", "data logging", "watchdog feed"],
    "priority": ["low (1)", "normal (5)", "high (10)", "realtime (configMAX_PRIORITIES-1)"],
    "feature": ["BLE", "USB", "logging", "shell", "networking"],
    "profile": ["Heart Rate", "Battery", "Environmental Sensing", "custom GATT"],
    "wakeup_source": ["timer", "ext0 GPIO", "ext1 GPIO bitmask", "touch pad", "ULP coprocessor"],
    "sample_rate": ["1kHz", "10kHz", "44.1kHz", "100kHz"],
    "layout": ["factory + 2 OTA + NVS + SPIFFS", "single app + NVS", "dual app + coredump"],
    "node_count": ["5", "10", "50", "100"],
    "resolution": ["8", "10", "12", "16"],
    "libs_specific": ["PubSubClient", "ArduinoOTA", "ESPAsyncWebServer", "AccelStepper"],
    "asm_task": ["bit manipulation", "interrupt vector table", "delay loop", "stack frame setup", "memory copy", "CRC calculation"],
    "avr_task": ["LED blink with timer interrupt", "UART transmit", "ADC read", "PWM generation", "watchdog reset"],
    "riscv_task": ["GPIO toggle", "timer interrupt handler", "UART polling", "CSR read/write", "trap handler"],
    "pic_family": ["PIC18F", "PIC24F", "dsPIC33", "PIC32MZ", "SAMD21"],
    "variant": ["46K22", "25K50", "27J53"],
    "source": ["piezoelectric", "thermoelectric", "RF", "solar indoor"],
}


def fill_template(template):
    result = template
    for key, values in VARS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    return result


def generate_qa(category_name, topic_template):
    topic = fill_template(topic_template)
    prompt = f"""You are an expert embedded systems engineer writing training data.

Category: {category_name}
Topic: {topic}

Generate a detailed, technically accurate Q&A pair.
Include actual code snippets (C/C++, Python, YAML, INI) where relevant.
The answer should be 200-600 words with working code examples.

Reply ONLY JSON: {{"question": "...", "answer": "..."}}"""

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(CODESTRAL_URL, headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
                "max_tokens": 1000,
            })
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            if "question" in data and "answer" in data:
                return {
                    "conversations": [
                        {"from": "system", "value": f"You are an expert embedded systems engineer specializing in {category_name}. You write production-grade firmware code."},
                        {"from": "human", "value": data["question"]},
                        {"from": "gpt", "value": data["answer"]},
                    ],
                    "domain": "embedded",
                    "category": category_name,
                    "source": "codestral-teacher-distillation",
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CATEGORIES)
    print("=== Embedded Systems Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs ({len(CATEGORIES)} categories)\n")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    total = 0
    errors = 0

    with open(OUTPUT, "w") as f:
        for cat in CATEGORIES:
            print(f"\n=== {cat['name']} ({cat['count']} pairs) ===")
            cat_count = 0
            for i in range(cat["count"]):
                topic = random.choice(cat["topics"])
                result = generate_qa(cat["name"], topic)
                if result:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    cat_count += 1
                    total += 1
                else:
                    errors += 1
                if (i + 1) % 50 == 0:
                    print(f"  [{i+1}/{cat['count']}] generated={cat_count} errors={errors}")
                time.sleep(0.5)
            print(f"  DONE: {cat_count} pairs")

    print("\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
