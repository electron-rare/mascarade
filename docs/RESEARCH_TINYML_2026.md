# TinyML SOTA 2026

## Frameworks

| Framework | Status | Cible | Force |
|-----------|--------|-------|-------|
| TFLite Micro (LiteRT) | Actif, standard | Tous MCU | 16 KB runtime, INT8 |
| Edge Impulse | Actif, commercial | 100+ boards | No-code AutoML, EON Compiler |
| MCUNet/TinyEngine (MIT) | Actif | Cortex-M | 3.4x moins RAM que TFLite |
| STM32Cube.AI | Actif | STM32 | Optimise pour STM32, NPU STM32N6 |
| NXP eIQ | Actif | NXP MCX | Portal GUI, Glow compiler |
| ESP-DL v3.2 | Actif | ESP32-S3/P4 | Format .espdl, dual-core scheduling |
| microTVM | Actif | Tous | Compiler-based, NAS support |
| NNoM | Actif, niche | Cortex-M | API Keras-like en C |
| SensiML/Piccolo | Actif | MCU + FPGA | Time-series specialiste |

## Modeles MCU (< 1MB RAM)

| Tache | Modele | RAM | Latence |
|-------|--------|-----|---------|
| Keyword spotting | DS-CNN 46.5K params | 30-70 KB | 15ms |
| Person detection | Plumerai MobileNet | 166 KB | 300ms (3.3 FPS) |
| Object detection | FOMO MobileNetV2 0.1 | 200-300 KB | 143ms (7 FPS) |
| Anomaly detection | Autoencoder INT8 | 50 KB | 45ms |
| Sound classification | YAMNet-lite | 200 KB | 80-120ms |
| Gesture recognition | 1D CNN | 10-50 KB | 10ms |

## MLPerf Tiny v1.3 (Sept 2025)

5 benchmarks : KWS, Visual Wake Words, CIFAR-10, Anomaly Detection, Wake Word Streaming.
Syntiant NDP120 = leader efficacite energetique.

## Papers cles 2025-2026

- MCUNetV3 : on-device training sous 256 KB SRAM
- TinyTNAS : NAS sans GPU pour time-series
- MicroNAS : NAS differentiable + latency lookup tables
- INT4 MCU : experimental, production reste INT8
- Federated Learning MCU : sub-96 KB, gradient sparsification

Sources : arxiv.org/html/2506.18927v2, shawnhymel.com, mdpi.com/1424-8220/25/10/3191
