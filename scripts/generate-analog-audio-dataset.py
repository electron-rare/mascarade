"""Generate analog electronics + audio design Q&A dataset via Codestral."""

import json
import time
import os
import httpx
import random

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
OUTPUT = "finetune/datasets/analog_audio_electronics.jsonl"

CATEGORIES = [
    {
        "name": "Op-Amp Circuits",
        "count": 300,
        "topics": [
            "Design a {topology} amplifier with gain {gain}dB using {opamp}",
            "Calculate input/output impedance of {topology} configuration with {opamp}",
            "Stability analysis and compensation for {opamp} in {topology} configuration",
            "Noise analysis of {opamp} circuit for {application}",
            "Common-mode rejection ratio optimization for {topology} using {opamp}",
            "Power supply rejection ratio improvement for {opamp} circuit",
            "Slew rate limitations of {opamp} in {application}",
            "Design instrumentation amplifier with CMRR > {cmrr}dB",
            "Active rectifier circuit using {opamp} for {application}",
            "Sample-and-hold circuit design with {opamp}",
        ],
    },
    {
        "name": "Active Filters",
        "count": 300,
        "topics": [
            "Design {order}-order {filter_type} {response} filter at {freq} cutoff",
            "Sallen-Key {filter_type} filter with Q={q} using {opamp}",
            "Multiple feedback (MFB) {filter_type} filter design",
            "State-variable filter for simultaneous LP/HP/BP at {freq}",
            "Notch filter at {notch_freq} for {application}",
            "All-pass filter for {phase_shift} phase shift at {freq}",
            "Anti-aliasing filter design for {sample_rate} ADC",
            "Crossover network design at {crossover_freq} for {type} speakers",
            "Parametric equalizer band with {bandwidth} octave width",
            "RIAA phono equalization curve implementation",
        ],
    },
    {
        "name": "Audio Amplifiers",
        "count": 300,
        "topics": [
            "Design Class {class} audio amplifier with {power}W into {impedance} ohms",
            "Headphone amplifier design for {impedance} ohm headphones",
            "Microphone preamplifier with {gain}dB gain and phantom power",
            "Guitar amplifier preamp stage with {tubes} topology",
            "Class D amplifier design using {ic} for {power}W output",
            "Balanced line driver/receiver for professional audio",
            "Phono preamplifier for {cartridge} cartridge",
            "Summing amplifier mixer with {channels} channels",
            "Audio AGC (automatic gain control) circuit design",
            "THD+N analysis and optimization for audio amplifier",
        ],
    },
    {
        "name": "DAC/ADC Circuits",
        "count": 200,
        "topics": [
            "Design I/V converter for {dac} current-output DAC",
            "Anti-aliasing filter for {bits}-bit ADC at {sample_rate}",
            "Reference voltage circuit for {bits}-bit {type} converter",
            "Differential to single-ended conversion for ADC input",
            "Oversampling and decimation filter design for {bits}-bit audio",
            "Jitter analysis and clock distribution for audio DAC",
            "Multi-channel ADC input multiplexing design",
            "Sigma-delta modulator for {bits}-bit audio at {sample_rate}",
        ],
    },
    {
        "name": "Power Supply Design",
        "count": 300,
        "topics": [
            "Design {topology} converter: {vin}V to {vout}V at {current}A",
            "LDO regulator selection and design for {application}",
            "Feedback loop compensation for {topology} converter",
            "EMI filter design for {topology} switching converter",
            "Soft-start circuit for {topology} power supply",
            "Current limiting and protection for {topology} supply",
            "MPPT solar charge controller design for {panel}W panel",
            "Li-ion battery charger with CC/CV using {ic}",
            "Dual rail supply (+/-{voltage}V) for audio circuits",
            "Power sequencing for multi-rail system",
            "Efficiency optimization: light-load vs full-load for {topology}",
            "Thermal design for {power}W dissipation with {package} package",
        ],
    },
    {
        "name": "Oscillators and PLLs",
        "count": 200,
        "topics": [
            "Design {type} oscillator at {freq} with {stability} stability",
            "VCO design for {freq_range} range with {tuning}V tuning",
            "Crystal oscillator circuit for {freq} with {ppm} ppm accuracy",
            "PLL design for clock synthesis: {ref_freq} to {out_freq}",
            "Wien bridge oscillator with amplitude stabilization",
            "Relaxation oscillator using {component} for {freq}",
            "Colpitts oscillator design for {freq} RF application",
            "555 timer astable/monostable for {application}",
            "DDS (direct digital synthesis) circuit implementation",
            "Jitter specification and measurement for clock oscillator",
        ],
    },
    {
        "name": "Eurorack/Synth Design",
        "count": 200,
        "topics": [
            "Design Eurorack {module_type} module with {cv_range}V CV input",
            "VCA circuit for Eurorack using {topology} with CV control",
            "Envelope generator (ADSR) analog circuit for Eurorack",
            "Eurorack power supply design (+12V/-12V/+5V) from {source}",
            "Eurorack output module with headphone amp and line out",
            "CV-controlled filter (VCF) using {filter_ic} for Eurorack",
            "LFO module with multiple waveforms for Eurorack",
            "Sample and hold module for Eurorack",
            "Analog noise generator (white/pink) for Eurorack",
            "Ring modulator circuit for Eurorack",
            "Quantizer circuit for 1V/oct standard",
            "Eurorack bus board and power distribution design",
        ],
    },
    {
        "name": "Guitar Effects",
        "count": 200,
        "topics": [
            "Design {effect_type} guitar pedal circuit",
            "Overdrive/distortion clipping stage using {clipping} diodes",
            "Analog delay circuit using {ic} BBD chip",
            "Phaser effect using {stages} stages of all-pass filters",
            "Chorus effect circuit with {type} LFO modulation",
            "Wah pedal circuit with {inductor} inductor",
            "Compressor pedal using {topology} detection",
            "Tremolo circuit with optocoupler-based gain control",
            "Fuzz Face circuit analysis and component selection",
            "True bypass switching with relay and JFET",
            "Power supply filtering for guitar pedal board",
            "Buffered vs unbuffered signal chain analysis",
        ],
    },
    {
        "name": "SPICE Simulation",
        "count": 200,
        "topics": [
            "Write ngspice netlist for {circuit} and run {analysis} analysis",
            "LTspice simulation of {circuit} with {analysis}",
            "Monte Carlo analysis of {circuit} with {tolerance}% tolerance",
            "Worst-case analysis for {circuit} component variations",
            "SPICE model creation for {component}",
            "Convergence troubleshooting for {circuit} in ngspice",
            "Parametric sweep of {parameter} in {circuit} simulation",
            "FFT analysis of {circuit} output in SPICE",
            "Noise simulation (.noise) for {circuit} in ngspice",
            "Temperature sweep simulation for {circuit}",
        ],
    },
    {
        "name": "Analog Design Fundamentals",
        "count": 200,
        "topics": [
            "Thevenin/Norton equivalent for {circuit}",
            "Bode plot analysis of {circuit} transfer function",
            "Root locus analysis for {circuit} stability",
            "Impedance matching for {source_z} source to {load_z} load",
            "Decoupling strategy for {ic} on {layer}-layer PCB",
            "Ground plane design for mixed-signal PCB",
            "Star grounding vs ground plane for audio PCB",
            "Crosstalk analysis between analog and digital signals",
            "Component selection: resistor types for {application}",
            "Capacitor types comparison for {application} (ceramic, film, electrolytic)",
        ],
    },
]

