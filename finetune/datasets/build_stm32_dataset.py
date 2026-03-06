#!/usr/bin/env python3
"""Build fine-tuning dataset for STM32/firmware/embedded domain.

Sources:
  - MuratKomurcu/stm32-hal-dataset (HuggingFace)
  - Hand-crafted seed examples covering HAL, LL, ISR, DMA, RTOS, ASM

Output: ShareGPT-format JSONL ready for Unsloth fine-tuning.

Usage:
  python build_stm32_dataset.py                    # Seeds only (~30 examples)
  python build_stm32_dataset.py --with-hf          # Seeds + HuggingFace dataset
  python build_stm32_dataset.py --max-samples 2000 # Limit HF samples
"""

import argparse
import json
import os

SYSTEM_PROMPT = (
    "You are an expert STM32 and ARM Cortex-M embedded systems engineer. "
    "You write production-ready C firmware using STM32 HAL/LL drivers, "
    "CMSIS, FreeRTOS, and bare-metal register-level programming. "
    "You provide complete, compilable code with proper error handling, "
    "correct register addresses, and clear technical explanations. "
    "You also write ARM Thumb-2 assembly when needed."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Configure UART2 on STM32F4 at 115200 baud with DMA reception."},
            {"from": "gpt", "value": """Here's a complete UART2 + DMA setup for STM32F4:

```c
#include "stm32f4xx_hal.h"

UART_HandleTypeDef huart2;
DMA_HandleTypeDef hdma_usart2_rx;
uint8_t rx_buffer[256];

void UART2_DMA_Init(void) {
    // 1. Enable clocks
    __HAL_RCC_USART2_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();

    // 2. GPIO: PA2=TX, PA3=RX (AF7)
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    // 3. DMA1 Stream5 Channel4 for USART2_RX
    hdma_usart2_rx.Instance = DMA1_Stream5;
    hdma_usart2_rx.Init.Channel = DMA_CHANNEL_4;
    hdma_usart2_rx.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_usart2_rx.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_usart2_rx.Init.MemInc = DMA_MINC_ENABLE;
    hdma_usart2_rx.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    hdma_usart2_rx.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    hdma_usart2_rx.Init.Mode = DMA_CIRCULAR;
    hdma_usart2_rx.Init.Priority = DMA_PRIORITY_HIGH;
    hdma_usart2_rx.Init.FIFOMode = DMA_FIFOMODE_DISABLE;
    HAL_DMA_Init(&hdma_usart2_rx);
    __HAL_LINKDMA(&huart2, hdmarx, hdma_usart2_rx);

    // 4. UART config
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    huart2.Init.WordLength = UART_WORDLENGTH_8B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_NONE;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);

    // 5. NVIC
    HAL_NVIC_SetPriority(DMA1_Stream5_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(DMA1_Stream5_IRQn);

    // 6. Start DMA reception
    HAL_UART_Receive_DMA(&huart2, rx_buffer, sizeof(rx_buffer));
}

void DMA1_Stream5_IRQHandler(void) {
    HAL_DMA_IRQHandler(&hdma_usart2_rx);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART2) {
        // Full buffer received - process rx_buffer here
    }
}

void HAL_UART_RxHalfCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART2) {
        // Half buffer received - process first half
    }
}
```

Key points:
- USART2 is on APB1 (42MHz max on F4), baud rate error is <0.1% at 115200
- DMA1 Stream5 Channel4 is the fixed mapping for USART2_RX (see reference manual Table 42)
- Circular mode allows continuous reception without re-starting DMA
- Half-complete callback lets you process data while the other half fills"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a FreeRTOS task that reads an I2C sensor (BME280) every 2 seconds and sends data to a queue."},
            {"from": "gpt", "value": """Here's a FreeRTOS task for BME280 I2C reading with queue:

```c
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "stm32f4xx_hal.h"

#define BME280_ADDR       (0x76 << 1)  // 7-bit addr shifted for HAL
#define BME280_REG_ID     0xD0
#define BME280_REG_CTRL   0xF4
#define BME280_REG_DATA   0xF7

typedef struct {
    float temperature;
    float pressure;
    float humidity;
    uint32_t timestamp;
} SensorData_t;

extern I2C_HandleTypeDef hi2c1;
QueueHandle_t xSensorQueue;

// Compensation parameters (read from BME280 at init)
static uint16_t dig_T1;
static int16_t dig_T2, dig_T3;

static HAL_StatusTypeDef bme280_read_reg(uint8_t reg, uint8_t *data, uint16_t len) {
    return HAL_I2C_Mem_Read(&hi2c1, BME280_ADDR, reg,
                            I2C_MEMADD_SIZE_8BIT, data, len, 100);
}

static HAL_StatusTypeDef bme280_write_reg(uint8_t reg, uint8_t value) {
    return HAL_I2C_Mem_Write(&hi2c1, BME280_ADDR, reg,
                             I2C_MEMADD_SIZE_8BIT, &value, 1, 100);
}

static BaseType_t bme280_init(void) {
    uint8_t id;
    if (bme280_read_reg(BME280_REG_ID, &id, 1) != HAL_OK || id != 0x60) {
        return pdFAIL;
    }
    // Read compensation data
    uint8_t calib[6];
    bme280_read_reg(0x88, calib, 6);
    dig_T1 = (calib[1] << 8) | calib[0];
    dig_T2 = (int16_t)((calib[3] << 8) | calib[2]);
    dig_T3 = (int16_t)((calib[5] << 8) | calib[4]);

    // Normal mode, oversampling x1 for T/P/H
    bme280_write_reg(0xF2, 0x01);        // ctrl_hum: oversamp x1
    bme280_write_reg(BME280_REG_CTRL, 0x27);  // ctrl_meas: T x1, P x1, normal mode
    return pdPASS;
}

static float bme280_compensate_temp(int32_t adc_T) {
    int32_t var1 = ((((adc_T >> 3) - ((int32_t)dig_T1 << 1))) * ((int32_t)dig_T2)) >> 11;
    int32_t var2 = (((((adc_T >> 4) - ((int32_t)dig_T1)) *
                      ((adc_T >> 4) - ((int32_t)dig_T1))) >> 12) *
                    ((int32_t)dig_T3)) >> 14;
    int32_t t_fine = var1 + var2;
    return (float)((t_fine * 5 + 128) >> 8) / 100.0f;
}

void vSensorTask(void *pvParameters) {
    (void)pvParameters;

    if (bme280_init() != pdPASS) {
        vTaskDelete(NULL);
        return;
    }

    SensorData_t data;
    uint8_t raw[8];

    for (;;) {
        if (bme280_read_reg(BME280_REG_DATA, raw, 8) == HAL_OK) {
            int32_t adc_T = ((int32_t)raw[3] << 12) | ((int32_t)raw[4] << 4) | (raw[5] >> 4);
            data.temperature = bme280_compensate_temp(adc_T);
            data.timestamp = xTaskGetTickCount();

            xQueueSend(xSensorQueue, &data, pdMS_TO_TICKS(100));
        }
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

// Call from main() after HAL_Init and I2C init
void sensor_task_create(void) {
    xSensorQueue = xQueueCreate(10, sizeof(SensorData_t));
    configASSERT(xSensorQueue != NULL);
    xTaskCreate(vSensorTask, "Sensor", 512, NULL, tskIDLE_PRIORITY + 2, NULL);
}
```

Design notes:
- Stack size 512 words (2KB) is sufficient for I2C + float math
- Queue depth 10 prevents data loss if consumer is temporarily busy
- 100ms timeout on xQueueSend avoids blocking if queue is full
- Task priority 2 (above idle) — adjust based on your system
- BME280 compensation follows the datasheet algorithm exactly"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write ARM Thumb-2 assembly for a fast memcpy with 32-bit aligned transfers on Cortex-M4."},
            {"from": "gpt", "value": """Here's an optimized aligned memcpy in Thumb-2 assembly for Cortex-M4:

```asm
    .syntax unified
    .thumb
    .section .text
    .global fast_memcpy
    .type fast_memcpy, %function

@ void fast_memcpy(void *dst, const void *src, uint32_t len)
@ r0 = dst, r1 = src, r2 = len (bytes, must be multiple of 4)
fast_memcpy:
    push    {r4-r7, lr}

    @ Handle blocks of 16 bytes (4 words) using LDM/STM
    lsrs    r3, r2, #4          @ r3 = len / 16 (number of 16-byte blocks)
    beq     .Lwords             @ skip if < 16 bytes

.Lblock16:
    ldmia   r1!, {r4-r7}        @ load 4 words from src, post-increment
    stmia   r0!, {r4-r7}        @ store 4 words to dst, post-increment
    subs    r3, r3, #1
    bne     .Lblock16

.Lwords:
    @ Handle remaining 1-3 words
    ands    r2, r2, #0x0F       @ remaining bytes (0-15)
    beq     .Ldone

.Lword_loop:
    ldr     r4, [r1], #4
    str     r4, [r0], #4
    subs    r2, r2, #4
    bgt     .Lword_loop

.Ldone:
    pop     {r4-r7, pc}         @ return (pop lr into pc)

    .size fast_memcpy, .-fast_memcpy
```

Performance analysis:
- LDM/STM with 4 registers: 5 cycles per 16 bytes on Cortex-M4 (flash, 0-wait-state)
- With flash wait states (typical at 168MHz): ~8-10 cycles per 16 bytes
- Compared to byte-by-byte: ~4x faster for aligned data
- For unaligned data, use LDRB/STRB fallback or enable UNALIGN_TRP in SCB->CCR

Calling from C:
```c
extern void fast_memcpy(void *dst, const void *src, uint32_t len);

// len MUST be multiple of 4, both pointers MUST be 4-byte aligned
fast_memcpy(dest_buf, src_buf, 256);
```

Caveats:
- No unaligned access handling — caller must ensure alignment
- No overlap detection (not memmove)
- Length must be multiple of 4; for arbitrary lengths, add byte-level tail handling"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "How to configure the ADC on STM32F4 with DMA for continuous multi-channel scanning?"},
            {"from": "gpt", "value": """Here's ADC1 multi-channel scan with DMA on STM32F4:

```c
#include "stm32f4xx_hal.h"

#define ADC_CHANNELS  4
ADC_HandleTypeDef hadc1;
DMA_HandleTypeDef hdma_adc1;
volatile uint16_t adc_values[ADC_CHANNELS];  // PA0, PA1, PA4, PA5

void ADC_MultiChannel_Init(void) {
    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_DMA2_CLK_ENABLE();

    // GPIO: analog input (no pull, no alternate function)
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_4 | GPIO_PIN_5;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    // DMA2 Stream0 Channel0 for ADC1
    hdma_adc1.Instance = DMA2_Stream0;
    hdma_adc1.Init.Channel = DMA_CHANNEL_0;
    hdma_adc1.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_adc1.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_adc1.Init.MemInc = DMA_MINC_ENABLE;
    hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    hdma_adc1.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
    hdma_adc1.Init.Mode = DMA_CIRCULAR;
    hdma_adc1.Init.Priority = DMA_PRIORITY_MEDIUM;
    HAL_DMA_Init(&hdma_adc1);
    __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);

    // ADC1 configuration
    hadc1.Instance = ADC1;
    hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;  // 21MHz
    hadc1.Init.Resolution = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode = ENABLE;           // Scan all channels
    hadc1.Init.ContinuousConvMode = ENABLE;     // Continuous mode
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.NbrOfConversion = ADC_CHANNELS;
    hadc1.Init.DMAContinuousRequests = ENABLE;
    hadc1.Init.EOCSelection = ADC_EOC_SEQ_CONV;
    HAL_ADC_Init(&hadc1);

    // Channel configuration: PA0=CH0, PA1=CH1, PA4=CH4, PA5=CH5
    ADC_ChannelConfTypeDef ch = {0};
    uint32_t channels[] = {ADC_CHANNEL_0, ADC_CHANNEL_1, ADC_CHANNEL_4, ADC_CHANNEL_5};
    for (int i = 0; i < ADC_CHANNELS; i++) {
        ch.Channel = channels[i];
        ch.Rank = i + 1;
        ch.SamplingTime = ADC_SAMPLETIME_84CYCLES;  // ~4us per channel
        HAL_ADC_ConfigChannel(&hadc1, &ch);
    }

    // Start ADC+DMA
    HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_values, ADC_CHANNELS);
}

// Read values anywhere in your code:
float get_voltage(uint8_t channel) {
    return (float)adc_values[channel] * 3.3f / 4095.0f;
}
```

Timing: with 84-cycle sampling + 12-cycle conversion at 21MHz ADC clock, each channel takes ~4.6us. Full scan of 4 channels: ~18.4us → ~54kHz effective sample rate per channel.

DMA circular mode means `adc_values[]` is always up-to-date without CPU intervention."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Implement a hardware timer interrupt on STM32F4 that toggles an LED at exactly 1kHz."},
            {"from": "gpt", "value": """Timer interrupt at 1kHz using TIM2 on STM32F4 (assuming 84MHz APB1 clock):

```c
#include "stm32f4xx_hal.h"

TIM_HandleTypeDef htim2;

void TIM2_Init_1kHz(void) {
    __HAL_RCC_TIM2_CLK_ENABLE();

    // TIM2 on APB1 = 84MHz (when APB1 prescaler != 1, timer clock is 2x APB1)
    // Target: 1kHz interrupt
    // Prescaler: 84 → timer clock = 84MHz / 84 = 1MHz
    // Period: 1000 → 1MHz / 1000 = 1kHz
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 84 - 1;      // PSC register (0-based)
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 1000 - 1;        // ARR register (0-based)
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_Base_Init(&htim2);

    // Enable update interrupt
    HAL_NVIC_SetPriority(TIM2_IRQn, 3, 0);  // Priority 3
    HAL_NVIC_EnableIRQ(TIM2_IRQn);

    // Start timer with interrupt
    HAL_TIM_Base_Start_IT(&htim2);
}

void TIM2_IRQHandler(void) {
    HAL_TIM_IRQHandler(&htim2);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
    if (htim->Instance == TIM2) {
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);  // Toggle LED on PA5
    }
}
```

Calculation verification:
- APB1 timer clock = 84MHz (on STM32F407 at 168MHz HCLK)
- PSC = 83 → counter clock = 84MHz / (83+1) = 1MHz (1us resolution)
- ARR = 999 → overflow every (999+1) × 1us = 1ms → 1kHz

Accuracy: crystal-referenced, jitter < 1 cycle of AHB clock (~6ns). For sub-microsecond timing, use TIM2 in 32-bit mode (ARR up to 2^32-1)."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a SPI driver for STM32 to communicate with a W25Q128 flash memory. Include read, write, and erase functions."},
            {"from": "gpt", "value": """W25Q128 SPI flash driver for STM32:

```c
#include "stm32f4xx_hal.h"
#include <string.h>

extern SPI_HandleTypeDef hspi1;

#define W25Q_CS_LOW()   HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET)
#define W25Q_CS_HIGH()  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET)

// W25Q128 commands
#define W25Q_WRITE_ENABLE    0x06
#define W25Q_WRITE_DISABLE   0x04
#define W25Q_READ_STATUS1    0x05
#define W25Q_READ_DATA       0x03
#define W25Q_PAGE_PROGRAM    0x02
#define W25Q_SECTOR_ERASE    0x20  // 4KB
#define W25Q_BLOCK_ERASE_32K 0x52
#define W25Q_BLOCK_ERASE_64K 0xD8
#define W25Q_CHIP_ERASE      0xC7
#define W25Q_READ_ID         0x9F

#define W25Q_PAGE_SIZE       256
#define W25Q_SECTOR_SIZE     4096

static void w25q_write_enable(void) {
    uint8_t cmd = W25Q_WRITE_ENABLE;
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    W25Q_CS_HIGH();
}

static void w25q_wait_busy(void) {
    uint8_t cmd = W25Q_READ_STATUS1;
    uint8_t status;
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    do {
        HAL_SPI_Receive(&hspi1, &status, 1, 100);
    } while (status & 0x01);  // BUSY bit
    W25Q_CS_HIGH();
}

uint32_t w25q_read_id(void) {
    uint8_t cmd = W25Q_READ_ID;
    uint8_t id[3];
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    HAL_SPI_Receive(&hspi1, id, 3, 100);
    W25Q_CS_HIGH();
    return (id[0] << 16) | (id[1] << 8) | id[2];
    // Expected: 0xEF4018 for W25Q128
}

void w25q_read(uint32_t addr, uint8_t *buf, uint32_t len) {
    uint8_t cmd[4] = {
        W25Q_READ_DATA,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
    };
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, cmd, 4, 100);
    HAL_SPI_Receive(&hspi1, buf, len, 1000);
    W25Q_CS_HIGH();
}

// Write up to 256 bytes within a single page
static void w25q_page_program(uint32_t addr, const uint8_t *data, uint16_t len) {
    if (len == 0 || len > W25Q_PAGE_SIZE) return;

    w25q_write_enable();

    uint8_t cmd[4] = {
        W25Q_PAGE_PROGRAM,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
    };
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, cmd, 4, 100);
    HAL_SPI_Transmit(&hspi1, (uint8_t *)data, len, 1000);
    W25Q_CS_HIGH();

    w25q_wait_busy();  // Page program: typ 0.7ms, max 3ms
}

void w25q_write(uint32_t addr, const uint8_t *data, uint32_t len) {
    while (len > 0) {
        // Bytes remaining in current page
        uint16_t page_remaining = W25Q_PAGE_SIZE - (addr % W25Q_PAGE_SIZE);
        uint16_t chunk = (len < page_remaining) ? len : page_remaining;

        w25q_page_program(addr, data, chunk);

        addr += chunk;
        data += chunk;
        len -= chunk;
    }
}

void w25q_erase_sector(uint32_t addr) {
    addr &= ~(W25Q_SECTOR_SIZE - 1);  // Align to 4KB boundary
    w25q_write_enable();

    uint8_t cmd[4] = {
        W25Q_SECTOR_ERASE,
        (addr >> 16) & 0xFF,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
    };
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, cmd, 4, 100);
    W25Q_CS_HIGH();

    w25q_wait_busy();  // Sector erase: typ 45ms, max 400ms
}

void w25q_erase_chip(void) {
    w25q_write_enable();
    uint8_t cmd = W25Q_CHIP_ERASE;
    W25Q_CS_LOW();
    HAL_SPI_Transmit(&hspi1, &cmd, 1, 100);
    W25Q_CS_HIGH();
    w25q_wait_busy();  // Chip erase: typ 40s, max 200s for 128Mbit
}
```

Important notes:
- W25Q128 has 16MB (128Mbit) organized in 256-byte pages, 4KB sectors, 64KB blocks
- Page program can only write within a single 256-byte page boundary
- `w25q_write()` handles cross-page writes automatically
- Flash must be erased (0xFF) before programming — erase sets bits to 1, program clears to 0
- SPI clock: up to 104MHz for standard read (mode 0 or 3)"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "How do I set up the STM32 MPU (Memory Protection Unit) to protect a critical memory region?"},
            {"from": "gpt", "value": """Here's how to configure the MPU on Cortex-M4/M7 to protect a critical data region:

```c
#include "stm32f4xx_hal.h"

void MPU_Config(void) {
    // Disable MPU before configuration
    HAL_MPU_Disable();

    MPU_Region_InitTypeDef mpu_init = {0};

    // Region 0: Protect critical config struct at 0x20000000 (first 1KB of SRAM)
    // Read-only for unprivileged code, full access for privileged
    mpu_init.Enable = MPU_REGION_ENABLE;
    mpu_init.Number = MPU_REGION_NUMBER0;
    mpu_init.BaseAddress = 0x20000000;
    mpu_init.Size = MPU_REGION_SIZE_1KB;
    mpu_init.SubRegionDisable = 0x00;      // All sub-regions enabled
    mpu_init.TypeExtField = MPU_TEX_LEVEL0;
    mpu_init.AccessPermission = MPU_REGION_PRIV_RW_URO;  // Privileged RW, Unprivileged RO
    mpu_init.DisableExec = MPU_INSTRUCTION_ACCESS_DISABLE;  // No code execution
    mpu_init.IsShareable = MPU_ACCESS_NOT_SHAREABLE;
    mpu_init.IsCacheable = MPU_ACCESS_CACHEABLE;
    mpu_init.IsBufferable = MPU_ACCESS_BUFFERABLE;
    HAL_MPU_ConfigRegion(&mpu_init);

    // Region 1: Stack guard — make last 32 bytes of stack non-accessible
    // Triggers MemManage fault on stack overflow
    mpu_init.Number = MPU_REGION_NUMBER1;
    mpu_init.BaseAddress = 0x20004FE0;     // End of 20KB SRAM - 32 bytes
    mpu_init.Size = MPU_REGION_SIZE_32B;
    mpu_init.AccessPermission = MPU_REGION_NO_ACCESS;  // Any access = fault
    mpu_init.DisableExec = MPU_INSTRUCTION_ACCESS_DISABLE;
    mpu_init.IsCacheable = MPU_ACCESS_NOT_CACHEABLE;
    mpu_init.IsBufferable = MPU_ACCESS_NOT_BUFFERABLE;
    HAL_MPU_ConfigRegion(&mpu_init);

    // Enable MPU with default memory map for undefined regions
    HAL_MPU_Enable(MPU_PRIVILEGED_DEFAULT);
}

// MemManage fault handler — called when MPU violation occurs
void MemManage_Handler(void) {
    uint32_t cfsr = SCB->CFSR;
    uint32_t mmfar = SCB->MMFAR;

    if (cfsr & SCB_CFSR_MMARVALID_Msk) {
        // MMFAR contains the faulting address
        // Log: "MPU violation at address 0x%08X", mmfar
    }
    if (cfsr & SCB_CFSR_DACCVIOL_Msk) {
        // Data access violation
    }
    if (cfsr & SCB_CFSR_IACCVIOL_Msk) {
        // Instruction access violation
    }

    // In production: log fault, reset, or enter safe state
    NVIC_SystemReset();
}
```

MPU region size must be a power of 2 (32B to 4GB). Base address must be aligned to region size. Cortex-M4 supports 8 regions, M7 supports 8 or 16.

Use case: protect calibration data, cryptographic keys, or safety-critical state from accidental corruption by application code."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Implement a CAN bus driver for STM32F4 to send and receive messages."},
            {"from": "gpt", "value": """CAN1 driver for STM32F4 with TX/RX and filtering:

```c
#include "stm32f4xx_hal.h"

CAN_HandleTypeDef hcan1;

void CAN1_Init(void) {
    __HAL_RCC_CAN1_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    // PB8=CAN1_RX, PB9=CAN1_TX (AF9)
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF9_CAN1;
    HAL_GPIO_Init(GPIOB, &gpio);

    // CAN config: 500kbps at 42MHz APB1
    // Bit time = Sync + BS1 + BS2 = 1 + 11 + 2 = 14 TQ
    // BRP = 42MHz / (500k * 14) = 6
    hcan1.Instance = CAN1;
    hcan1.Init.Prescaler = 6;
    hcan1.Init.Mode = CAN_MODE_NORMAL;
    hcan1.Init.SyncJumpWidth = CAN_SJW_1TQ;
    hcan1.Init.TimeSeg1 = CAN_BS1_11TQ;
    hcan1.Init.TimeSeg2 = CAN_BS2_2TQ;
    hcan1.Init.TimeTriggeredMode = DISABLE;
    hcan1.Init.AutoBusOff = ENABLE;      // Auto recovery from bus-off
    hcan1.Init.AutoWakeUp = DISABLE;
    hcan1.Init.AutoRetransmission = ENABLE;
    hcan1.Init.ReceiveFifoLocked = DISABLE;
    hcan1.Init.TransmitFifoPriority = DISABLE;
    HAL_CAN_Init(&hcan1);

    // Filter: accept all messages in FIFO0
    CAN_FilterTypeDef filter = {0};
    filter.FilterBank = 0;
    filter.FilterMode = CAN_FILTERMODE_IDMASK;
    filter.FilterScale = CAN_FILTERSCALE_32BIT;
    filter.FilterIdHigh = 0x0000;
    filter.FilterIdLow = 0x0000;
    filter.FilterMaskIdHigh = 0x0000;    // Accept all
    filter.FilterMaskIdLow = 0x0000;
    filter.FilterFIFOAssignment = CAN_RX_FIFO0;
    filter.FilterActivation = ENABLE;
    HAL_CAN_ConfigFilter(&hcan1, &filter);

    // Enable RX interrupt
    HAL_NVIC_SetPriority(CAN1_RX0_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(CAN1_RX0_IRQn);
    HAL_CAN_ActivateNotification(&hcan1, CAN_IT_RX_FIFO0_MSG_PENDING);

    HAL_CAN_Start(&hcan1);
}

HAL_StatusTypeDef CAN_Send(uint32_t id, uint8_t *data, uint8_t len) {
    CAN_TxHeaderTypeDef header = {0};
    header.StdId = id;       // 11-bit standard ID
    header.IDE = CAN_ID_STD;
    header.RTR = CAN_RTR_DATA;
    header.DLC = len;        // 0-8 bytes

    uint32_t mailbox;
    return HAL_CAN_AddTxMessage(&hcan1, &header, data, &mailbox);
}

void CAN1_RX0_IRQHandler(void) {
    HAL_CAN_IRQHandler(&hcan1);
}

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan) {
    CAN_RxHeaderTypeDef header;
    uint8_t data[8];

    if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &header, data) == HAL_OK) {
        // Process received message
        // header.StdId = sender ID
        // header.DLC = data length
        // data[] = payload
    }
}
```

Bit timing verification for 500kbps:
- APB1 = 42MHz, BRP = 6 → TQ = 6/42MHz = 142.86ns
- Bit time = 14 × TQ = 2.0us → 500kbps ✓
- Sample point = (1 + 11) / 14 = 85.7% (recommended: 75-87.5%)

For filtered reception, set mask bits to 1 for bits that must match the filter ID."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a low-power sleep mode implementation for STM32L4 with RTC wakeup."},
            {"from": "gpt", "value": """STM32L4 Stop 2 mode with RTC wakeup alarm:

```c
#include "stm32l4xx_hal.h"

RTC_HandleTypeDef hrtc;

void RTC_Init(void) {
    __HAL_RCC_RTC_ENABLE();

    hrtc.Instance = RTC;
    hrtc.Init.HourFormat = RTC_HOURFORMAT_24;
    hrtc.Init.AsynchPrediv = 127;   // LSE 32768Hz / 128 = 256Hz
    hrtc.Init.SynchPrediv = 255;    // 256Hz / 256 = 1Hz
    hrtc.Init.OutPut = RTC_OUTPUT_DISABLE;
    HAL_RTC_Init(&hrtc);
}

void enter_stop2_with_rtc_wakeup(uint32_t seconds) {
    // 1. Get current time
    RTC_TimeTypeDef time;
    RTC_DateTypeDef date;
    HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN);
    HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN);  // Must read date after time

    // 2. Set alarm A to wake up after 'seconds'
    RTC_AlarmTypeDef alarm = {0};
    uint32_t total_secs = time.Hours * 3600 + time.Minutes * 60 + time.Seconds + seconds;
    alarm.AlarmTime.Hours = (total_secs / 3600) % 24;
    alarm.AlarmTime.Minutes = (total_secs / 60) % 60;
    alarm.AlarmTime.Seconds = total_secs % 60;
    alarm.AlarmTime.SubSeconds = 0;
    alarm.AlarmMask = RTC_ALARMMASK_DATEWEEKDAY;  // Ignore day — match H:M:S only
    alarm.AlarmSubSecondMask = RTC_ALARMSUBSECONDMASK_ALL;
    alarm.Alarm = RTC_ALARM_A;
    HAL_RTC_SetAlarm_IT(&hrtc, &alarm, RTC_FORMAT_BIN);

    // 3. Prepare for Stop 2
    HAL_SuspendTick();                    // Stop SysTick (saves ~1uA)
    __HAL_RCC_PWR_CLK_ENABLE();

    // 4. Enter Stop 2 mode
    // Current consumption: ~1.3uA (STM32L476)
    HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);

    // --- CPU stops here until RTC alarm fires ---

    // 5. Wakeup: restore clocks
    SystemClock_Config();                 // Re-init PLL (Stop mode disables it)
    HAL_ResumeTick();

    // 6. Disable alarm
    HAL_RTC_DeactivateAlarm(&hrtc, RTC_ALARM_A);
}

void RTC_Alarm_IRQHandler(void) {
    HAL_RTC_AlarmIRQHandler(&hrtc);
}

void HAL_RTC_AlarmAEventCallback(RTC_HandleTypeDef *hrtc) {
    // Wakeup event — execution continues after HAL_PWREx_EnterSTOP2Mode()
}

// Usage
void main_loop(void) {
    while (1) {
        // Do work: read sensors, transmit data...
        do_sensor_reading();
        transmit_data();

        // Sleep for 60 seconds
        enter_stop2_with_rtc_wakeup(60);
    }
}
```

Power modes comparison (STM32L4):
| Mode | Current | Wakeup time | RAM retained |
|------|---------|-------------|-------------|
| Run (80MHz) | ~10mA | — | Yes |
| Sleep | ~1mA | <1us | Yes |
| Stop 0 | ~5uA | ~5us | Yes |
| Stop 1 | ~2.5uA | ~5us | Yes |
| **Stop 2** | **~1.3uA** | **~5us** | **Yes** |
| Standby | ~0.3uA | ~50us | No (only BKP regs) |
| Shutdown | ~30nA | ~50us | No |

Stop 2 is the sweet spot: lowest current with full SRAM retention and fast wakeup."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Explain the STM32 clock tree and write the SystemClock_Config for 168MHz on STM32F407."},
            {"from": "gpt", "value": """STM32F407 clock tree and 168MHz configuration:

```
HSE (8MHz crystal)
  └─→ PLL
       ├─ PLLM = 8  → VCO input = 8/8 = 1MHz (must be 1-2MHz)
       ├─ PLLN = 336 → VCO output = 1 × 336 = 336MHz (100-432MHz)
       ├─ PLLP = 2   → SYSCLK = 336/2 = 168MHz
       └─ PLLQ = 7   → USB clock = 336/7 = 48MHz (must be 48MHz for USB)

SYSCLK (168MHz)
  ├─ AHB prescaler /1 → HCLK = 168MHz
  │   ├─ Cortex-M4 core
  │   ├─ DMA
  │   └─ Flash (5 wait states at 168MHz, 3.3V)
  ├─ APB1 prescaler /4 → PCLK1 = 42MHz (max 42MHz)
  │   ├─ TIM2-7,12-14 timers → 84MHz (2× when prescaler != 1)
  │   ├─ USART2-5, I2C, SPI2/3, CAN
  │   └─ DAC, PWR
  └─ APB2 prescaler /2 → PCLK2 = 84MHz (max 84MHz)
      ├─ TIM1,8-11 timers → 168MHz (2× when prescaler != 1)
      ├─ USART1/6, SPI1, ADC
      └─ SDIO, SYSCFG
```

```c
void SystemClock_Config(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    // Enable Power controller and set voltage regulator scale 1 (max perf)
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    // Configure HSE + PLL
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 8;     // VCO input: 8MHz / 8 = 1MHz
    osc.PLL.PLLN = 336;   // VCO output: 1MHz × 336 = 336MHz
    osc.PLL.PLLP = RCC_PLLP_DIV2;  // SYSCLK: 336 / 2 = 168MHz
    osc.PLL.PLLQ = 7;     // USB: 336 / 7 = 48MHz
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        Error_Handler();
    }

    // Configure bus clocks
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                    RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;    // HCLK = 168MHz
    clk.APB1CLKDivider = RCC_HCLK_DIV4;     // APB1 = 42MHz
    clk.APB2CLKDivider = RCC_HCLK_DIV2;     // APB2 = 84MHz

    // Flash latency: 5 wait states for 168MHz at 3.3V (see RM0090 Table 10)
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5) != HAL_OK) {
        Error_Handler();
    }
}
```

Common mistakes:
1. Wrong flash latency → hard fault or random crashes
2. PLLM must produce 1-2MHz VCO input — adjust for your crystal
3. APB1 max is 42MHz — exceeding it causes peripheral malfunction
4. Timer clocks are 2× APB clock when APB prescaler > 1"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "How to use the STM32 hardware CRC peripheral for data integrity verification?"},
            {"from": "gpt", "value": """STM32 hardware CRC32 peripheral usage:

```c
#include "stm32f4xx_hal.h"

CRC_HandleTypeDef hcrc;

void CRC_Init(void) {
    __HAL_RCC_CRC_CLK_ENABLE();
    hcrc.Instance = CRC;
    HAL_CRC_Init(&hcrc);
}

// Calculate CRC32 of a data buffer
uint32_t calculate_crc32(const uint32_t *data, uint32_t len_words) {
    return HAL_CRC_Calculate(&hcrc, (uint32_t *)data, len_words);
}

// Accumulate CRC (continue from previous calculation)
uint32_t accumulate_crc32(const uint32_t *data, uint32_t len_words) {
    return HAL_CRC_Accumulate(&hcrc, (uint32_t *)data, len_words);
}

// Practical example: verify firmware integrity at boot
#define APP_START_ADDR  0x08008000  // Application starts at 32KB offset
#define APP_SIZE        (128 * 1024) // 128KB application
#define CRC_STORED_ADDR 0x0803FFFC  // Last 4 bytes of app region

typedef enum {
    FW_VALID,
    FW_CORRUPTED,
} FirmwareStatus_t;

FirmwareStatus_t verify_firmware(void) {
    CRC_Init();

    uint32_t *app_data = (uint32_t *)APP_START_ADDR;
    uint32_t app_words = (APP_SIZE - 4) / 4;  // Exclude stored CRC

    uint32_t computed_crc = calculate_crc32(app_data, app_words);
    uint32_t stored_crc = *(volatile uint32_t *)CRC_STORED_ADDR;

    return (computed_crc == stored_crc) ? FW_VALID : FW_CORRUPTED;
}
```

Notes:
- STM32 CRC uses polynomial 0x04C11DB7 (CRC-32/MPEG-2), NOT the standard CRC-32 (Ethernet)
- Input is 32-bit words, not bytes — pad your data if needed
- Hardware CRC takes 4 AHB cycles per word (very fast, ~42M words/sec at 168MHz)
- `HAL_CRC_Calculate()` resets the CRC register first; `HAL_CRC_Accumulate()` continues
- STM32F7/H7 support configurable polynomial, initial value, and byte-level input"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a bootloader concept for STM32 that jumps to the application after CRC check."},
            {"from": "gpt", "value": """Minimal bootloader for STM32F4 with CRC verification:

```c
#include "stm32f4xx_hal.h"

#define BOOTLOADER_SIZE   0x8000      // 32KB for bootloader
#define APP_ADDR          (FLASH_BASE + BOOTLOADER_SIZE)  // 0x08008000
#define APP_SIZE_MAX      (224 * 1024) // 224KB max application

typedef void (*AppEntry_t)(void);

static void jump_to_app(uint32_t app_address) {
    // 1. Check if valid stack pointer at app_address
    //    (must point to SRAM: 0x20000000 - 0x2001FFFF for 128KB SRAM)
    uint32_t app_sp = *(volatile uint32_t *)app_address;
    if ((app_sp & 0x2FF00000) != 0x20000000) {
        return;  // Invalid stack pointer — no valid application
    }

    // 2. Get reset handler address (second word of vector table)
    uint32_t app_reset = *(volatile uint32_t *)(app_address + 4);

    // 3. Disable all interrupts
    __disable_irq();

    // 4. Deinit HAL and peripherals
    HAL_RCC_DeInit();
    HAL_DeInit();

    // 5. Reset SysTick
    SysTick->CTRL = 0;
    SysTick->LOAD = 0;
    SysTick->VAL = 0;

    // 6. Clear all pending interrupts
    for (int i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFF;  // Disable all IRQs
        NVIC->ICPR[i] = 0xFFFFFFFF;  // Clear all pending
    }

    // 7. Relocate vector table to application
    SCB->VTOR = app_address;

    // 8. Set stack pointer and jump
    __set_MSP(app_sp);
    AppEntry_t app_entry = (AppEntry_t)app_reset;
    app_entry();

    // Should never reach here
    while (1);
}

int main(void) {
    HAL_Init();
    SystemClock_Config();

    // Check for firmware update trigger (e.g., button pressed or flag in backup register)
    if (check_update_trigger()) {
        // Enter DFU/update mode
        uart_firmware_update();
    }

    // Verify application CRC
    if (verify_firmware() == FW_VALID) {
        jump_to_app(APP_ADDR);
    }

    // Application invalid — stay in bootloader
    blink_error_led();
    while (1);
}
```

Linker script for bootloader (STM32F407_BOOT.ld):
```
MEMORY {
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 32K
  RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 128K
}
```

Application linker must set `ORIGIN = 0x08008000` and in `system_stm32f4xx.c`:
```c
#define VECT_TAB_OFFSET  0x8000
```

The application's vector table must start at 0x08008000 with the initial SP value and Reset_Handler address."""}
        ]
    },
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert STM32 HAL dataset from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []
    print("  Downloading MuratKomurcu/stm32-hal-dataset...")
    try:
        ds = load_dataset("MuratKomurcu/stm32-hal-dataset", split="train", streaming=True)
        count = 0
        for row in ds:
            instruction = row.get("instruction", "")
            code = row.get("output", "") or row.get("code", "")
            if not instruction or not code or len(code) < 50:
                continue
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": instruction},
                    {"from": "gpt", "value": code},
                ]
            })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} HAL examples")
    except Exception as e:
        print(f"    Failed: {e}")
    return samples


def main():
    parser = argparse.ArgumentParser(description="Build STM32/firmware fine-tuning dataset")
    parser.add_argument("--with-hf", action="store_true", help="Include HuggingFace datasets")
    parser.add_argument("--max-samples", type=int, default=2000, help="Max HF samples")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "stm32_chat.jsonl")

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
    print(f"\n  Next: upload to HuggingFace Hub:")
    print(f"    huggingface-cli upload your-username/mascarade-stm32-dataset {output_path}")


if __name__ == "__main__":
    main()
