#!/usr/bin/env python3
"""Build fine-tuning dataset for DSP/signal processing domain.

Covers: FFT, digital filters (FIR/IIR), audio processing, CMSIS-DSP,
        spectral analysis, modulation/demodulation.

Usage:
  python build_dsp_dataset.py                    # Seeds only (~3 examples)
  python build_dsp_dataset.py --with-hf          # Seeds + HuggingFace datasets
  python build_dsp_dataset.py --max-samples 2000 # Limit HF samples per source
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert digital signal processing engineer. You design "
    "and implement FIR/IIR digital filters, FFT-based spectral analysis, "
    "audio processing algorithms, and real-time DSP on ARM Cortex-M "
    "using CMSIS-DSP. You provide complete implementations with correct "
    "math, fixed-point optimizations, and clear explanations of the "
    "underlying theory."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Implement a real-time FFT spectrum analyzer on STM32 using CMSIS-DSP."},
            {"from": "gpt", "value": """Real-time FFT spectrum analyzer using CMSIS-DSP on Cortex-M4:

```c
#include "arm_math.h"
#include <string.h>

#define FFT_SIZE      1024
#define SAMPLE_RATE   44100

// Buffers (must be aligned for CMSIS-DSP)
static float32_t fft_input[FFT_SIZE * 2];   // Complex: [re,im,re,im,...]
static float32_t fft_output[FFT_SIZE * 2];
static float32_t magnitude[FFT_SIZE / 2];

// Hanning window (pre-computed)
static float32_t window[FFT_SIZE];

// CMSIS-DSP FFT instance
static arm_cfft_instance_f32 fft_instance;

void spectrum_init(void) {
    // Initialize FFT (1024-point complex FFT)
    arm_cfft_init_f32(&fft_instance, FFT_SIZE);

    // Pre-compute Hanning window
    for (int i = 0; i < FFT_SIZE; i++) {
        window[i] = 0.5f * (1.0f - arm_cos_f32(2.0f * PI * i / (FFT_SIZE - 1)));
    }
}

void compute_spectrum(const float32_t *audio_samples) {
    // 1. Apply window and pack into complex array
    for (int i = 0; i < FFT_SIZE; i++) {
        fft_input[2*i]     = audio_samples[i] * window[i];  // Real
        fft_input[2*i + 1] = 0.0f;                          // Imaginary
    }

    // 2. In-place complex FFT
    arm_cfft_f32(&fft_instance, fft_input, 0, 1);  // 0=forward, 1=bit-reverse

    // 3. Calculate magnitude (only first half — symmetric for real input)
    arm_cmplx_mag_f32(fft_input, magnitude, FFT_SIZE / 2);

    // 4. Convert to dB
    for (int i = 0; i < FFT_SIZE / 2; i++) {
        magnitude[i] = 20.0f * log10f(magnitude[i] / FFT_SIZE + 1e-10f);
    }
}

// Get frequency for a given bin
float bin_to_freq(int bin) {
    return (float)bin * SAMPLE_RATE / FFT_SIZE;
    // Resolution: 44100 / 1024 = 43.07 Hz per bin
}

// Find dominant frequency
float find_peak_frequency(void) {
    float32_t max_val;
    uint32_t max_idx;
    arm_max_f32(magnitude, FFT_SIZE / 2, &max_val, &max_idx);
    return bin_to_freq(max_idx);
}
```

Performance on STM32F4 @ 168MHz:
- 1024-point FFT: ~0.7ms (CMSIS-DSP uses radix-4/radix-2 butterfly)
- Magnitude calculation: ~0.2ms
- Total: ~1ms per frame → supports real-time at 44.1kHz

Memory: ~16KB for buffers (could use Q15 fixed-point to halve it)

