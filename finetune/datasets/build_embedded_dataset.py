#!/usr/bin/env python3
"""Build fine-tuning dataset for embedded ARM/ESP32/RISC-V domain.

Covers: ARM Cortex-M (STM32, Teensy, nRF), ESP32/ESP-IDF, RISC-V,
        Raspberry Pi, bare-metal firmware, CMSIS, FreeRTOS.

Usage:
  python build_embedded_dataset.py                    # Seeds only (~6 examples)
  python build_embedded_dataset.py --with-hf          # Seeds + HuggingFace datasets
  python build_embedded_dataset.py --max-samples 2000 # Limit HF samples per source
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert embedded systems engineer specializing in "
    "ARM Cortex-M (STM32, nRF52, Teensy, SAMD), ESP32/ESP-IDF, "
    "and RISC-V architectures. You write production-grade firmware in C/C++, "
    "bare-metal and RTOS-based, with proper register-level access, DMA, "
    "interrupt handling, low-power modes, and bootloader design. "
    "You know CMSIS, HAL, LL drivers, linker scripts, startup code, "
    "and ARM/RISC-V assembly. You also handle Raspberry Pi bare-metal "
    "and embedded Linux (device trees, kernel modules, GPIO/SPI/I2C)."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write bare-metal ARM Cortex-M4 startup code in assembly with vector table and Reset_Handler."},
            {"from": "gpt", "value": """ARM Cortex-M4 bare-metal startup (GNU AS syntax):

```asm
/* startup.s — Cortex-M4 startup for STM32F4xx */
.syntax unified
.cpu cortex-m4
.fpu fpv4-sp-d16
.thumb

/* Vector table — must be at 0x00000000 (or VTOR offset) */
.section .isr_vector, "a", %progbits
.type g_pfnVectors, %object

g_pfnVectors:
    .word _estack              /* Initial SP (top of RAM) */
    .word Reset_Handler        /* Reset */
    .word NMI_Handler          /* NMI */
    .word HardFault_Handler    /* Hard Fault */
    .word MemManage_Handler    /* MPU Fault */
    .word BusFault_Handler     /* Bus Fault */
    .word UsageFault_Handler   /* Usage Fault */
    .word 0, 0, 0, 0           /* Reserved */
    .word SVC_Handler          /* SVCall */
    .word DebugMon_Handler     /* Debug Monitor */
    .word 0                    /* Reserved */
    .word PendSV_Handler       /* PendSV */
    .word SysTick_Handler      /* SysTick */
    /* IRQ0-81 would follow here for STM32F4 */

.size g_pfnVectors, . - g_pfnVectors

/* Reset handler — C runtime init */
.section .text.Reset_Handler
.type Reset_Handler, %function
.global Reset_Handler

Reset_Handler:
    /* 1. Set stack pointer (redundant but safe) */
    ldr sp, =_estack

    /* 2. Enable FPU (Cortex-M4F) */
    ldr r0, =0xE000ED88     /* CPACR address */
    ldr r1, [r0]
    orr r1, r1, #(0xF << 20) /* CP10 + CP11 full access */
    str r1, [r0]
    dsb
    isb

    /* 3. Copy .data from Flash to RAM */
    ldr r0, =_sdata          /* RAM destination start */
    ldr r1, =_edata          /* RAM destination end */
    ldr r2, =_sidata         /* Flash source (LMA) */
copy_data:
    cmp r0, r1
    bge zero_bss
    ldr r3, [r2], #4
    str r3, [r0], #4
    b copy_data

    /* 4. Zero .bss section */
zero_bss:
    ldr r0, =_sbss
    ldr r1, =_ebss
    movs r2, #0
bss_loop:
    cmp r0, r1
    bge call_main
    str r2, [r0], #4
    b bss_loop

    /* 5. Call SystemInit() then main() */
call_main:
    bl SystemInit             /* Clock config (defined in system_stm32f4xx.c) */
    bl main                   /* User application */

    /* If main returns, loop forever */
hang:
    b hang

.size Reset_Handler, . - Reset_Handler

/* Default handlers — infinite loop (weak, can be overridden) */
.macro def_irq_handler handler
    .weak \\handler
    .type \\handler, %function
\\handler:
    b .
    .size \\handler, . - \\handler
.endm

def_irq_handler NMI_Handler
def_irq_handler HardFault_Handler
def_irq_handler MemManage_Handler
def_irq_handler BusFault_Handler
def_irq_handler UsageFault_Handler
def_irq_handler SVC_Handler
def_irq_handler DebugMon_Handler
def_irq_handler PendSV_Handler
def_irq_handler SysTick_Handler
```

