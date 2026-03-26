"""Generate AI on-chip training datasets — one per chip/platform."""

import json
import time
import os
import httpx
import random

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
MODEL = os.environ.get("MODEL", "devstral")
OUTPUT_DIR = "finetune/datasets"

CHIPS = [
    {
        "name": "max78000",
        "file": "ai_max78000.jsonl",
        "count": 150,
        "system": "You are an expert in Analog Devices MAX78000/MAX78002 CNN accelerator programming. You write firmware using the MSDK (Maxim SDK), configure the CNN engine, deploy quantized models, and optimize power consumption.",
        "topics": [
            "How to load and run a CNN model on MAX78000 using the MSDK",
            "Configure MAX78000 CNN accelerator for {model} inference",
            "Write MAX78000 firmware for real-time {task} at {power} power mode",
            "Quantize a {model} model for MAX78000 CNN engine (8-bit weights)",
            "MAX78000 power management: switch between active CNN and sleep modes",
            "Implement {task} on MAX78000 with camera input and CNN processing",
            "MAX78000 vs MAX78002: differences in CNN layers, memory, and performance",
            "Debug MAX78000 CNN inference: common errors and fixes",
            "MAX78000 audio classification: microphone input to CNN pipeline",
            "Optimize MAX78000 CNN model for minimum latency on {task}",
        ],
    },
    {
        "name": "syntiant",
        "file": "ai_syntiant_ndp.jsonl",
        "count": 120,
        "system": "You are an expert in Syntiant NDP120/NDP200 Neural Decision Processor programming. You deploy always-on audio AI models using the Syntiant Core 2 SDK and NDP toolkit.",
        "topics": [
            "Deploy a wake word model on Syntiant NDP120 using Core 2 SDK",
            "Configure NDP120 for multi-keyword detection with {n} keywords",
            "Syntiant NDP200 vs NDP120: architecture differences and capabilities",
            "Optimize power consumption on NDP120 for always-on {task}",
            "Train and deploy a custom wake word on Syntiant NDP using Edge Impulse",
            "NDP120 audio pipeline: PDM microphone to neural network inference",
            "Implement speaker verification on Syntiant NDP200",
            "Syntiant NDP firmware: interrupt handling and result processing",
            "Deploy a multi-model pipeline on NDP200 (wake word + command recognition)",
            "Syntiant TDK integration: sensor fusion with NDP120",
        ],
    },
    {
        "name": "ethos_u55",
        "file": "ai_arm_ethos.jsonl",
        "count": 200,
        "system": "You are an expert in Arm Ethos-U55/U65 microNPU programming. You compile models with Vela, integrate with Cortex-M55/M85, and optimize for TOPS/W efficiency.",
        "topics": [
            "Compile a TFLite model for Ethos-U55 using Vela compiler",
            "Ethos-U55 supported operators: which TFLite ops run on NPU vs CPU fallback",
            "Integrate Ethos-U55 with Cortex-M55 using CMSIS-NN and TFLite Micro",
            "Optimize {model} for Ethos-U55: operator fusion and memory planning",
            "Ethos-U55 vs Ethos-U65: performance, area, and power comparison",
            "Deploy {task} model on Alif Ensemble E7 with dual Ethos-U55",
            "Ethos-U55 memory configuration: SRAM vs external flash for model weights",
            "Write Ethos-U55 driver initialization code for custom SoC",
            "Profile Ethos-U55 inference: cycle counts, memory bandwidth, utilization",
            "Ethos-U55 on Renesas RA8: end-to-end deployment guide",
            "Ethos-U55 on Infineon PSoC Edge: setup and model deployment",
            "Vela compiler options: optimization levels, arena size, tensor allocator",
        ],
    },
    {
        "name": "kendryte",
        "file": "ai_kendryte.jsonl",
        "count": 120,
        "system": "You are an expert in Kendryte K210/K230 KPU (Knowledge Processing Unit) programming. You deploy vision and audio AI models using MaixPy, nncase compiler, and bare-metal RISC-V.",
        "topics": [
            "Deploy YOLOv5 on Kendryte K230 using nncase compiler",
            "K210 KPU programming: load and run a face detection model",
            "MaixPy on K210: camera capture to KPU inference pipeline",
            "K230 vs K210: KPU architecture, TOPS, and supported operators",
            "Quantize a {model} model for K210 KPU using nncase",
            "K210 bare-metal RISC-V: direct KPU register programming",
            "Implement real-time {task} on K230 with dual RISC-V cores",
            "K210 audio classification using KPU and I2S microphone",
            "Optimize K230 model for minimum latency: tiling and pipelining",
            "K210 power modes: KPU active vs sleep, FPIOA configuration",
        ],
    },
    {
        "name": "nxp_neutron",
        "file": "ai_nxp_neutron.jsonl",
        "count": 150,
        "system": "You are an expert in NXP MCX-N series with eIQ Neutron NPU. You deploy models using eIQ toolkit, Glow compiler, and MCUXpresso SDK.",
        "topics": [
            "Deploy a TFLite model on NXP MCX-N947 using eIQ Neutron NPU",
            "eIQ toolkit workflow: train, optimize, deploy on MCX-N",
            "Glow compiler for NXP Neutron NPU: model compilation and optimization",
            "MCX-N947 Neutron NPU: 4 TOPS architecture and memory hierarchy",
            "Compare NXP Neutron NPU vs Arm Ethos-U55 for {task}",
            "NXP eIQ inference engine: TFLite Micro vs Glow backend on MCX-N",
            "Deploy {task} model on MCX-N with sensor input and NPU processing",
            "MCX-N power optimization: NPU clock gating and voltage scaling",
            "NXP MCUXpresso ML tools: model profiler and benchmark suite",
            "Implement multi-model inference on MCX-N Neutron NPU",
        ],
    },
    {
        "name": "stm32_ai",
        "file": "ai_stm32_cube.jsonl",
        "count": 200,
        "system": "You are an expert in STM32Cube.AI (X-CUBE-AI) and the new STM32N6 with NPU. You convert, optimize, and deploy neural networks on STM32 microcontrollers.",
        "topics": [
            "Convert a Keras/TFLite model to STM32 using X-CUBE-AI",
            "STM32Cube.AI: model validation, compression, and C code generation",
            "Deploy {task} model on STM32H7 using X-CUBE-AI runtime",
            "STM32N6 NPU: architecture, supported operators, and performance",
            "Compare X-CUBE-AI vs TFLite Micro on STM32 for {task}",
            "STM32 model optimization: quantization, pruning, knowledge distillation",
            "X-CUBE-AI memory analysis: Flash vs RAM placement strategies",
            "STM32N6 deployment guide: from training to NPU inference",
            "Benchmark {model} on STM32H7 vs STM32N6: CPU vs NPU comparison",
            "STM32 AI use cases: predictive maintenance, anomaly detection, voice",
            "NanoEdge AI Studio: autoML for STM32 anomaly detection",
            "STM32 camera module + X-CUBE-AI for person detection",
        ],
    },
    {
        "name": "apple_npu",
        "file": "ai_apple_coreml_mlx.jsonl",
        "count": 200,
        "system": "You are an expert in Apple Neural Engine, CoreML, and MLX (ml-explore). You deploy and fine-tune models on Apple Silicon (M1-M4) using CoreML, MLX, and Apple Intelligence APIs.",
        "topics": [
            "Convert a PyTorch model to CoreML using coremltools",
            "Deploy {model} on Apple Neural Engine via CoreML",
            "MLX fine-tuning: LoRA on Apple Silicon M-series GPU",
            "CoreML vs MLX: when to use which on Apple Silicon",
            "Apple Intelligence on-device: architecture and capabilities",
            "MLX inference: load and run {model} with ml-explore/mlx",
            "CoreML model optimization: quantization, palettization, pruning",
            "Apple Neural Engine: which operations run on ANE vs GPU vs CPU",
            "MLX-LM: text generation with Llama/Mistral on Apple Silicon",
            "CoreML on iOS/macOS: model deployment and performance profiling",
            "MLX fine-tuning pipeline: dataset preparation, LoRA config, evaluation",
            "Apple Vision Pro ML: CoreML 3D model deployment",
            "CoreML Stable Diffusion on Apple Silicon: optimization guide",
            "MLX vs llama.cpp vs GGUF: performance comparison on M-series",
        ],
    },
    {
        "name": "tinyml",
        "file": "ai_tinyml_generic.jsonl",
        "count": 200,
        "system": "You are an expert in TinyML: deploying machine learning models on microcontrollers with < 1MB RAM. You use TFLite Micro, Edge Impulse, MCUNet, and quantization techniques.",
        "topics": [
            "Deploy a keyword spotting model using TFLite Micro on {mcu}",
            "Edge Impulse: train and deploy {task} model on {mcu}",
            "TFLite Micro vs CMSIS-NN: performance comparison on Cortex-M",
            "Quantize a {model} model to INT8 for MCU deployment",
            "MCUNet: Neural Architecture Search for microcontrollers",
            "TinyEngine: optimized inference engine for MCU (MIT HAN Lab)",
            "Implement anomaly detection on {mcu} using TinyML",
            "MLPerf Tiny benchmark: how to run and interpret results",
            "On-device learning: federated learning on microcontrollers",
            "TinyML model optimization: pruning, distillation, NAS for MCU",
            "Audio classification on MCU: from MFCC features to inference",
            "TinyML power analysis: inference energy on {mcu} at {freq}MHz",
            "microTVM (Apache TVM): compile models for MCU targets",
            "ONNX Runtime Micro: deploy ONNX models on Cortex-M",
            "TinyML accelerometer gesture recognition on {mcu}",
        ],
    },
]

