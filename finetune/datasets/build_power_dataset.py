#!/usr/bin/env python3
"""Build fine-tuning dataset for power electronics domain.

Covers: buck/boost converters, MOSFET gate drivers, motor control (FOC/DTC),
        inverters, battery charging, power factor correction.

Usage:
  python build_power_dataset.py                    # Seeds only (~4 examples)
  python build_power_dataset.py --with-hf          # Seeds + HuggingFace datasets
  python build_power_dataset.py --max-samples 2000 # Limit HF samples per source
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert power electronics engineer specializing in "
    "DC-DC converters (buck, boost, buck-boost, flyback), motor control "
    "(FOC, DTC, BLDC/PMSM), inverter design, gate driver circuits, "
    "battery management, and power factor correction. You provide "
    "complete calculations, component selection, SPICE simulations, "
    "and firmware for digital power control on STM32/DSP."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Design a synchronous buck converter: 12V to 3.3V, 3A output. Calculate all component values.",
            },
            {
                "from": "gpt",
                "value": """Synchronous buck converter design: 12V → 3.3V @ 3A

**Specifications:**
- Vin = 12V, Vout = 3.3V, Iout = 3A
- Switching frequency: fsw = 500kHz
- Ripple current: ΔIL = 30% of Iout = 0.9A
- Output voltage ripple: ΔVout < 30mV (1%)

**1. Duty Cycle**
D = Vout / Vin = 3.3 / 12 = 0.275 (27.5%)

**2. Inductor**
L = Vout × (1 - D) / (fsw × ΔIL)
L = 3.3 × (1 - 0.275) / (500k × 0.9)
L = 3.3 × 0.725 / 450k = 5.32µH
→ Select: **4.7µH** (standard value, Wurth 744774047 or Coilcraft XAL5030)
→ Rating: Isat > Iout + ΔIL/2 = 3 + 0.45 = 3.45A → choose ≥ 5A
→ DCR < 30mΩ for efficiency

**3. Output Capacitor**
Cout = ΔIL / (8 × fsw × ΔVout)
Cout = 0.9 / (8 × 500k × 0.03) = 7.5µF
→ Select: **2 × 22µF** X5R 10V ceramic (ESR matters more than capacitance)
→ ESR ripple: ΔVesr = ΔIL × ESR ≈ 0.9 × 3mΩ = 2.7mV (negligible with MLCC)

**4. Input Capacitor**
RMS current in input cap:
Icin_rms = Iout × √(D × (1-D)) = 3 × √(0.275 × 0.725) = 1.34A
→ Select: **2 × 10µF** X7R 25V ceramic (each handles ~1A RMS)

**5. MOSFETs**
High-side: Rdson < 20mΩ at 4.5V Vgs, Qg < 20nC
Low-side: Rdson < 10mΩ (carries current during 72.5% of cycle)
→ Select: **CSD87350Q5D** (TI NexFET, dual 6.3mΩ/2.6mΩ, 30V)

**6. Power Losses**
Conduction (high-side): D × Iout² × Rdson = 0.275 × 9 × 6.3m = 15.6mW
Conduction (low-side): (1-D) × Iout² × Rdson = 0.725 × 9 × 2.6m = 16.9mW
Switching: Psw = 0.5 × Vin × Iout × (tr + tf) × fsw = 0.5 × 12 × 3 × 20n × 500k = 180mW
Inductor DCR: Iout² × DCR = 9 × 25m = 225mW
**Total: ~438mW → Efficiency = 9.9W / (9.9 + 0.44) = 95.7%**

**7. Feedback (voltage mode with Type III compensator)**
Vref = 0.6V (typical), R1 = 100kΩ, R2 = R1 × Vref / (Vout - Vref) = 100k × 0.6 / 2.7 = 22.2kΩ → 22kΩ