Corresponding linker script sections needed:
```
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 1024K
    RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 128K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
```

Key points:
- Vector table MUST start at address 0x0 (or set VTOR register)
- FPU must be enabled before any float operations
- `.data` copy and `.bss` zero are essential for C runtime
- Weak handlers allow user code to override individual IRQs"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write ESP32 code using ESP-IDF to configure SPI master and communicate with an SPI flash chip (W25Q128)."},
            {"from": "gpt", "value": """ESP-IDF SPI master driver for W25Q128 SPI flash:

```c
#include "driver/spi_master.h"
#include "esp_log.h"
#include <string.h>

#define TAG "W25Q128"

// W25Q128 commands
#define CMD_WRITE_ENABLE    0x06
#define CMD_WRITE_DISABLE   0x04
#define CMD_READ_STATUS     0x05
#define CMD_READ_DATA       0x03
#define CMD_PAGE_PROGRAM    0x02
#define CMD_SECTOR_ERASE    0x20
#define CMD_CHIP_ERASE      0xC7
#define CMD_READ_JEDEC_ID   0x9F

// SPI pins (ESP32 VSPI)
#define PIN_MOSI  23
#define PIN_MISO  19
#define PIN_CLK   18
#define PIN_CS    5

static spi_device_handle_t spi_dev;

esp_err_t w25q128_init(void) {
    // 1. Configure SPI bus
    spi_bus_config_t bus_cfg = {
        .mosi_io_num = PIN_MOSI,
        .miso_io_num = PIN_MISO,
        .sclk_io_num = PIN_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &bus_cfg, SPI_DMA_CH_AUTO));

    // 2. Attach device (W25Q128 supports up to 104MHz, use 40MHz for reliability)
    spi_device_interface_config_t dev_cfg = {
        .clock_speed_hz = 40 * 1000 * 1000,  // 40 MHz
        .mode = 0,                             // CPOL=0, CPHA=0
        .spics_io_num = PIN_CS,
        .queue_size = 7,
        .flags = 0,
    };
    ESP_ERROR_CHECK(spi_bus_add_device(SPI3_HOST, &dev_cfg, &spi_dev));

    // 3. Verify JEDEC ID
    uint8_t id[3];
    w25q128_read_jedec_id(id);
    ESP_LOGI(TAG, "JEDEC ID: %02X %02X %02X", id[0], id[1], id[2]);
    // Expected: EF 40 18 (Winbond W25Q128)
    if (id[0] != 0xEF || id[2] != 0x18) {
        ESP_LOGE(TAG, "Unexpected JEDEC ID!");
        return ESP_ERR_NOT_FOUND;
    }
    return ESP_OK;
}

void w25q128_read_jedec_id(uint8_t *id) {
    spi_transaction_t t = {
        .cmd = CMD_READ_JEDEC_ID,
        .length = 24,            // 3 bytes response
        .flags = SPI_TRANS_USE_RXDATA,
    };
    spi_device_transmit(spi_dev, &t);
    memcpy(id, t.rx_data, 3);
}

static void w25q128_write_enable(void) {
    spi_transaction_t t = {
        .cmd = CMD_WRITE_ENABLE,
        .length = 0,
    };
    spi_device_transmit(spi_dev, &t);
}

static void w25q128_wait_busy(void) {
    spi_transaction_t t = {
        .cmd = CMD_READ_STATUS,
        .length = 8,
        .flags = SPI_TRANS_USE_RXDATA,
    };
    do {
        spi_device_transmit(spi_dev, &t);
    } while (t.rx_data[0] & 0x01);  // BUSY bit
}

esp_err_t w25q128_read(uint32_t addr, uint8_t *buf, size_t len) {
    uint8_t cmd[4] = {
        CMD_READ_DATA,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
    };
    spi_transaction_t t = {
        .tx_buffer = cmd,
        .length = 32,             // 4 bytes command+address
        .rx_buffer = buf,
        .rxlength = len * 8,
    };
    // Use full-duplex: send cmd, then read data
    spi_transaction_ext_t ext = {
        .base = {
            .flags = SPI_TRANS_VARIABLE_CMD | SPI_TRANS_VARIABLE_ADDR,
            .rx_buffer = buf,
            .rxlength = len * 8,
        },
        .command_bits = 8,
        .address_bits = 24,
    };
    ext.base.cmd = CMD_READ_DATA;
    ext.base.addr = addr;
    return spi_device_transmit(spi_dev, (spi_transaction_t *)&ext);
}

esp_err_t w25q128_page_program(uint32_t addr, const uint8_t *data, size_t len) {
    if (len > 256) return ESP_ERR_INVALID_SIZE;  // Page size = 256 bytes

    w25q128_write_enable();

    spi_transaction_ext_t ext = {
        .base = {
            .flags = SPI_TRANS_VARIABLE_CMD | SPI_TRANS_VARIABLE_ADDR,
            .tx_buffer = data,
            .length = len * 8,
        },
        .command_bits = 8,
        .address_bits = 24,
    };
    ext.base.cmd = CMD_PAGE_PROGRAM;
    ext.base.addr = addr;

    esp_err_t ret = spi_device_transmit(spi_dev, (spi_transaction_t *)&ext);
    w25q128_wait_busy();  // Typical 0.7ms, max 3ms
    return ret;
}

esp_err_t w25q128_sector_erase(uint32_t addr) {
    w25q128_write_enable();

    spi_transaction_ext_t ext = {
        .base = {
            .flags = SPI_TRANS_VARIABLE_CMD | SPI_TRANS_VARIABLE_ADDR,
            .length = 0,
        },
        .command_bits = 8,
        .address_bits = 24,
    };
    ext.base.cmd = CMD_SECTOR_ERASE;
    ext.base.addr = addr & 0xFFF000;  // Align to 4KB sector

    esp_err_t ret = spi_device_transmit(spi_dev, (spi_transaction_t *)&ext);
    w25q128_wait_busy();  // Typical 45ms, max 400ms
    return ret;
}
```

Key points:
- W25Q128: 128Mbit (16MB), 65536 pages of 256 bytes, 4KB sectors
- Must erase before programming (sets bits to 1, programming sets to 0)
- SPI Mode 0 (CPOL=0, CPHA=0) or Mode 3 (CPOL=1, CPHA=1)
- Use DMA for transfers >64 bytes (ESP-IDF handles this with SPI_DMA_CH_AUTO)"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a RISC-V bare-metal program in assembly that blinks an LED on a SiFive HiFive1 board."},
            {"from": "gpt", "value": """RISC-V bare-metal LED blink for SiFive HiFive1 (FE310-G000):

```asm
# led_blink.S — RISC-V RV32IMAC bare-metal LED blink
# HiFive1 Rev B: Green LED on GPIO pin 19

.equ GPIO_BASE,      0x10012000
.equ GPIO_OUTPUT_EN,  0x08    # Output enable register
.equ GPIO_OUTPUT_VAL, 0x0C    # Output value register
.equ GPIO_PIN,        19       # Green LED

.equ CLINT_BASE,      0x02000000
.equ CLINT_MTIME,     0xBFF8   # Machine timer (64-bit)

.section .text
.globl _start

_start:
    # 1. Set GPIO pin 19 as output
    li   t0, GPIO_BASE
    lw   t1, GPIO_OUTPUT_EN(t0)
    li   t2, (1 << GPIO_PIN)
    or   t1, t1, t2
    sw   t1, GPIO_OUTPUT_EN(t0)

blink_loop:
    # 2. Toggle LED
    lw   t1, GPIO_OUTPUT_VAL(t0)
    xor  t1, t1, t2
    sw   t1, GPIO_OUTPUT_VAL(t0)

    # 3. Delay (~500ms at 16MHz default clock)
    li   a0, 8000000          # ~0.5s at 16MHz
delay:
    addi a0, a0, -1
    bnez a0, delay

    j    blink_loop

# Trap handler (minimal)
.globl _trap_handler
_trap_handler:
    j _trap_handler

# Entry point for linker
.section .init
.globl _entry
_entry:
    # Set stack pointer
    la   sp, _stack_top
    # Clear BSS
    la   t0, _bss_start
    la   t1, _bss_end
clear_bss:
    bge  t0, t1, done_bss
    sw   zero, 0(t0)
    addi t0, t0, 4
    j    clear_bss
done_bss:
    # Set trap vector
    la   t0, _trap_handler
    csrw mtvec, t0
    # Jump to main code
    j    _start
```

Linker script (`hifive1.ld`):
```ld
MEMORY {
    FLASH (rx)  : ORIGIN = 0x20000000, LENGTH = 16M
    RAM   (rwx) : ORIGIN = 0x80000000, LENGTH = 16K
}

SECTIONS {
    .init : { *(.init) } > FLASH
    .text : { *(.text*) } > FLASH
    .rodata : { *(.rodata*) } > FLASH

    .data : {
        _data_start = .;
        *(.data*)
        _data_end = .;
    } > RAM AT > FLASH

    .bss : {
        _bss_start = .;
        *(.bss*)
        *(COMMON)
        _bss_end = .;
    } > RAM

    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
}
```

Build:
```bash
riscv64-unknown-elf-gcc -march=rv32imac -mabi=ilp32 -nostdlib \\
    -T hifive1.ld -o blink.elf led_blink.S
riscv64-unknown-elf-objcopy -O binary blink.elf blink.bin
# Flash with JLink or OpenOCD
```

Key RISC-V differences from ARM:
- CSR registers (mtvec, mstatus) instead of NVIC
- No vector table — single trap handler dispatches via mcause
- Memory-mapped GPIO (no special peripheral bus like AHB/APB)
- RV32IMAC = Integer + Multiply + Atomic + Compressed instructions"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "How to configure DMA on STM32F4 using LL drivers for high-speed ADC sampling?"},
            {"from": "gpt", "value": """STM32F4 DMA + ADC with LL drivers for continuous high-speed sampling:

```c
#include "stm32f4xx_ll_adc.h"
#include "stm32f4xx_ll_dma.h"
#include "stm32f4xx_ll_gpio.h"
#include "stm32f4xx_ll_rcc.h"
#include "stm32f4xx_ll_tim.h"

#define ADC_BUFFER_SIZE  1024
#define SAMPLE_RATE      100000  // 100 kSPS

static volatile uint16_t adc_buffer[ADC_BUFFER_SIZE];
static volatile bool buffer_ready = false;

void adc_dma_init(void) {
    // 1. Enable clocks
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPIOA);
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_DMA2);
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_ADC1);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);

    // 2. Configure GPIO (PA0 = ADC1_IN0, analog mode)
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_0, LL_GPIO_MODE_ANALOG);

    // 3. Configure TIM2 as ADC trigger (TRGO on update)
    // APB1 = 84MHz, prescaler=0, ARR = 84M/100k - 1 = 839
    LL_TIM_SetPrescaler(TIM2, 0);
    LL_TIM_SetAutoReload(TIM2, (84000000 / SAMPLE_RATE) - 1);
    LL_TIM_SetTriggerOutput(TIM2, LL_TIM_TRGO_UPDATE);

    // 4. Configure DMA2 Stream0 Channel0 (ADC1)
    LL_DMA_SetChannelSelection(DMA2, LL_DMA_STREAM_0, LL_DMA_CHANNEL_0);
    LL_DMA_SetDataTransferDirection(DMA2, LL_DMA_STREAM_0,
                                     LL_DMA_DIRECTION_PERIPH_TO_MEMORY);
    LL_DMA_SetStreamPriorityLevel(DMA2, LL_DMA_STREAM_0,
                                   LL_DMA_PRIORITY_HIGH);
    LL_DMA_SetMode(DMA2, LL_DMA_STREAM_0, LL_DMA_MODE_CIRCULAR);
    LL_DMA_SetPeriphIncMode(DMA2, LL_DMA_STREAM_0,
                             LL_DMA_PERIPH_NOINCREMENT);
    LL_DMA_SetMemoryIncMode(DMA2, LL_DMA_STREAM_0,
                             LL_DMA_MEMORY_INCREMENT);
    LL_DMA_SetPeriphSize(DMA2, LL_DMA_STREAM_0, LL_DMA_PDATAALIGN_HALFWORD);
    LL_DMA_SetMemorySize(DMA2, LL_DMA_STREAM_0, LL_DMA_MDATAALIGN_HALFWORD);

    // Source: ADC1->DR, Destination: buffer
    LL_DMA_SetPeriphAddress(DMA2, LL_DMA_STREAM_0,
                             LL_ADC_DMA_GetRegAddr(ADC1, LL_ADC_DMA_REG_REGULAR_DATA));
    LL_DMA_SetMemoryAddress(DMA2, LL_DMA_STREAM_0, (uint32_t)adc_buffer);
    LL_DMA_SetDataLength(DMA2, LL_DMA_STREAM_0, ADC_BUFFER_SIZE);

    // Enable half-transfer and transfer-complete interrupts
    LL_DMA_EnableIT_HT(DMA2, LL_DMA_STREAM_0);
    LL_DMA_EnableIT_TC(DMA2, LL_DMA_STREAM_0);
    NVIC_SetPriority(DMA2_Stream0_IRQn, 1);
    NVIC_EnableIRQ(DMA2_Stream0_IRQn);

    LL_DMA_EnableStream(DMA2, LL_DMA_STREAM_0);

    // 5. Configure ADC1
    LL_ADC_SetCommonClock(__LL_ADC_COMMON_INSTANCE(ADC1),
                           LL_ADC_CLOCK_SYNC_PCLK_DIV4);  // 84/4 = 21MHz
    LL_ADC_SetResolution(ADC1, LL_ADC_RESOLUTION_12B);
    LL_ADC_SetDataAlignment(ADC1, LL_ADC_DATA_ALIGN_RIGHT);
    LL_ADC_SetSequencersScanMode(ADC1, LL_ADC_SEQ_SCAN_DISABLE);
    LL_ADC_REG_SetTriggerSource(ADC1, LL_ADC_REG_TRIG_EXT_TIM2_TRGO);
    LL_ADC_REG_SetTriggerEdge(ADC1, LL_ADC_REG_TRIG_EXT_RISING);
    LL_ADC_REG_SetContinuousMode(ADC1, LL_ADC_REG_CONV_SINGLE);
    LL_ADC_REG_SetDMATransfer(ADC1, LL_ADC_REG_DMA_TRANSFER_UNLIMITED);
    LL_ADC_REG_SetSequencerLength(ADC1, LL_ADC_REG_SEQ_SCAN_DISABLE);
    LL_ADC_REG_SetSequencerRanks(ADC1, LL_ADC_REG_RANK_1, LL_ADC_CHANNEL_0);
    LL_ADC_SetChannelSamplingTime(ADC1, LL_ADC_CHANNEL_0,
                                   LL_ADC_SAMPLINGTIME_15CYCLES);
    // Conversion time: (15+12)/21MHz = 1.28µs → max 781 kSPS

    // 6. Start
    LL_ADC_Enable(ADC1);
    LL_TIM_EnableCounter(TIM2);
    LL_ADC_REG_StartConversionExtTrig(ADC1, LL_ADC_REG_TRIG_EXT_RISING);
}

void DMA2_Stream0_IRQHandler(void) {
    if (LL_DMA_IsActiveFlag_HT0(DMA2)) {
        LL_DMA_ClearFlag_HT0(DMA2);
        // Process first half: adc_buffer[0..511]
    }
    if (LL_DMA_IsActiveFlag_TC0(DMA2)) {
        LL_DMA_ClearFlag_TC0(DMA2);
        // Process second half: adc_buffer[512..1023]
        buffer_ready = true;
    }
}
```

Double-buffering strategy:
- DMA in circular mode fills buffer continuously
- HT interrupt → process first half while DMA fills second half
- TC interrupt → process second half while DMA wraps to first half
- Zero CPU involvement in data transfer — true hardware pipeline"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a Raspberry Pi bare-metal program in C that blinks an LED on GPIO17 without any OS."},
            {"from": "gpt", "value": """Raspberry Pi bare-metal LED blink (BCM2835/RPi 1, adaptable to RPi 3/4):

```c
/* kernel.c — Bare-metal GPIO blink for Raspberry Pi */

#include <stdint.h>

// BCM2835 (RPi 1) peripheral base — change for other models:
// RPi 2/3: 0x3F000000, RPi 4: 0xFE000000
#define PERIPHERAL_BASE  0x20000000
#define GPIO_BASE        (PERIPHERAL_BASE + 0x200000)

// GPIO registers (each controls 10 pins)
#define GPFSEL1     ((volatile uint32_t *)(GPIO_BASE + 0x04))  // GPIO 10-19
#define GPSET0      ((volatile uint32_t *)(GPIO_BASE + 0x1C))  // Set pins 0-31
#define GPCLR0      ((volatile uint32_t *)(GPIO_BASE + 0x28))  // Clear pins 0-31

// System timer (free-running 1MHz counter)
#define TIMER_CLO   ((volatile uint32_t *)(PERIPHERAL_BASE + 0x3004))

#define LED_PIN     17

static void delay_ms(uint32_t ms) {
    uint32_t start = *TIMER_CLO;
    while (*TIMER_CLO - start < ms * 1000);
}

void kernel_main(void) {
    // 1. Set GPIO17 as output
    // GPFSEL1 controls pins 10-19, each pin uses 3 bits
    // Pin 17: bits [23:21], value 001 = output
    uint32_t sel = *GPFSEL1;
    sel &= ~(7 << 21);    // Clear bits [23:21]
    sel |= (1 << 21);     // Set to output (001)
    *GPFSEL1 = sel;

    // 2. Blink loop
    while (1) {
        *GPSET0 = (1 << LED_PIN);   // LED ON
        delay_ms(500);
        *GPCLR0 = (1 << LED_PIN);   // LED OFF
        delay_ms(500);
    }
}
```

Boot stub (`boot.S`):
```asm
/* boot.S — RPi bare-metal entry point */
.section ".text.boot"
.globl _start

_start:
    // Check processor ID — only core 0 runs, others halt
    mrc p15, 0, r0, c0, c0, 5   // Read MPIDR
    and r0, r0, #3
    cmp r0, #0
    bne halt

    // Set stack pointer (below kernel at 0x8000)
    mov sp, #0x8000

    // Zero BSS
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
bss_loop:
    cmp r0, r1
    strlt r2, [r0], #4
    blt bss_loop

    // Jump to C code
    bl kernel_main

halt:
    wfe
    b halt
```

Linker script (`linker.ld`):
```ld
SECTIONS {
    . = 0x8000;  /* RPi loads kernel.img here */
    .text : { KEEP(*(.text.boot)) *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    __bss_start = .;
    .bss : { *(.bss*) }
    __bss_end = .;
}
```

Build & deploy:
```bash
arm-none-eabi-gcc -mcpu=arm1176jzf-s -fpic -ffreestanding \\
    -c boot.S -o boot.o
arm-none-eabi-gcc -mcpu=arm1176jzf-s -fpic -ffreestanding \\
    -std=gnu11 -O2 -c kernel.c -o kernel.o
arm-none-eabi-gcc -T linker.ld -o kernel.elf -ffreestanding \\
    -O2 -nostdlib boot.o kernel.o
arm-none-eabi-objcopy kernel.elf -O binary kernel.img
# Copy kernel.img to SD card root alongside bootcode.bin and start.elf
```"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Explain the Teensy 4.1 (i.MX RT1062) startup sequence and how to use its hardware timers in bare-metal."},
            {"from": "gpt", "value": """Teensy 4.1 (i.MX RT1062 Cortex-M7) startup and hardware timers:

**Boot sequence:**
1. Boot ROM in i.MX RT1062 reads FlexSPI NOR flash
2. Image Vector Table (IVT) at offset 0x1000 points to:
   - Entry point (Reset_Handler)
   - DCD (Device Configuration Data) for SDRAM/clock init
   - Boot data (load address, size)
3. FlexRAM configured: 512KB total split as ITCM/DTCM/OCRAM
4. Clocks configured: ARM core up to 600MHz, bus clocks derived

**FlexRAM configuration (Teensy default):**
```c
// Teensy 4.1 FlexRAM split:
// ITCM: 512KB (instruction TCM — fast code execution)
// DTCM: 512KB (data TCM — stack, variables, fast data)
// OCRAM: 0KB (used via DMAMEM attribute)
// Total on-chip: 1MB (512K ITCM + 512K DTCM)
// External PSRAM: 8MB (optional, via FlexSPI2)
```

**Hardware Timers — GPT (General Purpose Timer):**

```c
#include "imxrt.h"  // Teensy core register definitions

// GPT1: 32-bit timer with capture/compare, clock up to 150MHz
void gpt1_init(uint32_t period_us) {
    // 1. Enable clock gate
    CCM_CCGR1 |= CCM_CCGR1_GPT1_BUS(CCM_CCGR_ON) |
                  CCM_CCGR1_GPT1_SERIAL(CCM_CCGR_ON);

    // 2. Reset and configure
    GPT1_CR = 0;                      // Disable first
    GPT1_CR = GPT_CR_SWR;            // Software reset
    while (GPT1_CR & GPT_CR_SWR);    // Wait for reset

    // 3. Clock source: peripheral clock = 150MHz
    //    Prescaler: /150 = 1MHz tick (1µs resolution)
    GPT1_CR = GPT_CR_CLKSRC(1);      // Peripheral clock
    GPT1_PR = 149;                    // Prescaler /150

    // 4. Set compare value for desired period
    GPT1_OCR1 = period_us - 1;       // Output compare register 1

    // 5. Enable compare interrupt
    GPT1_IR = GPT_IR_OF1IE;          // Output compare 1 interrupt
    NVIC_ENABLE_IRQ(IRQ_GPT1);
    NVIC_SET_PRIORITY(IRQ_GPT1, 32); // Priority 32 (0=highest)

    // 6. Enable timer (restart mode: resets on compare match)
    GPT1_CR |= GPT_CR_EN | GPT_CR_FRR; // FRR=0 for restart mode
}

void gpt1_isr(void) {
    GPT1_SR = GPT_SR_OF1;  // Clear interrupt flag (W1C)
    // Your periodic code here — runs every period_us microseconds
    digitalToggleFast(13);  // Toggle LED
}

// PIT (Periodic Interrupt Timer) — simpler, 4 channels
void pit_init(uint8_t channel, uint32_t period_us) {
    CCM_CCGR1 |= CCM_CCGR1_PIT(CCM_CCGR_ON);
    PIT_MCR = 0;  // Enable PIT module

    // PIT clock = 24MHz (from OSC)
    uint32_t cycles = 24 * period_us - 1;

    volatile uint32_t *ldval = &PIT_LDVAL0 + (channel * 4);
    volatile uint32_t *tctrl = &PIT_TCTRL0 + (channel * 4);

    *ldval = cycles;
    *tctrl = PIT_TCTRL_TIE | PIT_TCTRL_TEN;  // Enable timer + interrupt

    // Enable NVIC (PIT channels 0-3 share 4 IRQ lines)
    NVIC_ENABLE_IRQ(IRQ_PIT + channel);
}
```

**Timer comparison on i.MX RT1062:**
| Timer | Bits | Channels | Clock | Best for |
|-------|------|----------|-------|----------|
| GPT | 32-bit | 2 (GPT1, GPT2) | Up to 150MHz | Long periods, capture |
| PIT | 32-bit | 4 | 24MHz fixed | Simple periodic interrupts |
| TMR (Quad) | 16-bit | 4×4=16 | Configurable | PWM, quadrature encoder |
| FlexPWM | 16-bit | 4 modules | Up to 150MHz | Motor control, center-aligned PWM |

Teensy 4.1 specific: use `IntervalTimer` class for simplified access, but bare-metal gives you full control over DMA triggers and chained timers."""}
        ]
    },
]