VARS = {
    "model": ["MobileNetV2", "YOLOv5-nano", "ResNet-8", "DS-CNN", "DSCNN-L", "EfficientNet-Lite0", "MobileViT-XXS"],
    "task": ["keyword spotting", "person detection", "image classification", "anomaly detection", "gesture recognition", "object detection", "speaker verification", "sound classification"],
    "power": ["low", "normal", "burst"],
    "n": ["3", "5", "10", "20"],
    "mcu": ["STM32L476", "STM32H743", "nRF52840", "RP2040", "Arduino Nano 33 BLE", "ESP32-S3", "Cortex-M4"],
    "freq": ["48", "64", "80", "120", "168", "240"],
}


def fill_template(template):
    result = template
    for key, values in VARS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    return result


def generate_qa(chip):
    topic = fill_template(random.choice(chip["topics"]))
    headers = {"Content-Type": "application/json"}
    try:
        r = httpx.Client(timeout=120).post(OLLAMA_URL, headers=headers, json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": chip["system"]},
                {"role": "user", "content": topic + "\n\nProvide detailed, practical answer with code examples where applicable."},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        })
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"]
        if len(answer) > 100:
            return {
                "conversations": [
                    {"from": "system", "value": chip["system"]},
                    {"from": "human", "value": topic},
                    {"from": "gpt", "value": answer},
                ],
                "domain": f"ai-on-chip-{chip['name']}",
                "source": "devstral-distillation",
            }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CHIPS)
    print(f"=== AI on Chip Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs across {len(CHIPS)} platforms\n")

    for chip in CHIPS:
        output = os.path.join(OUTPUT_DIR, chip["file"])
        print(f"\n=== {chip['name']} ({chip['count']} pairs) -> {chip['file']} ===")
        count = 0
        errors = 0

        with open(output, "w") as f:
            for i in range(chip["count"]):
                result = generate_qa(chip)
                if result:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                    count += 1
                else:
                    errors += 1
                if (i + 1) % 25 == 0:
                    print(f"  [{i+1}/{chip['count']}] generated={count} errors={errors}")
                time.sleep(0.5)
        print(f"  DONE: {count} pairs, {errors} errors")

    print(f"\n=== ALL DONE ===")


if __name__ == "__main__":
    main()