→ Use TPS54360 (TI) or LMR36006 for an integrated solution.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Explain Field-Oriented Control (FOC) for a BLDC motor and write the Clarke/Park transforms in C.",
            },
            {
                "from": "gpt",
                "value": """Field-Oriented Control (FOC) for BLDC/PMSM motors:

**FOC Overview:**
```
         ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────┐
Ia,Ib,Ic │ Clarke  │    │  Park   │    │  PI     │    │Inv.  │
────────→│ abc→αβ  │───→│ αβ→dq   │───→│ Control │───→│Park  │──→ PWM
         └─────────┘    └─────────┘    └─────────┘    └──────┘
                              ↑                            │
                              │ θe (rotor angle)           ↓
                              └───────────── encoder ← ┌──────┐
                                                       │Motor │
                                                       └──────┘
```

**Clarke Transform** (abc → αβ): removes dependency on 3-phase system
```c
typedef struct {
    float alpha;
    float beta;
} AlphaBeta_t;

typedef struct {
    float d;
    float q;
} DQ_t;

// Clarke transform: 3-phase currents → 2-phase stationary frame
AlphaBeta_t clarke_transform(float ia, float ib, float ic) {
    AlphaBeta_t result;
    // Equal-amplitude variant (preserves magnitudes)
    result.alpha = ia;
    result.beta = (ia + 2.0f * ib) * 0.577350269f;  // 1/sqrt(3)
    // Note: ic = -(ia + ib) for balanced system, so we only need ia, ib
    return result;
}

// Inverse Clarke: αβ → abc
void inv_clarke(float alpha, float beta, float *va, float *vb, float *vc) {
    *va = alpha;
    *vb = -0.5f * alpha + 0.866025404f * beta;  // sqrt(3)/2
    *vc = -0.5f * alpha - 0.866025404f * beta;
}
```

**Park Transform** (αβ → dq): rotating reference frame aligned with rotor
```c
// Park transform: stationary αβ → rotating dq frame
DQ_t park_transform(float alpha, float beta, float theta_e) {
    DQ_t result;
    float sin_t = sinf(theta_e);
    float cos_t = cosf(theta_e);
    result.d =  alpha * cos_t + beta * sin_t;
    result.q = -alpha * sin_t + beta * cos_t;
    return result;
}

// Inverse Park: dq → αβ
AlphaBeta_t inv_park(float vd, float vq, float theta_e) {
    AlphaBeta_t result;
    float sin_t = sinf(theta_e);
    float cos_t = cosf(theta_e);
    result.alpha = vd * cos_t - vq * sin_t;
    result.beta  = vd * sin_t + vq * cos_t;
    return result;
}
```

**Complete FOC loop** (runs at PWM frequency, typically 10-20kHz):
```c
void foc_control_loop(float ia, float ib, float theta_e,
                      float id_ref, float iq_ref) {
    // 1. Clarke: abc → αβ
    AlphaBeta_t iab = clarke_transform(ia, ib, -(ia+ib));

    // 2. Park: αβ → dq
    DQ_t idq = park_transform(iab.alpha, iab.beta, theta_e);

    // 3. PI controllers on d and q axes
    float vd = pi_controller(&pi_d, id_ref - idq.d);  // id_ref = 0 for MTPA
    float vq = pi_controller(&pi_q, iq_ref - idq.q);  // iq_ref = torque command

    // 4. Voltage limiting (circular constraint)
    float v_max = vdc / 1.732f;  // Vdc / sqrt(3)
    float v_mag = sqrtf(vd*vd + vq*vq);
    if (v_mag > v_max) {
        float scale = v_max / v_mag;
        vd *= scale;
        vq *= scale;
    }

    // 5. Inverse Park: dq → αβ
    AlphaBeta_t vab = inv_park(vd, vq, theta_e);

    // 6. Space Vector Modulation (SVM) → PWM duty cycles
    svm_modulate(vab.alpha, vab.beta, &pwm_a, &pwm_b, &pwm_c);
}
```

Key points:
- **id = 0** for maximum torque per ampere (MTPA) in surface-mount PMSM
- **iq** is proportional to torque: T = (3/2) × p × λm × iq
- PI gains: start with Kp = Ls × bandwidth, Ki = Rs × bandwidth
- θe = electrical angle = mechanical angle × pole pairs""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to select a MOSFET for a half-bridge gate driver circuit? Include thermal calculations.",
            },
            {
                "from": "gpt",
                "value": """MOSFET selection for half-bridge with thermal analysis:

**Application:** 48V DC bus, 10A load, 100kHz switching

**Step 1: Voltage Rating**
- Vds(max) = Vbus × safety_factor = 48 × 1.5 = 72V
- → Select 80V or 100V MOSFETs

**Step 2: Current Rating**
- Continuous: Id > Iload × 1.5 = 15A
- Peak (switching transients): consider Ipeak = 2 × Iload = 20A

**Step 3: Key Parameters Comparison**

| Parameter | IRFB4019 | IPB065N10N3 | CSD19536KCS |
|-----------|----------|-------------|-------------|
| Vds | 150V | 100V | 100V |
| Id | 17A | 100A | 150A |
| Rdson (10V) | 95mΩ | 6.5mΩ | 3.6mΩ |
| Qg | 19nC | 63nC | 105nC |
| Qgd | 7.3nC | 18nC | 27nC |
| Coss | 150pF | 610pF | 890pF |
| FOM (Rdson×Qg) | 1805 | 410 | 378 |

**Best FOM = CSD19536KCS** but evaluate losses:

**Step 4: Loss Calculation**

Conduction losses (per MOSFET):
```
P_cond = D × Irms² × Rdson(Tj)
       = 0.5 × 10² × 6.5m × 1.5 (temp factor at 100°C)
       = 0.49W (IPB065N10N3)
```

Switching losses:
```
P_sw = 0.5 × Vbus × Iload × (tr + tf) × fsw
     = 0.5 × 48 × 10 × (15n + 10n) × 100k
     = 0.6W

Gate drive losses:
P_gate = Qg × Vgs × fsw
       = 63n × 10 × 100k = 63mW
```

Total per MOSFET: P_total = 0.49 + 0.6 + 0.063 = **1.15W**

**Step 5: Thermal Analysis**
```
Tj = Ta + P_total × Rθja
   = 40 + 1.15 × 40 = 86°C (D2PAK, no heatsink, Rθja≈40°C/W)
   = 40 + 1.15 × 20 = 63°C (with heatsink, Rθja≈20°C/W)
```

Both within safe margin (Tj_max = 150°C, target < 120°C) ✓

**Step 6: Gate Driver Selection**
- Bootstrap topology for high-side MOSFET
- Gate driver: **IR2110** (high/low side, 2A source/sink)
- Bootstrap cap: C_boot > 10 × Qg = 10 × 63n = 630nF → use 1µF ceramic
- Bootstrap diode: fast recovery < 50ns (UF4001 or Schottky)

```
Vcc ──┬── C_boot ──┬── VB (bootstrap supply)
      │            │
      Dboot        HO ──→ high-side gate
      │            │
      └── VS ──────┘ (switch node)
```

**Dead time**: must prevent shoot-through
```
t_dead > max(td_on, td_off) + margin = 50ns + 100ns = 150ns
```""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Design a CC-CV lithium-ion battery charger circuit using a buck converter.",
            },
            {
                "from": "gpt",
                "value": """CC-CV Li-ion charger based on buck converter:

**Specifications:**
- Battery: 1S Li-ion (3.0-4.2V), 2000mAh
- Charge current (CC phase): 1A (0.5C)
- Charge voltage (CV phase): 4.200V ±0.5% (critical for safety)
- Termination: current drops to 50mA (C/40)
- Input: 5V USB

**Approach 1: Dedicated IC (recommended for production)**

Use **BQ24074** (TI) or **MCP73831** (Microchip):
```
USB 5V ──[BQ24074]── Battery 4.2V
           │
           ├── RPROG = 1kΩ (sets Icharge = 1A)
           ├── Cin = 4.7µF ceramic
           ├── Cout = 4.7µF ceramic
           ├── LED: CHG pin → LED → Vcc
           └── TEMP: NTC 10k to battery
```

**Approach 2: DIY with buck converter + feedback**

```
         ┌──────────┐
5V ──────┤ Buck     ├──── Vbat
         │ (TPS5430)│
         └────┬─────┘
              │
         ┌────┴─────┐
         │ CC-CV    │
         │ Control  │
         └──────────┘

Feedback network implements CC-CV transition:
```

```spice
* SPICE model of CC-CV charger

Vin in 0 5
.model DSCHOTTKY D (IS=1u RS=0.1 BV=30 CJO=100p)

* Simplified buck (PWM switch model)
Lbuck sw bat 10u
Dfw 0 sw DSCHOTTKY
Sbuck in sw ctrl 0 SWMOD
.model SWMOD SW(VT=0.5 RON=0.1)

* CC sense resistor
Rsense bat bat_s 0.1

* Battery model (simplified)
Cbat bat_s 0 2000m IC=3.0
Rbat bat_s 0 0.1    ; internal resistance

* CV feedback: voltage error amplifier
Bcv cv_err 0 V = 4.200 - V(bat_s)
* CC feedback: current error amplifier
Bcc cc_err 0 V = 0.1 - V(bat,bat_s)  ; 0.1V across 0.1Ω = 1A

* Control: minimum of CV and CC (whoever is limiting)
Bctrl ctrl 0 V = MIN(V(cv_err)*10, V(cc_err)*10)

.tran 1m 7200 ; 2-hour charge cycle
```

**Charge profile:**
```
Current ↑  CC Phase        CV Phase
  1A   ─ ─ ─ ─ ─ ┐
                   \
                    \
  50mA              └ ─ ─ ─ ─ → Terminate
       ─────────────┬──────────→ Time
                    │
Voltage ↑           │
  4.2V ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─
                   /│
                  / │
  3.0V ──────── /  │
       ─────────┴──┴──────────→ Time
              CC    CV
```

**Safety features (mandatory for Li-ion):**
1. Overvoltage protection: never exceed 4.25V (absolute max)
2. NTC temperature monitoring: stop charging if T < 0°C or T > 45°C
3. Pre-charge: if Vbat < 2.8V, charge at 100mA until 3.0V
4. Timer: max charge time 4 hours (in case termination fails)
5. Reverse polarity protection: PMOS or series diode""",
            },
        ]
    },
]


