"""Generate Assembly Language training dataset — 5 architectures."""

import json
import time
import os
import httpx
import random

MASCARADE_URL = os.environ.get("MASCARADE_URL", "http://192.168.0.119:8100/v1/chat/completions")
MASCARADE_KEY = os.environ.get("MASCARADE_API_KEY", "aa441ffe110b493ecc08c7d8936fdf8f020986c72afc098f")
MODEL = os.environ.get("MODEL", "codestral:codestral-latest")
OUTPUT = "finetune/datasets/asm_assembly.jsonl"

CATEGORIES = [
    {
        "name": "ARM Cortex-M Thumb2",
        "count": 300,
        "system": "You are an expert ARM Cortex-M assembly programmer. You write production-grade Thumb2 assembly for STM32, nRF52, and SAMD microcontrollers.",
        "topics": [
            "Write a startup.s file for {mcu} with vector table, reset handler, and stack initialization",
            "Write ARM Thumb2 assembly to configure {peripheral} on {mcu}",
            "Write a linker script (.ld) for {mcu} with {ram}KB RAM and {flash}KB Flash",
            "Implement a {function} in ARM assembly using Thumb2 instructions",
            "Write NVIC interrupt configuration in assembly for {interrupt} on Cortex-M4",
            "Implement {algo} in ARM Cortex-M assembly optimized for speed",
            "Write a context switch routine in ARM assembly for a simple RTOS",
            "Explain the ARM Cortex-M register map and write assembly to save/restore context",
            "Write ARM assembly to configure the MPU (Memory Protection Unit) for {region}",
            "Implement DMA transfer setup in ARM assembly for {peripheral}",
            "Write ARM assembly for SysTick timer configuration at {freq}Hz",
            "Implement fault handler in ARM assembly (HardFault, MemManage, BusFault)",
            "Write ARM inline assembly in C for {operation} using __asm volatile",
            "Implement DSP multiply-accumulate in ARM Cortex-M4 assembly using SIMD instructions",
            "Write bootloader entry point in ARM assembly with flash unlock sequence",
        ],
    },
    {
        "name": "AVR ATmega/ATtiny",
        "count": 250,
        "system": "You are an expert AVR assembly programmer. You write assembly for ATmega328P, ATtiny85, ATtiny13, and other AVR microcontrollers using avr-as/avr-gcc.",
        "topics": [
            "Write AVR assembly for ATmega328P to blink an LED on {port} at {freq}Hz",
            "Implement UART TX/RX in AVR assembly for ATmega328P at {baud} baud",
            "Write AVR assembly interrupt handler for {interrupt} on ATmega328P",
            "Implement SPI master in AVR assembly for ATmega328P",
            "Write AVR assembly for ATtiny85 to generate PWM on {pin}",
            "Implement I2C (TWI) communication in AVR assembly",
            "Write AVR assembly to read ADC on ATmega328P channel {channel}",
            "Implement software UART in AVR assembly for ATtiny13 (no hardware UART)",
            "Write AVR assembly timer configuration for Timer{n} in {mode} mode",
            "Implement watchdog timer setup in AVR assembly",
            "Write AVR assembly for EEPROM read/write on ATmega328P",
            "Implement sleep mode entry/exit in AVR assembly for power saving",
            "Write AVR assembly to configure external interrupts INT0/INT1",
            "Explain AVR register file (r0-r31, SREG, SP) and write a delay loop",
            "Implement {algo} in AVR assembly optimized for ATtiny (limited registers)",
        ],
    },
    {
        "name": "RISC-V RV32I/RV64",
        "count": 250,
        "system": "You are an expert RISC-V assembly programmer. You write assembly for RV32I, RV32IM, RV64I cores including GD32V, CH32V, and SiFive boards.",
        "topics": [
            "Write RISC-V RV32I assembly for a bare-metal startup (crt0.s) with trap vector",
            "Implement {function} in RISC-V assembly using only RV32I base instructions",
            "Write RISC-V linker script for {mcu} with {ram}KB SRAM",
            "Implement RISC-V CSR access in assembly (mstatus, mtvec, mcause, mepc)",
            "Write RISC-V trap handler in assembly for exceptions and interrupts",
            "Implement multiply/divide in RISC-V assembly without M extension",
            "Write RISC-V assembly for PLIC (Platform-Level Interrupt Controller) setup",
            "Implement RISC-V atomic operations using A extension (lr.w/sc.w)",
            "Write RISC-V assembly for timer interrupt using mtime/mtimecmp",
            "Implement context switch in RISC-V assembly for multitasking",
            "Write RISC-V assembly to configure PMP (Physical Memory Protection)",
            "Implement floating-point operations in RISC-V F extension assembly",
            "Write CH32V003 startup assembly with PFIC interrupt controller",
            "Implement {algo} in RISC-V compressed (C extension) instructions",
            "Write RISC-V assembly for SPI/I2C peripheral on GD32VF103",
        ],
    },
    {
        "name": "x86 NASM/GAS",
        "count": 250,
        "system": "You are an expert x86/x86_64 assembly programmer. You write assembly in both NASM and GAS syntax for Linux and bare-metal, including SIMD (SSE, AVX).",
        "topics": [
            "Write x86_64 NASM assembly for {syscall} system call on Linux",
            "Implement {function} in x86_64 assembly following System V ABI calling convention",
            "Write x86 NASM assembly for a bootloader that prints a message (512 bytes, MBR)",
            "Implement {algo} using SSE/SSE2 SIMD instructions in x86_64 assembly",
            "Write x86_64 assembly with AVX2 for {operation} on float arrays",
            "Implement string operations (strlen, memcpy, strcmp) in x86_64 NASM",
            "Write x86 GAS syntax (.intel_syntax noprefix) for {function}",
            "Implement x86_64 inline assembly in C using asm volatile for {operation}",
            "Write x86 assembly for protected mode transition (real mode to protected mode)",
            "Implement a simple x86 interrupt handler (IDT setup + ISR)",
            "Write x86_64 assembly for mutex/spinlock using LOCK CMPXCHG",
            "Implement x86 CPUID detection in assembly (features, vendor string)",
            "Write x86_64 NASM macro for {pattern}",
            "Implement {algo} using AVX-512 instructions",
            "Write x86 assembly for paging setup (4-level page tables, CR3)",
        ],
    },
    {
        "name": "ESP32 Xtensa / ULP",
        "count": 150,
        "system": "You are an expert ESP32 assembly programmer. You write Xtensa LX6/LX7 assembly and ULP (Ultra Low Power) coprocessor assembly for ESP32/ESP32-S2/ESP32-S3.",
        "topics": [
            "Write ESP32 ULP assembly to read ADC and wake main CPU when threshold exceeded",
            "Implement ULP assembly program for GPIO monitoring during deep sleep",
            "Write ESP32 Xtensa inline assembly in C for {operation}",
            "Implement ESP32 ULP timer-based periodic measurement in assembly",
            "Write ULP assembly for I2C sensor reading (bit-banged) during deep sleep",
            "Implement ESP32 ULP assembly with RTC memory access for data logging",
            "Write ESP32-S2 ULP-RISC-V assembly (different from Xtensa ULP)",
            "Implement ESP32 Xtensa assembly for fast interrupt handler (level 1-5)",
            "Write ESP32 ULP assembly to count pulses on GPIO during deep sleep",
            "Explain ESP32 ULP instruction set (ALU, branch, I/O, sleep) with examples",
            "Write ESP32 ULP assembly for capacitive touch detection during sleep",
            "Implement ESP32 windowed register ABI in Xtensa assembly",
        ],
    },
]