EMBEDDED_KEYWORDS = [
    "arm", "cortex", "cortex-m", "cortex-a", "stm32", "nrf52", "nrf53",
    "samd", "sam", "atsamd", "teensy", "imxrt", "i.mx",
    "esp32", "esp-idf", "esp8266", "espressif",
    "risc-v", "riscv", "sifive", "hifive", "gd32v",
    "raspberry pi", "bcm2835", "bcm2711", "bcm2712",
    "bare metal", "bare-metal", "startup", "linker script", "vector table",
    "cmsis", "hal driver", "ll driver", "register",
    "dma", "interrupt", "isr", "nvic", "timer", "pwm", "adc", "dac",
    "spi", "i2c", "uart", "usart", "can", "gpio",
    "bootloader", "firmware", "flash", "eeprom",
    "freertos", "rtos", "scheduler", "semaphore", "mutex",
    "low power", "sleep", "deep sleep", "wfi", "wfe",
    "jtag", "swd", "openocd", "gdb", "debug",
    "assembly", "thumb", "arm asm",
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert embedded systems datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. STM32 HAL code (29.7k rows)
    # Columns: id, instruction, input, output, category
    print("  Downloading MuratKomurcu/stm32-hal-dataset...")
    try:
        ds = load_dataset("MuratKomurcu/stm32-hal-dataset", split="train", streaming=True)
        count = 0
        for row in ds:
            instruction = row.get("instruction", "")
            inp = row.get("input", "")
            output = row.get("output", "")
            if not output or len(output) < 50:
                continue
            question = inp if inp else instruction
            if not question:
                continue
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question.strip()},
                    {"from": "gpt", "value": f"```c\n{output.strip()[:4000]}\n```"},
                ]
            })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} STM32 HAL examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. ESP-IDF documentation (text)
    print("  Downloading gouthamsk/esp_idf_text...")
    try:
        ds = load_dataset("gouthamsk/esp_idf_text", split="train", streaming=True)
        count = 0
        for row in ds:
            text = row.get("text", "")
            if not text or len(text) < 100:
                continue
            # Use first line or sentence as question
            first_line = text.strip().split('\n')[0].strip()
            if len(first_line) > 20:
                question = f"Explain this ESP-IDF concept: {first_line[:100]}"
            else:
                question = "Explain this ESP-IDF documentation."
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": text.strip()[:4000]},
                ]
            })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} ESP-IDF doc examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. ESP-IDF chunked documentation (MQTT, TLS, HTTP, etc.)
    print("  Downloading gouthamsk/esp_idf_chunked_data...")
    try:
        ds = load_dataset("gouthamsk/esp_idf_chunked_data", split="train", streaming=True)
        count = 0
        for row in ds:
            data = row.get("data", "") or row.get("text", "")
            if not data or len(data) < 100:
                continue
            first_line = data.strip().split('\n')[0].strip()
            question = f"Explain this ESP-IDF topic: {first_line[:100]}" if len(first_line) > 15 else "Explain this ESP-IDF documentation."
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": data.strip()[:4000]},
                ]
            })
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} ESP-IDF chunked doc examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 4. Electronics StackExchange (ARM/embedded filter)
    # Columns: Id, Tags, Answer, Body, Title, CreationDate
    print("  Downloading bshada/electronics.stackexchange.com (embedded filter)...")
    try:
        ds = load_dataset("bshada/electronics.stackexchange.com", split="train", streaming=True)
        count = 0
        for row in ds:
            title = row.get("Title", "")
            body = row.get("Body", "")
            answer = row.get("Answer", "")
            tags = row.get("Tags", "")
            if not title or not answer or len(answer) < 100:
                continue
            combined = (title + " " + body + " " + answer + " " + tags).lower()
            if not any(kw in combined for kw in EMBEDDED_KEYWORDS):
                continue
            question = re.sub(r'<[^>]+>', '', title + "\n" + body).strip()
            answer_clean = re.sub(r'<[^>]+>', '', answer).strip()
            if len(answer_clean) < 80:
                continue
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question[:1000]},
                    {"from": "gpt", "value": answer_clean[:4000]},
                ]
            })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Electronics SE (embedded) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 5. LeetCode Assembly (ARM32 + ARM64 variants)
    # Columns: id, problem_id, problem_title, difficulty, c_source, architecture, optimization, compiler, assembly
    print("  Downloading ronantakizawa/leetcode-assembly (ARM filter)...")
    try:
        ds = load_dataset("ronantakizawa/leetcode-assembly", split="train", streaming=True)
        count = 0
        for row in ds:
            arch = row.get("architecture", "")
            if arch not in ("aarch64", "arm"):
                continue
            assembly = row.get("assembly", "")
            c_source = row.get("c_source", "")
            title = row.get("problem_title", "")
            optim = row.get("optimization", "")
            if not assembly or len(assembly) < 20:
                continue
            question = f"Compile this C function to {arch} assembly ({optim}):\n```c\n{c_source.strip()[:500]}\n```" if c_source else f"Write {arch} assembly for: {title}"
            answer = f"```asm\n; {title} — {arch} {optim}\n{assembly.strip()[:4000]}\n```"
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": answer},
                ]
            })
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} ARM assembly examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 6. STEM-AI Electrical Engineering (embedded filter)
    print("  Downloading STEM-AI-mtl/Electrical-engineering (embedded filter)...")
    try:
        ds = load_dataset("STEM-AI-mtl/Electrical-engineering", split="train", streaming=True)
        count = 0
        for row in ds:
            question = row.get("question", "") or row.get("instruction", "") or row.get("title", "")
            answer = row.get("answer", "") or row.get("output", "") or row.get("response", "")
            if not question or not answer or len(answer) < 80:
                continue
            combined = (question + " " + answer).lower()
            if not any(kw in combined for kw in EMBEDDED_KEYWORDS):
                continue
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question.strip()},
                    {"from": "gpt", "value": answer.strip()},
                ]
            })
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} STEM-AI embedded examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(description="Build embedded ARM/ESP32/RISC-V fine-tuning dataset")
    parser.add_argument("--with-hf", action="store_true", help="Include HuggingFace datasets")
    parser.add_argument("--max-samples", type=int, default=2000, help="Max HF samples per source")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "embedded_chat.jsonl")

    all_samples = list(SEED_EXAMPLES)
    print(f"  {len(SEED_EXAMPLES)} seed examples")

    if args.with_hf:
        hf_samples = build_from_huggingface(args.max_samples)
        all_samples.extend(hf_samples)

    with open(output_path, "w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n  Wrote {len(all_samples)} examples to {output_path}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")
    if not args.with_hf:
        print(f"\n  To enrich: python build_embedded_dataset.py --with-hf --max-samples 2000")


if __name__ == "__main__":
    main()