VARS = {
    "topology": ["inverting", "non-inverting", "differential", "transimpedance", "summing", "integrator", "differentiator"],
    "gain": ["10", "20", "40", "60", "80"],
    "opamp": ["TL072", "NE5532", "OPA2134", "LM358", "AD8620", "OPA1612", "LM741", "OP07"],
    "application": ["audio preamplifier", "sensor interface", "instrumentation", "active filter", "voltage reference", "DAC output"],
    "cmrr": ["80", "100", "120"],
    "filter_type": ["low-pass", "high-pass", "band-pass", "band-stop"],
    "response": ["Butterworth", "Chebyshev (0.5dB)", "Bessel", "Linkwitz-Riley"],
    "order": ["2nd", "4th", "6th", "8th"],
    "freq": ["20Hz", "100Hz", "1kHz", "3.4kHz", "10kHz", "20kHz", "100kHz"],
    "q": ["0.5", "0.707", "1.0", "2.0", "5.0"],
    "notch_freq": ["50Hz", "60Hz", "120Hz", "1kHz"],
    "phase_shift": ["90", "180"],
    "sample_rate": ["44.1kHz", "48kHz", "96kHz", "192kHz", "384kHz"],
    "crossover_freq": ["80Hz", "500Hz", "2kHz", "3.5kHz"],
    "type": ["2-way", "3-way"],
    "bandwidth": ["1/3", "2/3", "1"],
    "class": ["A", "AB", "B", "D", "H"],
    "power": ["1", "5", "10", "25", "50", "100", "250"],
    "impedance": ["8", "16", "32", "50", "150", "300", "600"],
    "tubes": ["12AX7 single stage", "12AX7 cascaded", "12AU7 cathode follower", "EL84 push-pull"],
    "ic": ["TPA3116", "TPA3255", "MAX98357", "PAM8403", "IRS2092"],
    "cartridge": ["moving magnet (MM)", "moving coil (MC)"],
    "channels": ["4", "8", "16", "32"],
    "dac": ["PCM5102", "ES9038", "AK4490", "WM8741"],
    "bits": ["12", "16", "24", "32"],
    "vin": ["5", "12", "24", "48", "120", "230"],
    "vout": ["1.8", "3.3", "5", "12", "15", "24", "48"],
    "current": ["0.5", "1", "2", "3", "5", "10"],
    "panel": ["10", "50", "100", "250"],
    "voltage": ["5", "9", "12", "15", "24"],
    "package": ["SOT-23", "DPAK", "TO-220", "TO-247"],
    "freq_range": ["1-10kHz", "10-100kHz", "100kHz-1MHz", "1-30MHz"],
    "tuning": ["0-3.3", "0-5", "0-10"],
    "stability": ["0.01%", "0.1%", "1%"],
    "ppm": ["10", "25", "50", "100"],
    "ref_freq": ["10MHz", "25MHz", "50MHz"],
    "out_freq": ["100MHz", "200MHz", "500MHz"],
    "component": ["comparator", "Schmitt trigger", "current mirror"],
    "module_type": ["VCO", "VCF", "VCA", "LFO", "ADSR", "mixer", "sequencer", "noise", "S&H"],
    "cv_range": ["-5 to +5", "0 to +5", "0 to +10"],
    "filter_ic": ["CEM3320", "AS3320", "SSI2164", "OTA (LM13700)"],
    "source": ["USB 5V", "wall adapter 12V", "eurorack bus"],
    "effect_type": ["overdrive", "fuzz", "distortion", "delay", "reverb", "chorus", "phaser", "flanger", "tremolo", "octave"],
    "clipping": ["silicon (1N4148)", "germanium (1N34A)", "LED", "MOSFET", "Schottky"],
    "stages": ["4", "6", "8", "12"],
    "inductor": ["500mH Halo", "Fasel", "custom toroid"],
    "circuit": ["common-emitter amplifier", "differential pair", "current mirror", "Sallen-Key filter", "buck converter", "Class AB output stage", "Wien bridge oscillator", "audio mixer"],
    "analysis": [".ac", ".tran", ".dc", ".noise", ".tf"],
    "tolerance": ["1", "5", "10", "20"],
    "parameter": ["resistance", "capacitance", "supply voltage", "temperature"],
    "source_z": ["50", "600", "10k", "47k"],
    "load_z": ["8", "32", "600", "10k", "1M"],
    "layer": ["2", "4"],
    "ic_name": ["op-amp", "ADC", "DAC", "MCU", "FPGA"],
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
    prompt = f"""You are an expert analog electronics and audio engineer writing training data.

Category: {category_name}
Topic: {topic}

Generate a detailed, technically accurate Q&A pair.
Include specific component values, formulas, SPICE snippets, or design calculations where relevant.
The answer should be 200-500 words.

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
                "max_tokens": 800,
            })
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            if "question" in data and "answer" in data:
                return {
                    "conversations": [
                        {"from": "system", "value": f"You are an expert analog electronics and audio engineer specializing in {category_name}."},
                        {"from": "human", "value": data["question"]},
                        {"from": "gpt", "value": data["answer"]},
                    ],
                    "domain": "analog-audio",
                    "category": category_name,
                    "source": "codestral-teacher-distillation",
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CATEGORIES)
    print(f"=== Analog + Audio Electronics Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs\n")

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

    print(f"\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