VARS = {
    "mcu": ["STM32F103", "STM32F407", "STM32L476", "STM32H743", "nRF52840", "SAMD21", "SAMD51", "RP2040"],
    "peripheral": ["USART1", "SPI1", "I2C1", "TIM2", "ADC1", "DMA1", "GPIO", "RTC"],
    "ram": ["20", "64", "128", "256", "512", "1024"],
    "flash": ["64", "128", "256", "512", "1024", "2048"],
    "function": ["memcpy", "memset", "strlen", "CRC32", "SHA256 round", "FIR filter", "PID controller", "FFT butterfly"],
    "interrupt": ["EXTI0", "TIM2_IRQn", "USART1_IRQn", "DMA1_Stream0", "SysTick", "PendSV"],
    "algo": ["bubble sort", "binary search", "CRC16", "LFSR", "bit reversal", "population count", "leading zeros"],
    "freq": ["1", "10", "100", "1000", "48000000", "72000000", "168000000"],
    "region": ["flash read-only", "SRAM read-write", "peripheral no-execute", "stack guard"],
    "operation": ["bit manipulation", "atomic increment", "endian swap", "saturating add", "count leading zeros"],
    "port": ["PORTB pin 5", "PORTD pin 7", "PORTC pin 3"],
    "baud": ["9600", "115200", "1000000"],
    "pin": ["PB0 (OC0A)", "PB1 (OC1A)", "PB3 (OC2A)"],
    "channel": ["0", "1", "5", "ADC_TEMPERATURE"],
    "n": ["0", "1", "2"],
    "mode": ["CTC", "Fast PWM", "Phase Correct PWM", "Normal"],
    "syscall": ["write", "read", "open", "mmap", "fork", "execve", "socket", "epoll_ctl"],
    "pattern": ["function prologue/epilogue", "loop unrolling", "conditional move", "stack frame setup"],
}


def fill_template(template):
    result = template
    for key, values in VARS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    return result


def generate_qa(category):
    topic = fill_template(random.choice(category["topics"]))
    try:
        r = httpx.Client(timeout=60).post(MASCARADE_URL, headers={
            "Authorization": f"Bearer {MASCARADE_KEY}",
            "Content-Type": "application/json",
        }, json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": category["system"]},
                {"role": "user", "content": topic + "\n\nProvide complete, commented assembly code. Explain each instruction."},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        })
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"]
        if len(answer) > 100:
            return {
                "conversations": [
                    {"from": "system", "value": category["system"]},
                    {"from": "human", "value": topic},
                    {"from": "gpt", "value": answer},
                ],
                "domain": "assembly",
                "category": category["name"],
                "source": "mascarade-codestral-distillation",
            }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CATEGORIES)
    print(f"=== ASM Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs across 5 architectures\n")

    os.makedirs(os.path.dirname(OUTPUT) if os.path.dirname(OUTPUT) else ".", exist_ok=True)
    total = 0
    errors = 0

    with open(OUTPUT, "w") as f:
        for cat in CATEGORIES:
            print(f"\n=== {cat['name']} ({cat['count']} pairs) ===")
            cat_count = 0
            for i in range(cat["count"]):
                result = generate_qa(cat)
                if result:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                    cat_count += 1
                    total += 1
                else:
                    errors += 1
                if (i + 1) % 25 == 0:
                    print(f"  [{i+1}/{cat['count']}] generated={cat_count} errors={errors}")
                time.sleep(0.5)
            print(f"  DONE: {cat_count} pairs")

    print(f"\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    sz = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0
    print(f"Size: {sz / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
