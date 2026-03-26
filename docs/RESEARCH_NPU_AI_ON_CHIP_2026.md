# NPU / AI on Chip SOTA 2026

## MCU avec NPU

| Chip | Fabricant | NPU | TOPS INT8 | SRAM | Prix | Dispo |
|------|-----------|-----|-----------|------|------|-------|
| STM32N6 | ST | Neural-ART | 0.6 | 4.2 MB | $8-15 | H2 2025 |
| Alif E7 | Alif | 2x Ethos-U55-256 | 0.5 | 13.5 MB | $10-20 | Shipping |
| Renesas RA8D1 | Renesas | Ethos-U55-128 | 0.13 | 2 MB | $8-12 | Shipping |
| Ambiq Apollo5 | Ambiq | Ethos-U55-128 | 0.13 | 3.75 MB | $5-10 | 2025 |
| Infineon PSoC Edge | Infineon | Ethos-U55-128 | 0.13 | 2 MB | $5-10 | 2025 |
| NXP MCX-N94x | NXP | eIQ Neutron | 0.005 | 512 KB | $3-6 | Shipping |
| MAX78000 | ADI | CNN accelerator | 1.2* | 442 KB | $5-8 | Shipping |
| MAX78002 | ADI | CNN v2 | 1.2* | 2 MB | $8-12 | Shipping |
| Syntiant NDP120 | Syntiant | Core 2 | 0.001 | 48 KB | $3-5 | Shipping |
| Syntiant NDP200 | Syntiant | Core 2+ | 0.01 | ~1 MB | $5-8 | 2025 |
| K210 | Canaan | KPU | 0.8 | 8 MB | $6 | Shipping |
| K230 | Canaan | KPU v2 | 2.0 | DDR ext | $10-15 | Shipping |
| ESP32-P4 | Espressif | PIE (pas NPU) | 0.001 | 768 KB | $3-5 | 2025 |
| GAP9 | GreenWaves | PULP RISC-V | 0.05 | 1.5 MB | $10-15 | Shipping |

*MAX78000 : peak CNN engine, modele doit tenir dans 442 KB poids

## Champions par categorie

- Performance : STM32N6 (600 GOPS)
- Flexibilite : Alif E7 (dual NPU + Cortex-A32 Linux)
- Efficacite : Ambiq Apollo5 (3-5 uW/MHz)
- Audio always-on : Syntiant NDP120 (<1 mW)
- Latence CNN : MAX78000 (microseconds, 100+ TOPS/W)
- Standard IP : Arm Ethos-U55 (5+ vendeurs)

## Arm Ethos-U55 vs U65

| Feature | U55 | U65 |
|---------|-----|-----|
| Cible | Cortex-M (MCU) | Cortex-M + A (MPU) |
| MAC configs | 32-256 | 256-512 |
| Peak TOPS INT8 | 0.5 | 1.0 |
| Memoire | SRAM only | + external AXI |
| Vendeurs | Renesas, Ambiq, Infineon, Alif, Samsung | En cours |
| Compilateur | Vela (`pip install ethos-u-vela`) | Vela |
| Ops supportees | 90+ TFLite | 90+ TFLite |

## Apple Silicon

| Chip | ANE TOPS | GPU TFLOPS | Mem BW | RAM |
|------|----------|------------|--------|-----|
| M4 | 38 | 4.6 | 120 GB/s | 16-32 GB |
| M4 Pro | 38 | 8+ | 273 GB/s | 24-48 GB |
| M4 Max | 38 | 14+ | 546 GB/s | 36-128 GB |

MLX tourne sur GPU (Metal), PAS sur ANE. CoreML pour ANE.

## RISC-V AI

- K230 KPU v2 : 2 TOPS, le plus capable
- GreenWaves GAP9 : 50 GOPS, ultra low power (PULP)
- ESP32-P4 PIE : SIMD, pas un vrai NPU
- SiFive X280 : RVV 1.0, 64 GOPS INT8

## Petits LLM pour edge

| Modele | Params | Taille Q4 | RAM min |
|--------|--------|-----------|---------|
| BitNet b1.58-2B4T | 2B | 400 MB | 500 MB |
| SmolLM2-135M | 135M | 80 MB | 128 MB |
| Gemma 3 270M | 270M | 150 MB | 256 MB |
| Qwen3-0.6B | 600M | 350 MB | 512 MB |
| TinyLlama-1.1B | 1.1B | 637 MB | 1 GB |

BitNet b1.58 = breakthrough : poids natifs 1.58-bit, 11 tok/s sur RPi 5.

Sources : arXiv:2503.22567, renesas.com, syntiant.com, ambiq.com, nxp.com, st.com