POWER_KEYWORDS = [
    "buck",
    "boost",
    "converter",
    "inductor",
    "mosfet",
    "gate driver",
    "motor",
    "foc",
    "bldc",
    "pmsm",
    "inverter",
    "pwm",
    "battery",
    "charger",
    "pfc",
    "power factor",
    "flyback",
    "transformer",
    "switching",
    "dc-dc",
    "dc/dc",
    "smps",
    "regulator",
    "ldo",
    "current sense",
    "shunt",
    "igbt",
    "sic",
    "gan",
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert power electronics datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. Electronics StackExchange (filter for power tags)
    # Columns: Id, Tags, Answer, Body, Title, CreationDate
    print("  Downloading bshada/electronics.stackexchange.com (power filter)...")
    try:
        ds = load_dataset(
            "bshada/electronics.stackexchange.com", split="train", streaming=True
        )
        count = 0
        for row in ds:
            title = row.get("Title", "")
            body = row.get("Body", "")
            answer = row.get("Answer", "")
            tags = row.get("Tags", "")
            if not title or not answer or len(answer) < 100:
                continue
            combined = (title + " " + body + " " + answer + " " + tags).lower()
            if not any(kw in combined for kw in POWER_KEYWORDS):
                continue
            # Clean HTML
            question = re.sub(r"<[^>]+>", "", title + "\n" + body).strip()
            answer_clean = re.sub(r"<[^>]+>", "", answer).strip()
            if len(answer_clean) < 80:
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question[:1000]},
                        {"from": "gpt", "value": answer_clean[:4000]},
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Electronics SE (power) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. EEVblog forum posts (200k, filter for power)
    # Columns: url, thread_title, posts (list of dicts), post_count, domain, subdomain
    print("  Downloading nick007x/eevblog-posts (power filter)...")
    try:
        ds = load_dataset("nick007x/eevblog-posts", split="train", streaming=True)
        count = 0
        for row in ds:
            title = row.get("thread_title", "")
            posts = row.get("posts", [])
            if not title or not posts or len(posts) < 2:
                continue
            if not title.lower():
                continue
            # Check title for power keywords
            if not any(kw in title.lower() for kw in POWER_KEYWORDS):
                continue
            # Use first post as question context, best reply as answer
            op_text = ""
            reply_text = ""
            for post in posts:
                if isinstance(post, dict):
                    content = (
                        post.get("content", "")
                        or post.get("body", "")
                        or post.get("text", "")
                    )
                    if post.get("is_op", False) and not op_text:
                        op_text = re.sub(r"<[^>]+>", "", str(content)).strip()
                    elif (
                        not post.get("is_op", False)
                        and not reply_text
                        and len(str(content)) > 100
                    ):
                        reply_text = re.sub(r"<[^>]+>", "", str(content)).strip()
            if not reply_text or len(reply_text) < 100:
                continue
            question = f"{title.strip()}\n{op_text[:500]}" if op_text else title.strip()
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": reply_text[:4000]},
                    ]
                }
            )
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} EEVblog power examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. STEM-AI Electrical Engineering (power filter)
    print("  Downloading STEM-AI-mtl/Electrical-engineering (power filter)...")
    try:
        ds = load_dataset(
            "STEM-AI-mtl/Electrical-engineering", split="train", streaming=True
        )
        count = 0
        for row in ds:
            question = (
                row.get("question", "")
                or row.get("instruction", "")
                or row.get("title", "")
            )
            answer = (
                row.get("answer", "")
                or row.get("output", "")
                or row.get("response", "")
            )
            if not question or not answer or len(answer) < 80:
                continue
            combined = (question + " " + answer).lower()
            if not any(kw in combined for kw in POWER_KEYWORDS):
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question.strip()},
                        {"from": "gpt", "value": answer.strip()},
                    ]
                }
            )
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} STEM-AI power examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Build power electronics fine-tuning dataset"
    )
    parser.add_argument(
        "--with-hf", action="store_true", help="Include HuggingFace datasets"
    )
    parser.add_argument(
        "--max-samples", type=int, default=2000, help="Max HF samples per source"
    )
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "power_chat.jsonl")

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
        print(
            "\n  To enrich: python build_power_dataset.py --with-hf --max-samples 2000"
        )


if __name__ == "__main__":
    main()