Frequency resolution = fs/N = 44100/1024 = **43.07 Hz per bin**
Max frequency = fs/2 = **22050 Hz** (Nyquist)"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Design a low-pass FIR filter with 100Hz cutoff at 1kHz sample rate. Show the coefficient calculation and C implementation."},
            {"from": "gpt", "value": """FIR low-pass filter design: fc=100Hz, fs=1kHz, 31 taps

**Design using windowed sinc method:**

```python
# Filter design (run once to get coefficients)
import numpy as np

fs = 1000      # Sample rate
fc = 100       # Cutoff frequency
N = 31         # Filter order (odd for symmetric)
n = np.arange(N)
M = (N - 1) / 2  # Center of filter

# Ideal sinc filter coefficients
wc = 2 * np.pi * fc / fs  # Normalized cutoff
h = np.where(n == M,
    wc / np.pi,
    np.sin(wc * (n - M)) / (np.pi * (n - M)))

# Apply Hamming window (better stopband attenuation than rectangular)
w = 0.54 - 0.46 * np.cos(2 * np.pi * n / (N - 1))
h_windowed = h * w

# Normalize for unity gain at DC
h_windowed /= np.sum(h_windowed)

# Print coefficients for C
print("const float fir_coeffs[] = {")
for i, coeff in enumerate(h_windowed):
    print(f"    {coeff:.10f}f,  // h[{i}]")
print("};")
```

**C implementation (real-time):**

```c
#include <string.h>

#define FIR_TAPS 31

// Pre-computed coefficients (from Python script above)
static const float fir_coeffs[FIR_TAPS] = {
    -0.0003015744f,  // h[0]
    -0.0008623391f,  // h[1]
    -0.0013902785f,  // h[2]
     0.0000000000f,  // h[3]
     0.0040822217f,  // h[4]
     0.0094987755f,  // h[5]
     0.0101587302f,  // h[6]
    -0.0000000000f,  // h[7]
    -0.0225749317f,  // h[8]
    -0.0451498634f,  // h[9]
    -0.0409647389f,  // h[10]
     0.0000000000f,  // h[11]
     0.0899610873f,  // h[12]
     0.1996580660f,  // h[13]
     0.2899542305f,  // h[14]
     0.3183098862f,  // h[15]  ← center tap
     0.2899542305f,  // h[16]
     0.1996580660f,  // h[17]
     0.0899610873f,  // h[18]
     0.0000000000f,  // h[19]
    -0.0409647389f,  // h[20]
    -0.0451498634f,  // h[21]
    -0.0225749317f,  // h[22]
    -0.0000000000f,  // h[23]
     0.0101587302f,  // h[24]
     0.0094987755f,  // h[25]
     0.0040822217f,  // h[26]
     0.0000000000f,  // h[27]
    -0.0013902785f,  // h[28]
    -0.0008623391f,  // h[29]
    -0.0003015744f,  // h[30]
};

// Circular buffer for delay line
static float delay_line[FIR_TAPS] = {0};
static int delay_idx = 0;

// Process one sample
float fir_filter(float input) {
    // Insert new sample into delay line
    delay_line[delay_idx] = input;

    // Convolution (MAC operation)
    float output = 0.0f;
    int idx = delay_idx;
    for (int i = 0; i < FIR_TAPS; i++) {
        output += fir_coeffs[i] * delay_line[idx];
        idx--;
        if (idx < 0) idx = FIR_TAPS - 1;  // Circular wrap
    }

    // Advance write pointer
    delay_idx++;
    if (delay_idx >= FIR_TAPS) delay_idx = 0;

    return output;
}

// Block processing (more efficient, uses CMSIS-DSP)
#ifdef USE_CMSIS_DSP
#include "arm_math.h"
static arm_fir_instance_f32 fir_inst;
static float32_t fir_state[FIR_TAPS + BLOCK_SIZE - 1];

void fir_init_cmsis(void) {
    arm_fir_init_f32(&fir_inst, FIR_TAPS, (float32_t *)fir_coeffs,
                     fir_state, BLOCK_SIZE);
}

void fir_process_block(float32_t *input, float32_t *output, uint32_t block_size) {
    arm_fir_f32(&fir_inst, input, output, block_size);
}
#endif
```

Filter characteristics:
- Passband (0-100Hz): 0dB (unity gain), ripple < 0.05dB
- Transition band: 100-150Hz
- Stopband (>150Hz): attenuation > 40dB (Hamming window)
- Group delay: (N-1)/2 = 15 samples = 15ms at 1kHz

For steeper roll-off: increase taps (51 or 101) or use IIR (Butterworth/Chebyshev)."""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Implement a second-order IIR biquad filter (Butterworth low-pass) in C with Direct Form II."},
            {"from": "gpt", "value": """Biquad IIR filter — Butterworth low-pass, Direct Form II Transposed:

```c
#include <math.h>

typedef struct {
    // Coefficients
    float b0, b1, b2;  // Numerator (feedforward)
    float a1, a2;       // Denominator (feedback), a0 normalized to 1
    // State variables (Direct Form II Transposed)
    float z1, z2;
} Biquad_t;

// Design Butterworth low-pass biquad
void biquad_lowpass(Biquad_t *bq, float fc, float fs) {
    float w0 = 2.0f * M_PI * fc / fs;
    float alpha = sinf(w0) / (2.0f * 0.7071f);  // Q = 1/sqrt(2) for Butterworth

    float cos_w0 = cosf(w0);
    float a0_inv = 1.0f / (1.0f + alpha);

    bq->b0 = ((1.0f - cos_w0) / 2.0f) * a0_inv;
    bq->b1 = (1.0f - cos_w0) * a0_inv;
    bq->b2 = bq->b0;
    bq->a1 = (-2.0f * cos_w0) * a0_inv;
    bq->a2 = (1.0f - alpha) * a0_inv;
    bq->z1 = 0.0f;
    bq->z2 = 0.0f;
}

// Process one sample — Direct Form II Transposed
// Most numerically stable implementation for floating-point
float biquad_process(Biquad_t *bq, float input) {
    float output = bq->b0 * input + bq->z1;
    bq->z1 = bq->b1 * input - bq->a1 * output + bq->z2;
    bq->z2 = bq->b2 * input - bq->a2 * output;
    return output;
}

// Cascaded biquads for higher-order filters
#define MAX_SECTIONS 4  // 4 biquads = 8th order

typedef struct {
    Biquad_t sections[MAX_SECTIONS];
    int num_sections;
} CascadedBiquad_t;

float cascade_process(CascadedBiquad_t *cb, float input) {
    float x = input;
    for (int i = 0; i < cb->num_sections; i++) {
        x = biquad_process(&cb->sections[i], x);
    }
    return x;
}

// Design 4th-order Butterworth (2 cascaded biquads)
void butterworth_4th_lowpass(CascadedBiquad_t *cb, float fc, float fs) {
    cb->num_sections = 2;
    // Section 1: Q = 0.5412 (first Butterworth pole pair)
    float w0 = 2.0f * M_PI * fc / fs;
    float alpha1 = sinf(w0) / (2.0f * 0.5412f);
    float cos_w0 = cosf(w0);
    float a0_inv = 1.0f / (1.0f + alpha1);
    cb->sections[0].b0 = ((1.0f - cos_w0) / 2.0f) * a0_inv;
    cb->sections[0].b1 = (1.0f - cos_w0) * a0_inv;
    cb->sections[0].b2 = cb->sections[0].b0;
    cb->sections[0].a1 = (-2.0f * cos_w0) * a0_inv;
    cb->sections[0].a2 = (1.0f - alpha1) * a0_inv;
    cb->sections[0].z1 = cb->sections[0].z2 = 0;

    // Section 2: Q = 1.3066 (second Butterworth pole pair)
    float alpha2 = sinf(w0) / (2.0f * 1.3066f);
    a0_inv = 1.0f / (1.0f + alpha2);
    cb->sections[1].b0 = ((1.0f - cos_w0) / 2.0f) * a0_inv;
    cb->sections[1].b1 = (1.0f - cos_w0) * a0_inv;
    cb->sections[1].b2 = cb->sections[1].b0;
    cb->sections[1].a1 = (-2.0f * cos_w0) * a0_inv;
    cb->sections[1].a2 = (1.0f - alpha2) * a0_inv;
    cb->sections[1].z1 = cb->sections[1].z2 = 0;
}
```

Why Direct Form II Transposed:
- Only 2 state variables per biquad (vs 4 for Direct Form I)
- Best numerical properties for floating-point arithmetic
- Each section: 5 multiplies + 4 additions per sample
- On Cortex-M4 with FPU: ~10 cycles per biquad section"""}
        ]
    },
]


