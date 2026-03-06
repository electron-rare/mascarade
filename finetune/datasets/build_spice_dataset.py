#!/usr/bin/env python3
"""Build fine-tuning dataset for SPICE circuit simulation domain.

Covers: ngspice netlists, LTspice, convergence debugging, PySpice automation.

Usage:
  python build_spice_dataset.py                        # Seeds only (~7 examples)
  python build_spice_dataset.py --with-external        # Seeds + Masala-CHAI + SPICEPilot
  python build_spice_dataset.py --with-hf              # Seeds + HuggingFace EE dataset
  python build_spice_dataset.py --with-external --with-hf  # All sources
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert analog circuit designer and SPICE simulation engineer. "
    "You write correct ngspice/LTspice netlists, debug convergence issues, "
    "perform AC/DC/transient analysis, and automate simulations with PySpice. "
    "You provide complete netlists with correct device models, proper analysis "
    "directives, and clear explanations of circuit behavior."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a SPICE netlist for a common-emitter amplifier with voltage divider bias. Include AC analysis from 10Hz to 10MHz.",
            },
            {
                "from": "gpt",
                "value": """Common-emitter amplifier with voltage divider bias:

```spice
* Common-Emitter Amplifier with Voltage Divider Bias
* Vcc = 12V, Gain ≈ -100, Ic ≈ 1mA

.model 2N2222 NPN (IS=14.34f BF=255.9 VAF=74.03 IKF=0.2847
+ ISE=14.34f NE=1.307 BR=6.092 VAR=28 IKR=0 ISC=0
+ NC=2 RB=10 RE=0 RC=1 CJE=22.01p CJC=7.306p TF=0.4ns)

* Power supply
VCC vcc 0 12

* Voltage divider bias: R1/R2 set Vb ≈ 2.7V → Ic ≈ 1mA
R1 vcc base 22k
R2 base 0 4.7k

* Transistor
Q1 collector base emitter 2N2222

* Collector resistor: Rc = (Vcc - Vce) / Ic ≈ 6.8k for Vce ≈ 5.2V
RC vcc collector 6.8k

* Emitter resistor (DC stability) + bypass cap (AC gain)
RE emitter 0 680
CE emitter 0 100u

* Input coupling
Vin in 0 AC 10m SIN(0 10m 1k)
Cin in base 10u

* Output coupling
Cout collector out 10u
RL out 0 10k

* Analysis
.op
.ac dec 50 10 10Meg
.tran 10u 5m

* Measurements
.measure AC gain_mid MAX vdb(out)
.measure AC f3dB_low WHEN vdb(out)=gain_mid-3 CROSS=1
.measure AC f3dB_high WHEN vdb(out)=gain_mid-3 CROSS=LAST

.control
run
plot vdb(out) xlimit 10 10Meg ylabel "Gain (dB)"
plot v(out) v(in)*100 xlimit 0 5m
.endc

.end
```

Design calculations:
- **Bias point**: Vb = Vcc × R2/(R1+R2) = 12 × 4.7/26.7 = 2.11V, Ve = Vb - 0.7 = 1.41V
- **Ic** ≈ Ve/Re = 1.41/680 = 2.07mA
- **Vce** = Vcc - Ic×(Rc+Re) = 12 - 2.07m×7.48k = 12 - 15.5 → need to adjust
- Better: Ic ≈ 1mA with Re=1.5k → Ve = 1.5V, Vb = 2.2V, R1=27k, R2=5.6k
- **AC gain** = -Rc/re' where re' = 26mV/Ic = 26Ω → Av ≈ -6800/26 = -261 (with bypass cap)
- **Bandwidth**: f_low ≈ 1/(2π×Cin×Rin) ≈ 10Hz, f_high limited by Cjc Miller effect""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "My SPICE simulation won't converge. I'm getting 'singular matrix' and 'timestep too small' errors. How do I debug this?",
            },
            {
                "from": "gpt",
                "value": """SPICE convergence debugging checklist:

**1. Singular Matrix Error**
Usually means a floating node or voltage source loop:
```spice
* BAD: node 'mid' has no DC path to ground
R1 in mid 1k
C1 mid out 1u
* FIX: add a high-value resistor to ground
Rleak mid 0 1G
```

```spice
* BAD: two voltage sources in parallel
V1 a b 5
V2 a b 5
* FIX: add a small series resistance
V1 a mid 5
Rser mid b 1m
V2 a b 5
```

**2. Timestep Too Small**
Cause: rapid switching or discontinuities. Solutions:

```spice
* Option A: Relax tolerances (try first)
.options reltol=0.01      ; default 0.001
.options abstol=1p        ; default 1p, try 10p
.options vntol=1m         ; default 1u, try 1m
.options itl4=200         ; default 10, increase iterations
.options method=gear      ; try Gear instead of Trapezoidal

* Option B: Use UIC (Use Initial Conditions) to skip DC operating point
.tran 1u 10m UIC
.ic V(cap_node)=0 V(out)=2.5

* Option C: Ramp power supply instead of step
VCC vcc 0 PWL(0 0 1m 12)  ; 1ms ramp instead of instant 12V
```

**3. DC Operating Point Fails**
```spice
* Add .nodeset hints for the solver
.nodeset V(base)=2.1 V(collector)=6.5 V(emitter)=1.4

* Or use GMIN stepping
.options gmin=1e-12       ; default, try 1e-9
.options gminsteps=100    ; more GMIN stepping iterations
```

**4. MOSFET Convergence Issues**
```spice
* Smooth transitions with subthreshold model
.options tnom=27
.options itl1=500         ; more DC iterations
.options itl2=200         ; more DC transfer curve iterations

* Add small parallel resistance to prevent floating gates
Rgate gate drain 100Meg
```

**5. Systematic Approach**
1. Start with `.op` only — if that fails, fix DC bias first
2. Use `.tran` with large timestep first, then reduce
3. Add `.save` to limit output data
4. Check every node has a DC path to ground
5. Check no inductor loops without resistance
6. Replace ideal switches with smooth PWL sources
7. Verify device model parameters (especially IS, BV for diodes)""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a PySpice script to simulate a low-pass RC filter and plot the Bode diagram.",
            },
            {
                "from": "gpt",
                "value": """PySpice Bode plot for a low-pass RC filter:

```python
import numpy as np
import matplotlib.pyplot as plt
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

# Create circuit
circuit = Circuit('Low-Pass RC Filter')

# Components: fc = 1/(2*pi*R*C) = 1/(2*pi*1k*100n) ≈ 1.59 kHz
circuit.V('input', 'input', circuit.gnd, 'AC 1')
circuit.R(1, 'input', 'output', 1@u_kΩ)
circuit.C(1, 'output', circuit.gnd, 100@u_nF)

# Create simulator
simulator = circuit.simulator(temperature=25, nominal_temperature=25)

# AC analysis: 10 Hz to 10 MHz, 50 points per decade
analysis = simulator.ac(start_frequency=10@u_Hz,
                        stop_frequency=10@u_MHz,
                        number_of_points=50,
                        variation='dec')

# Extract data
frequency = np.array(analysis.frequency)
vout = np.array(analysis['output'])

# Calculate magnitude (dB) and phase (degrees)
gain_db = 20 * np.log10(np.abs(vout))
phase_deg = np.degrees(np.angle(vout))

# Bode plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

# Magnitude
ax1.semilogx(frequency, gain_db, 'b-', linewidth=2)
ax1.axhline(y=-3, color='r', linestyle='--', alpha=0.7, label='-3dB')
ax1.axvline(x=1591, color='g', linestyle='--', alpha=0.7, label=f'fc = 1.59 kHz')
ax1.set_ylabel('Gain (dB)')
ax1.set_title('Bode Plot — RC Low-Pass Filter (R=1kΩ, C=100nF)')
ax1.grid(True, which='both', alpha=0.3)
ax1.legend()
ax1.set_ylim(-60, 5)

# Phase
ax2.semilogx(frequency, phase_deg, 'r-', linewidth=2)
ax2.axhline(y=-45, color='g', linestyle='--', alpha=0.7, label='-45° at fc')
ax2.set_ylabel('Phase (°)')
ax2.set_xlabel('Frequency (Hz)')
ax2.grid(True, which='both', alpha=0.3)
ax2.legend()
ax2.set_ylim(-100, 10)

plt.tight_layout()
plt.savefig('bode_rc_filter.png', dpi=150)
plt.show()

# Print key measurements
fc_idx = np.argmin(np.abs(gain_db + 3))
print(f"Cutoff frequency (-3dB): {frequency[fc_idx]:.1f} Hz")
print(f"DC gain: {gain_db[0]:.2f} dB")
print(f"Phase at fc: {phase_deg[fc_idx]:.1f}°")
print(f"Roll-off: {(gain_db[-1] - gain_db[fc_idx]) / np.log10(frequency[-1]/frequency[fc_idx]):.1f} dB/decade")
```

Expected output:
- fc ≈ 1591 Hz (-3dB point)
- Phase at fc = -45°
- Roll-off = -20 dB/decade (first-order filter)
- DC gain = 0 dB

Install: `pip install PySpice` + ngspice must be installed (`apt install ngspice`).""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Create a SPICE netlist for a 555 timer in astable mode generating a 1kHz square wave.",
            },
            {
                "from": "gpt",
                "value": """555 timer astable oscillator at 1kHz:

```spice
* 555 Timer Astable Mode - 1kHz Square Wave
* Using generic 555 subcircuit

.subckt NE555 GND TRIGGER OUTPUT RESET CONTROL THRESHOLD DISCHARGE VCC
* Simplified behavioral model
R1 VCC CONTROL 5k
R2 CONTROL ref1 5k
R3 ref1 GND 5k
* Comparators
B1 comp_hi 0 V = V(THRESHOLD) > V(CONTROL) ? 1 : 0
B2 comp_lo 0 V = V(TRIGGER) < V(ref1) ? 1 : 0
* SR flip-flop (behavioral)
B3 ff_out 0 V = V(comp_lo) > 0.5 ? 5 : (V(comp_hi) > 0.5 ? 0 : V(ff_out))
* Output driver
B4 OUTPUT GND V = V(ff_out) > 2.5 ? V(VCC)-1.5 : 0.1
* Discharge transistor
S1 DISCHARGE GND ff_out GND SMOD
.model SMOD SW(VT=2.5 RON=10 ROFF=100Meg)
.ends NE555

* Power
VCC vcc 0 5

* Timing components
* f = 1.44 / ((Ra + 2*Rb) * C)
* For 1kHz with ~50% duty: Ra=720, Rb=720, C=1uF
* f = 1.44 / ((720 + 1440) * 1e-6) = 1.44 / 2.16e-3 = 666Hz
* Adjusted: Ra=330, Rb=680, C=1uF → f = 1.44 / (1.69e-3) = 852Hz
* Better: Ra=470, Rb=470, C=680nF → f = 1.44 / (1.41e-3 * 680e-9)... use online calc
*
* Simpler: Ra=6.8k, Rb=3.3k, C=100nF
* f = 1.44 / ((6.8k + 6.6k) * 100n) = 1.44 / 1.34e-3 = 1074Hz ≈ 1kHz
* Duty = (Ra+Rb)/(Ra+2Rb) = 10.1/13.4 = 75.4%

Ra vcc discharge 6.8k
Rb discharge threshold 3.3k
Ct threshold 0 100n IC=0

* 555 connections
X1 0 trigger output 0 control threshold discharge vcc NE555
* Trigger tied to threshold for astable
.connect trigger threshold

* Bypass cap on control pin
Cbypass control 0 10n

.tran 10u 10m UIC

.control
run
plot v(output) v(threshold)
meas tran period TRIG v(output) VAL=2.5 RISE=1 TARG v(output) VAL=2.5 RISE=2
meas tran freq PARAM='1/period'
.endc

.end
```

For near 50% duty cycle, use a diode across Rb:
```spice
D1 threshold discharge 1N4148
* Charge through Ra only, discharge through Rb only
* Duty ≈ Ra/(Ra+Rb) = 6.8/(6.8+3.3) = 67%
```

For exact 50% duty, use CMOS 555 (TLC555) or add a flip-flop divider at output.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a SPICE netlist for an op-amp inverting amplifier with gain of -10, and verify the bandwidth with AC analysis.",
            },
            {
                "from": "gpt",
                "value": """Op-amp inverting amplifier (gain = -10) with bandwidth verification:

```spice
* Inverting Amplifier: Gain = -Rf/Ri = -100k/10k = -10
* Using UA741 op-amp model

.model UA741 opamp (LEVEL=3 GBWP=1MEG SLEW=0.5MEG
+ ROUT=75 RIN=2MEG IOS=20N VOFF=1M CMRR=90 PSRR=90
+ PM=60 APTS=1M VOH=13.5 VOL=-13.5)

* Power supplies
VCC vcc 0 15
VEE vee 0 -15

* Input signal
Vin in 0 AC 0.1 SIN(0 0.1 1k)

* Inverting amplifier
Ri in vminus 10k
Rf vminus out 100k

* Op-amp: non-inverting input to ground
XU1 0 vminus vcc vee out UA741

* Load
RL out 0 10k

* Analysis
.op
.ac dec 100 1 100Meg
.tran 1u 5m

.control
run

* Bode plot
plot vdb(out) xlimit 1 100Meg ylabel "Gain (dB)"
plot vp(out) xlimit 1 100Meg ylabel "Phase (deg)"

* Time domain
plot v(out) v(in)

* Measurements
meas AC gain_dc FIND vdb(out) AT=100
meas AC bw WHEN vdb(out)='gain_dc-3' CROSS=LAST
print gain_dc bw
.endc

.end
```

Expected results:
- **DC gain**: 20 dB (= 20×log10(10))
- **Bandwidth**: GBW/Gain = 1MHz/10 = 100kHz (for UA741)
- **Phase margin**: check stability — should be >45° at unity gain crossover

Gain-bandwidth product is constant for a voltage-feedback op-amp:
- GBW = Gain × Bandwidth = 10 × 100kHz = 1MHz ✓

For higher bandwidth, use an op-amp with higher GBW (e.g., OPA2134: 8MHz → BW = 800kHz at gain of 10).""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Simulate a full-wave bridge rectifier with capacitor filter in SPICE. Calculate ripple voltage.",
            },
            {
                "from": "gpt",
                "value": """Full-wave bridge rectifier with capacitor filter:

```spice
* Full-Wave Bridge Rectifier
* Input: 12Vrms 50Hz, Output: ~15.5V DC with ripple

* AC source (12Vrms = 16.97V peak)
Vac in1 in2 SIN(0 16.97 50)

* Bridge rectifier (4 diodes)
D1 in1 dcplus 1N4007
D2 dcminus in1 1N4007
D3 in2 dcplus 1N4007
D4 dcminus in2 1N4007

.model 1N4007 D (IS=76.9p RS=42.0m BV=1000 IBV=5.00u
+ CJO=26.5p M=0.333 N=1.45 TT=4.32u)

* Filter capacitor
Cfilt dcplus dcminus 1000u IC=0

* Load
Rload dcplus dcminus 100

* Analysis
.tran 100u 200m UIC

.control
run

* Plot output voltage and input
plot v(dcplus,dcminus) v(in1,in2) xlimit 100m 200m

* Measure ripple (after steady state)
meas tran Vmax MAX v(dcplus,dcminus) FROM=150m TO=200m
meas tran Vmin MIN v(dcplus,dcminus) FROM=150m TO=200m
meas tran Vripple PARAM='Vmax-Vmin'
meas tran Vdc AVG v(dcplus,dcminus) FROM=150m TO=200m

print Vmax Vmin Vripple Vdc
.endc

.end
```

Analytical verification:
- Vpeak = 16.97V - 2×0.7V (two diode drops) = 15.57V
- Ripple voltage: Vr = Iload / (2 × f × C) = (15.57/100) / (2 × 50 × 1000µ) = 1.56V
- Vdc ≈ Vpeak - Vr/2 = 15.57 - 0.78 = 14.79V

For lower ripple:
- Increase C: 2200µF → Vr ≈ 0.71V
- Increase Rload (lower current)
- Use LC filter: add 10mH inductor before capacitor

Diode selection criteria:
- PIV = Vpeak = 16.97V → 1N4007 (1000V PIV) is overkill but safe
- Iavg = Idc = 155.7mA → 1N4007 rated 1A ✓
- Isurge at power-on can be 10-20× Iavg""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a SPICE subcircuit model for a voltage regulator (LM7805) and test it.",
            },
            {
                "from": "gpt",
                "value": """LM7805 behavioral SPICE model with test circuit:

```spice
* LM7805 Voltage Regulator - Behavioral Model

.subckt LM7805 IN OUT GND
* Parameters: Vout=5V, dropout=2V, Iq=5mA, line_reg=3mV/V, load_reg=15mV/A
* Thermal shutdown at 150°C (not modeled here)

* Internal reference and error amplifier (behavioral)
Bref ref GND V = 1.25
Rfb1 OUT fb 3k    ; feedback: Vout = 1.25 * (1 + R1/R2) = 1.25 * 4 = 5V
Rfb2 fb GND 1k

* Error amplifier → controls pass transistor
Berr ctrl GND V = MAX(MIN(1000*(V(ref)-V(fb)), V(IN,GND)-0.3), 0)

* Pass transistor (controlled source)
Gpass IN OUT ctrl GND 1  ; transconductance
Rout OUT GND 100k        ; output impedance

* Quiescent current
Iq IN GND 5m

* Output current limit (behavioral)
Blimit sense GND V = I(Gpass) > 1.5 ? 1 : 0

* Thermal protection would go here (temperature-dependent)
.ends LM7805

* ===== Test Circuit =====

* Input: 9V DC (unregulated)
Vin vin 0 9

* Input filter cap
Cin vin 0 330n

* Regulator
X1 vin vout 0 LM7805

* Output filter cap (required for stability)
Cout vout 0 100n

* Load: 100mA
Rload vout 0 50

* Test: sweep input voltage to verify regulation
.dc Vin 3 15 0.1

* Transient: load step response
Iload vout 0 PULSE(100m 500m 5m 1u 1u 5m 20m)
.tran 10u 20m

.control
run

* Line regulation plot
plot v(vout) vs v(vin) title "Line Regulation"

* Load transient response
plot v(vout) title "Load Step Response"

meas dc Vout_reg FIND v(vout) AT=9
meas dc Vdropout WHEN v(vout)=4.9 CROSS=1
print Vout_reg Vdropout
.endc

.end
```

Key specifications (real LM7805):
- Output voltage: 5.0V ±4% (4.8-5.2V)
- Dropout voltage: 2.0V (Vin min = 7V)
- Line regulation: 3-100 mV (Vin = 7-25V)
- Load regulation: 15-100 mV (Iout = 5-1500mA)
- Max output current: 1.5A (with heatsink)
- Quiescent current: 5-8 mA

Thermal: P = (Vin-Vout) × Iout = (9-5) × 0.5 = 2W → needs heatsink if Rθja > 60°C/W""",
            },
        ]
    },
]


PYSPICE_SYSTEM_PROMPT = (
    "You are an expert in PySpice, the Python interface for ngspice. "
    "You write correct PySpice code for analog and digital circuit simulation, "
    "including MOSFET models (NMOS/PMOS), transient/AC/DC analysis, subcircuits, "
    "and matplotlib visualization. You follow best practices: ground node defined, "
    "proper units (@u_V, @u_kOhm, etc.), convergence options, and error handling."
)

SPICE_KEYWORDS = [
    "spice",
    "netlist",
    "simulation",
    "ltspice",
    "ngspice",
    "pspice",
    "hspice",
    "pyspice",
    ".tran",
    ".ac",
    ".dc",
    ".op",
    ".subckt",
    ".model",
    "circuit",
    "amplifier",
    "filter",
    "transistor",
    "op-amp",
    "opamp",
    "oscillat",
    "rectif",
    "capacitor",
    "inductor",
    "diode",
    "mosfet",
    "bjt",
    "jfet",
    "voltage regulator",
    "power supply",
    "feedback",
    "bode",
    "frequency response",
    "gain",
    "bandwidth",
    "phase margin",
    "common emitter",
    "common source",
    "differential",
    "cascode",
    "analog",
    "bias",
    "small signal",
    "transfer function",
]


def build_from_external() -> list[dict]:
    """Load external datasets: Masala-CHAI (SPICE netlists) + SPICEPilot (PySpice code)."""
    samples = []
    ext_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "external")

    # --- 1. Masala-CHAI: 2950 SPICE netlists (OpenAI messages → ShareGPT) ---
    chai_path = os.path.join(ext_dir, "Masala-CHAI", "analoggenie.jsonl")
    if os.path.isfile(chai_path):
        print("  Loading Masala-CHAI analoggenie.jsonl...")
        count = 0
        with open(chai_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                messages = row.get("messages", [])
                if len(messages) < 2:
                    continue
                # Convert OpenAI messages format → ShareGPT format
                convos = []
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if not content:
                        continue
                    if role == "system":
                        convos.append({"from": "system", "value": content})
                    elif role == "user":
                        convos.append({"from": "human", "value": content})
                    elif role == "assistant":
                        convos.append({"from": "gpt", "value": content})
                if len(convos) >= 2:
                    # Ensure system prompt exists
                    if convos[0]["from"] != "system":
                        convos.insert(0, {"from": "system", "value": SYSTEM_PROMPT})
                    samples.append({"conversations": convos})
                    count += 1
        print(f"    Got {count} Masala-CHAI SPICE netlist examples")
    else:
        print(f"  [!] Masala-CHAI not found at {chai_path}")
        print(
            "      Clone: git clone https://github.com/jitx-inc/Masala-CHAI.git finetune/external/Masala-CHAI"
        )

    # --- 2. SPICEPilot: PySpice code files → Q&A pairs ---
    spicepilot_dir = os.path.join(ext_dir, "SPICEPilot")
    if os.path.isdir(spicepilot_dir):
        print("  Loading SPICEPilot PySpice examples...")
        count = 0
        # Walk Claude_tests and GPT_tests for .py files
        for test_dir in ["Claude_tests", "GPT_tests"]:
            base = os.path.join(spicepilot_dir, test_dir)
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for fname in sorted(files):
                    if not fname.endswith(".py"):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        code = f.read()
                    if len(code) < 100:
                        continue
                    # Infer circuit name from code
                    circuit_name = "circuit"
                    for cl in code.splitlines():
                        if "Circuit(" in cl:
                            match = re.search(r"Circuit\(['\"](.+?)['\"]\)", cl)
                            if match:
                                circuit_name = match.group(1)
                            break
                    # Determine difficulty from path
                    difficulty = "medium"
                    path_lower = root.lower()
                    if "easy" in path_lower:
                        difficulty = "easy"
                    elif "hard" in path_lower:
                        difficulty = "hard"

                    question = (
                        f"Write a PySpice script to simulate a {circuit_name}. "
                        f"Include MOSFET models, transient analysis, and plotting. "
                        f"Difficulty: {difficulty}."
                    )
                    answer = f"PySpice simulation of {circuit_name}:\n\n```python\n{code}\n```"
                    samples.append(
                        {
                            "conversations": [
                                {"from": "system", "value": PYSPICE_SYSTEM_PROMPT},
                                {"from": "human", "value": question},
                                {"from": "gpt", "value": answer},
                            ]
                        }
                    )
                    count += 1
        print(f"    Got {count} SPICEPilot PySpice code examples")

        # --- 3. SPICEPilot benchmark: circuit descriptions → design Q&A ---
        bench_path = os.path.join(spicepilot_dir, "New_bench-mark.md")
        if os.path.isfile(bench_path):
            print("  Loading SPICEPilot benchmark descriptions...")
            with open(bench_path, "r", encoding="utf-8") as f:
                bench_text = f.read()
            # Parse numbered entries: N. **Name** \n - **Description:** text
            entries = re.findall(
                r"\d+\.\s+\*\*(.+?)\*\*\s*\n\s*-\s*\*\*Description:\*\*\s*(.+?)(?=\n\n|\n\d+\.|\n---|\Z)",
                bench_text,
                re.DOTALL,
            )
            count = 0
            for name, desc in entries:
                name = name.strip()
                desc = desc.strip()
                if len(desc) < 20:
                    continue
                question = f"Describe the design of a {name} circuit for SPICE simulation. How does it work and what are the key transistor connections?"
                answer = f"**{name}**\n\n{desc}\n\nTo simulate this in SPICE:\n1. Define NMOS and PMOS models with appropriate parameters (kp, vto, lambda, w, l)\n2. Connect transistors as described above\n3. Add input sources (pulse or sinusoidal depending on the circuit type)\n4. Run transient analysis to verify timing and voltage levels\n5. Check DC operating point to verify bias conditions"
                samples.append(
                    {
                        "conversations": [
                            {"from": "system", "value": SYSTEM_PROMPT},
                            {"from": "human", "value": question},
                            {"from": "gpt", "value": answer},
                        ]
                    }
                )
                count += 1
            print(f"    Got {count} SPICEPilot benchmark circuit descriptions")
    else:
        print(f"  [!] SPICEPilot not found at {spicepilot_dir}")
        print(
            "      Clone: git clone https://github.com/DavidLanworworworthy/SPICEPilot.git finetune/external/SPICEPilot"
        )

    # --- 4. symbench/spice-datasets: 6249 real SPICE netlists ---
    symbench_dir = os.path.join(ext_dir, "spice-datasets")
    if os.path.isdir(symbench_dir):
        print("  Loading symbench/spice-datasets (LTspice + KiCad netlists)...")
        count = 0
        for subdir in ["ltspice_demos", "ltspice_examples", "kicad_github"]:
            src_dir = os.path.join(symbench_dir, subdir)
            if not os.path.isdir(src_dir):
                continue
            for root, _dirs, files in os.walk(src_dir):
                for fname in sorted(files):
                    if not fname.endswith((".net", ".sp", ".cir")):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            netlist = f.read()
                    except Exception:
                        continue
                    if len(netlist) < 50 or len(netlist) > 8000:
                        continue
                    # Extract circuit name from first comment or filename
                    circuit_name = (
                        fname.replace(".net", "").replace(".sp", "").replace(".cir", "")
                    )
                    first_line = netlist.splitlines()[0] if netlist.splitlines() else ""
                    if first_line.startswith("*"):
                        circuit_name = (
                            first_line.lstrip("* ").strip()[:80] or circuit_name
                        )
                    source = subdir.replace("_", " ").title()
                    question = f"Write a SPICE netlist for: {circuit_name}"
                    answer = (
                        f"SPICE netlist ({source}):\n\n```spice\n{netlist.strip()}\n```"
                    )
                    samples.append(
                        {
                            "conversations": [
                                {"from": "system", "value": SYSTEM_PROMPT},
                                {"from": "human", "value": question},
                                {"from": "gpt", "value": answer},
                            ]
                        }
                    )
                    count += 1
        print(f"    Got {count} symbench SPICE netlist examples")
    else:
        print(f"  [!] symbench/spice-datasets not found at {symbench_dir}")
        print(
            "      Clone: git clone https://github.com/symbench/spice-datasets.git finetune/external/spice-datasets"
        )

    return samples


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download EE Q&A from HuggingFace and convert to ShareGPT format."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. STEM-AI Electrical Engineering
    print("  Downloading STEM-AI-mtl/Electrical-engineering (SPICE-related)...")
    try:
        ds = load_dataset(
            "STEM-AI-mtl/Electrical-engineering", split="train", streaming=True
        )
        count = 0
        for row in ds:
            instruction = row.get("instruction", "")
            output = row.get("output", "")
            if not instruction or not output:
                continue
            text_lower = (instruction + output).lower()
            if any(kw in text_lower for kw in SPICE_KEYWORDS):
                samples.append(
                    {
                        "conversations": [
                            {"from": "system", "value": SYSTEM_PROMPT},
                            {"from": "human", "value": instruction},
                            {"from": "gpt", "value": output},
                        ]
                    }
                )
                count += 1
                if count >= max_samples:
                    break
        print(f"    Got {count} STEM-AI circuit/SPICE examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. Electronics StackExchange (SPICE/analog filter)
    # Columns: Id, Tags, Answer, Body, Title, CreationDate
    print("  Downloading bshada/electronics.stackexchange.com (SPICE/analog filter)...")
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
            if not any(kw in combined for kw in SPICE_KEYWORDS):
                continue
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
        print(f"    Got {count} Electronics SE (SPICE/analog) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. Netlist instruction→SPICE pairs
    print("  Downloading goihere/Netlist_data...")
    try:
        ds = load_dataset("goihere/Netlist_data", split="train", streaming=True)
        count = 0
        for row in ds:
            text = row.get("combined_text", "") or row.get("text", "")
            if not text or len(text) < 50:
                continue
            # Parse ###Prompt: / ###Answer: format
            if "###Prompt:" in text and "###Answer:" in text:
                parts = text.split("###Answer:")
                prompt = parts[0].replace("###Prompt:", "").strip()
                answer = parts[1].strip() if len(parts) > 1 else ""
            else:
                # Fallback: use as-is
                prompt = "Generate a SPICE netlist for this circuit."
                answer = text.strip()
            if not answer or len(answer) < 30:
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": prompt},
                        {"from": "gpt", "value": answer},
                    ]
                }
            )
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} netlist instruction examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 4. Circuit Q&A (text only from multimodal dataset)
    print("  Downloading ayoubkirouane/Circuit (text Q&A)...")
    try:
        ds = load_dataset("ayoubkirouane/Circuit", split="train", streaming=True)
        count = 0
        for row in ds:
            texts = row.get("texts", [])
            if not texts:
                continue
            # Extract user/assistant pairs
            convos = [{"from": "system", "value": SYSTEM_PROMPT}]
            for t in texts:
                if isinstance(t, dict):
                    if t.get("user"):
                        convos.append({"from": "human", "value": t["user"]})
                    if t.get("assistant"):
                        convos.append({"from": "gpt", "value": t["assistant"]})
            if len(convos) >= 3:  # system + at least 1 Q&A pair
                samples.append({"conversations": convos})
                count += 1
                if count >= max_samples:
                    break
        print(f"    Got {count} Circuit Q&A examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 5. Open schematics (description → components as Q&A)
    print("  Downloading bshada/open-schematics (circuit descriptions)...")
    try:
        ds = load_dataset("bshada/open-schematics", split="train", streaming=True)
        count = 0
        for row in ds:
            name = row.get("name", "")
            desc = row.get("description", "")
            components = row.get("components_used", [])
            if not desc or len(desc) < 30 or not components:
                continue
            combined = (name + " " + desc).lower()
            if not any(kw in combined for kw in SPICE_KEYWORDS[:20]):
                continue
            comp_list = (
                ", ".join(components[:20])
                if isinstance(components, list)
                else str(components)
            )
            question = f"Design a circuit for: {desc.strip()}"
            answer = f"Circuit: {name}\n\nComponents needed:\n{comp_list}\n\nDescription: {desc.strip()}"
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question[:1000]},
                        {"from": "gpt", "value": answer[:4000]},
                    ]
                }
            )
            count += 1
            if count >= max_samples // 2:
                break
        print(f"    Got {count} open-schematics examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 6. Vrindarani/netlistgen: 106 prompt→SPICE netlist pairs
    print("  Downloading Vrindarani/netlistgen (prompt→netlist pairs)...")
    try:
        ds = load_dataset("Vrindarani/netlistgen", split="train", streaming=True)
        count = 0
        for row in ds:
            prompt = row.get("Prompt", "") or row.get("prompt", "")
            answer = row.get("Answer", "") or row.get("answer", "")
            if not prompt or not answer or len(answer) < 30:
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": prompt.strip()},
                        {"from": "gpt", "value": answer.strip()},
                    ]
                }
            )
            count += 1
        print(f"    Got {count} netlistgen prompt→netlist examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(description="Build SPICE fine-tuning dataset")
    parser.add_argument(
        "--with-hf", action="store_true", help="Include HuggingFace datasets"
    )
    parser.add_argument(
        "--with-external", action="store_true", help="Include Masala-CHAI + SPICEPilot"
    )
    parser.add_argument("--max-samples", type=int, default=1000, help="Max HF samples")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "spice_chat.jsonl")

    all_samples = list(SEED_EXAMPLES)
    print(f"  {len(SEED_EXAMPLES)} seed examples")

    if args.with_external:
        ext_samples = build_from_external()
        all_samples.extend(ext_samples)

    if args.with_hf:
        hf_samples = build_from_huggingface(args.max_samples)
        all_samples.extend(hf_samples)

    with open(output_path, "w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n  Wrote {len(all_samples)} examples to {output_path}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