DSP_KEYWORDS = [
    "fft", "filter", "fir", "iir", "dsp", "signal processing",
    "fourier", "spectrum", "frequency", "sampling", "nyquist",
    "convolution", "autocorrelation", "z-transform", "laplace",
    "biquad", "butterworth", "chebyshev", "windowing", "hanning",
    "hamming", "kaiser", "audio", "modulation", "demodulation",
    "decimation", "interpolation", "oversampling", "aliasing",
    "cmsis-dsp", "arm_math", "fixed-point", "q15", "q31",
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert DSP datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. Electronics StackExchange (filter for DSP topics)
    # Columns: Id, Tags, Answer, Body, Title, CreationDate
    print("  Downloading bshada/electronics.stackexchange.com (DSP filter)...")
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
            if not any(kw in combined for kw in DSP_KEYWORDS):
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
        print(f"    Got {count} Electronics SE (DSP) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. StackExchange common-pile (DSP subdomain)
    print("  Downloading common-pile/stackexchange (DSP filter)...")
    try:
        ds = load_dataset("common-pile/stackexchange", split="train", streaming=True)
        count = 0
        for row in ds:
            text = row.get("text", "") or row.get("content", "")
            source = row.get("source", "") or row.get("url", "") or row.get("meta", "")
            source_str = str(source).lower()
            # Only keep DSP-related posts
            if "dsp.stackexchange" not in source_str and "signal" not in source_str:
                if not any(kw in text.lower()[:500] for kw in DSP_KEYWORDS[:10]):
                    continue
            if not text or len(text) < 150:
                continue
            # Try to split into Q&A if possible
            lines = text.strip().split("\n\n", 1)
            if len(lines) >= 2:
                q = lines[0].strip()
                a = lines[1].strip()
            else:
                q = "Explain this DSP concept."
                a = text.strip()
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": q[:500]},
                    {"from": "gpt", "value": a[:4000]},
                ]
            })
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} StackExchange DSP examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. Electrical engineering dataset (STEM-AI, DSP filter)
    print("  Downloading STEM-AI-mtl/Electrical-engineering (DSP filter)...")
    try:
        ds = load_dataset("STEM-AI-mtl/Electrical-engineering", split="train", streaming=True)
        count = 0
        for row in ds:
            question = row.get("question", "") or row.get("instruction", "") or row.get("title", "")
            answer = row.get("answer", "") or row.get("output", "") or row.get("response", "")
            if not question or not answer or len(answer) < 80:
                continue
            combined = (question + " " + answer).lower()
            if not any(kw in combined for kw in DSP_KEYWORDS):
                continue
            answer = re.sub(r'<[^>]+>', '', answer)
            question = re.sub(r'<[^>]+>', '', question)
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
        print(f"    Got {count} STEM-AI DSP examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(description="Build DSP fine-tuning dataset")
    parser.add_argument("--with-hf", action="store_true", help="Include HuggingFace datasets")
    parser.add_argument("--max-samples", type=int, default=2000, help="Max HF samples per source")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "dsp_chat.jsonl")

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
        print(f"\n  To enrich: python build_dsp_dataset.py --with-hf --max-samples 2000")


if __name__ == "__main__":
    main()
