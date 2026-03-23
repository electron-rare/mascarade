"""Generate datasets for ALL missing domains — RF, Linux embedded, Safety, Battery, Thermal, Eurorack, Guitar FX."""

import json
import time
import os
import httpx
import random

CODESTRAL_URL = "https://codestral.mistral.ai/v1/chat/completions"
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "JbYYQUUpHOOFjpV5UuSct6QM4cT6otEl")
OUTPUT = "finetune/datasets/missing_domains.jsonl"

CATEGORIES = [
    # --- RF / Wireless ---
    {
        "name": "RF and Wireless Design",
        "count": 300,
        "topics": [
            "LoRa {chip} module design with antenna matching for {freq}MHz",
            "Sub-GHz radio link budget calculation for {distance}km range",
            "PCB antenna design ({type}) for {freq}MHz",
            "RF impedance matching network (L/Pi/T) for {z_source} to {z_load}",
            "LNA (Low Noise Amplifier) design for {freq}MHz with NF<{nf}dB",
            "RF mixer design for {freq}MHz to IF {if_freq}MHz",
            "VCO design for {freq_range} with phase noise <{phase_noise}dBc/Hz",
            "SAW/BAW filter selection for {freq}MHz {bandwidth}MHz BW",
            "RF PA (Power Amplifier) Class {rf_class} for {power}dBm output",
            "Smith chart matching network design for {application}",
            "Zigbee/Thread mesh network on {chip} with {node_count} nodes",
            "WiFi 6 (802.11ax) antenna diversity on ESP32-S3",
            "BLE 5.x long range (coded PHY) implementation",
            "NFC antenna design and tuning for {standard}",
            "UWB (Ultra-Wideband) ranging with DW3000",
            "RF shielding and isolation on PCB for {application}",
            "Spectrum analyzer measurement of {parameter} for {device}",
            "S-parameter analysis and VNA usage for RF design",
            "RF connector selection (SMA, U.FL, MMCX) and PCB transition",
            "Coexistence design: WiFi + BLE + Sub-GHz on same PCB",
        ],
    },
    # --- Linux Embedded ---
    {
        "name": "Embedded Linux",
        "count": 300,
        "topics": [
            "Yocto Project layer creation for custom {board}",
            "Yocto recipe (.bb) for cross-compiling {application}",
            "Buildroot configuration for minimal Linux on {soc}",
            "Linux device tree overlay for custom {peripheral} on {soc}",
            "Linux kernel driver: {driver_type} for {device}",
            "Linux GPIO/SPI/I2C userspace access via sysfs and libgpiod",
            "Linux real-time (PREEMPT_RT) patch for {latency}us latency",
            "U-Boot customization for {board} with secure boot",
            "Linux systemd service for embedded application autostart",
            "Linux OTA update with RAUC/Mender/SWUpdate for {board}",
            "Cross-compilation toolchain setup for {arch}",
            "Root filesystem optimization: read-only rootfs with overlayfs",
            "Linux framebuffer/DRM display driver for {display}",
            "Video4Linux2 (V4L2) camera capture on {soc}",
            "ALSA audio driver configuration for {codec} on {soc}",
            "Linux CAN bus (SocketCAN) on {soc}",
            "Linux Industrial I/O (IIO) subsystem for {sensor}",
            "Debian/Ubuntu image customization for {sbc}",
            "Docker on embedded Linux ({sbc}) for application containers",
            "Linux perf/ftrace profiling for embedded optimization",
        ],
    },
    # --- Functional Safety ---
    {
        "name": "Functional Safety and Certification",
        "count": 200,
        "topics": [
            "MISRA C:2012 rule {rule_category} compliance for embedded code",
            "IEC 61508 SIL {sil} requirements for {application}",
            "ISO 26262 ASIL {asil} decomposition for automotive ECU",
            "DO-178C DAL {dal} software verification for avionics",
            "IEC 62304 software lifecycle for medical device ({class})",
            "Safety analysis: FMEA for {system}",
            "Safety analysis: FTA (Fault Tree) for {failure_mode}",
            "Watchdog and supervisor IC selection for SIL {sil}",
            "Redundant architecture (1oo2, 2oo3) for safety-critical {application}",
            "Static analysis tools (Polyspace, PC-lint, Coverity) for MISRA",
            "Code coverage (MC/DC) requirements for DO-178C DAL A",
            "Safe state design and graceful degradation",
            "Diagnostic coverage calculation for IEC 61508",
            "Memory protection and MPU for safety partitioning",
            "Certified RTOS selection (SafeRTOS, QNX, INTEGRITY) for {standard}",
        ],
    },
    # --- Battery / BMS ---
    {
        "name": "Battery Management and Energy Harvesting",
        "count": 200,
        "topics": [
            "Li-ion BMS design for {cells}S{parallel}P pack",
            "Cell balancing ({method}) for {cells}S battery pack",
            "Battery fuel gauge (MAX17048/BQ27441) integration",
            "CC/CV charging profile implementation for {chemistry}",
            "Battery protection IC (DW01A, BQ29700) circuit design",
            "MPPT solar controller for {panel}W panel with {mcu}",
            "Supercapacitor sizing for {power}W backup for {duration}s",
            "Energy harvesting from {source} with BQ25570",
            "Wireless charging (Qi) receiver coil and circuit design",
            "USB PD (Power Delivery) sink/source negotiation on {mcu}",
            "Battery thermal management: NTC monitoring and cutoff",
            "State of Charge (SoC) estimation: Coulomb counting vs OCV",
            "State of Health (SoH) estimation over battery lifetime",
            "Battery cycle life prediction and derating",
            "Multi-chemistry charger (Li-ion, LiFePO4, NiMH) design",
        ],
    },
    # --- Thermal Design ---
    {
        "name": "Thermal Design and Management",
        "count": 150,
        "topics": [
            "Heatsink selection for {power}W in {package} package",
            "Thermal resistance calculation: junction to ambient for {ic}",
            "Thermal via array design for {power}W QFN exposed pad",
            "PCB copper pour for thermal management of {component}",
            "Active cooling (fan) design for {power}W enclosed system",
            "Thermal derating curve for {component} at {temp}C ambient",
            "Thermal simulation with ANSYS/COMSOL for PCB assembly",
            "Temperature sensor placement strategy for thermal monitoring",
            "Conformal coating impact on thermal performance",
            "Thermal pad and TIM (Thermal Interface Material) selection",
            "Junction temperature estimation from power dissipation",
            "Thermal runaway prevention in battery/power systems",
        ],
    },
    # --- Eurorack Specific ---
    {
        "name": "Eurorack Synthesizer Design",
        "count": 200,
        "topics": [
            "Eurorack power supply design: +12V/-12V/+5V from {source}",
            "Eurorack bus board and power distribution with protection",
            "VCO (Voltage Controlled Oscillator) core: {vco_type} with 1V/oct tracking",
            "VCF (Voltage Controlled Filter) with {filter_topology} using {filter_ic}",
            "VCA (Voltage Controlled Amplifier) using {vca_type}",
            "ADSR envelope generator: analog discrete vs {ic} IC",
            "LFO module with sine/triangle/square/random waveforms",
            "Eurorack CV input protection and scaling ({cv_range})",
            "Eurorack audio output: AC coupling and impedance matching",
            "Sample & Hold module with JFET and capacitor droop",
            "Analog noise generator (white/pink/red) for Eurorack",
            "Ring modulator with balanced (AD633) vs diode bridge",
            "Quantizer: CV to 1V/oct semitone steps with DAC",
            "Eurorack sequencer: analog shift register vs digital",
            "Wavefolder circuit (Lockhart, Serge) for harmonic generation",
            "Slew limiter / portamento circuit for CV",
            "Clock divider/multiplier module design",
            "Eurorack MIDI-to-CV converter with {mcu}",
            "Panel design and HP spacing for Eurorack modules",
            "Eurorack front panel PCB with tactile switches and LEDs",
        ],
    },
    # --- Guitar Effects Specific ---
    {
        "name": "Guitar Effects Pedal Design",
        "count": 200,
        "topics": [
            "Tube Screamer (TS808/TS9) circuit analysis and clipping variants",
            "Big Muff Pi: tone stack analysis and component selection",
            "Klon Centaur: charge pump, gain structure, and diode blend",
            "Fuzz Face (germanium vs silicon): bias point and temperature stability",
            "RAT distortion: LM308 op-amp and hard clipping analysis",
            "Boss DS-1 circuit: cascaded gain stages and tone control",
            "Analog delay with PT2399 IC: time range and modulation",
            "BBD (Bucket Brigade) chorus/flanger with MN3207/MN3102",
            "Spring reverb driver and recovery amplifier circuit",
            "Digital reverb with FV-1 Spin Semiconductor chip",
            "Phaser: {stages}-stage all-pass with JFET/OTA/LDR",
            "Envelope follower for auto-wah and synth effects",
            "Octave effect: analog (Green Ringer) vs digital (PLL)",
            "Compressor: OTA (CA3080) vs VCA (THAT2180) vs optical",
            "Boost pedal: JFET (2N5457) vs MOSFET (BS170) vs op-amp",
            "True bypass vs buffered bypass: relay, 3PDT, JFET switching",
            "Power supply filtering for guitar pedalboard: isolated vs daisy chain",
            "Expression pedal interface: TRS wiring and voltage divider",
            "Enclosure grounding and shielding for noise reduction",
            "PCB layout guidelines for low-noise guitar pedal design",
        ],
    },
    # --- PCB Layout Avance ---
    {
        "name": "Advanced PCB Layout and Signal Integrity",
        "count": 200,
        "topics": [
            "Stackup design for {layers}-layer PCB with {impedance}ohm controlled impedance",
            "Differential pair routing for USB 3.0 at 5Gbps",
            "DDR4 memory routing: length matching, topology, termination",
            "High-speed SerDes (PCIe Gen4) routing guidelines",
            "Power plane design: split planes, stitching capacitors",
            "Via transition modeling: stub length and back-drilling",
            "Crosstalk analysis and mitigation for parallel traces",
            "Return current path optimization for mixed-signal PCB",
            "Impedance discontinuity at connector transitions",
            "BGA fanout strategy for {pitch}mm pitch {ball_count} balls",
            "Flex-rigid PCB design: bend radius, layer transition",
            "RF PCB design: grounded coplanar waveguide implementation",
            "Thermal relief pad optimization for wave soldering",
            "Teardrops and filleting for manufacturing reliability",
            "Panelization: V-score vs tab routing vs mouse bites",
            "DFM (Design for Manufacturing) checklist for {fab}",
            "ENIG vs HASL vs OSP surface finish selection",
            "Solder paste stencil design: aperture modification for {package}",
            "HDI PCB design: microvias, stacked vias, ELIC",
            "Embedded components in PCB substrate",
        ],
    },
]

VARS = {
    "chip": ["SX1276", "SX1262", "CC1310", "CC1352", "nRF52840", "ESP32-C6", "RAK4631"],
    "freq": ["433", "868", "915", "2400", "5800"],
    "type": ["PCB trace inverted-F", "chip antenna", "PIFA", "patch", "helical", "wire monopole"],
    "distance": ["1", "5", "10", "50"],
    "z_source": ["50", "75"],
    "z_load": ["50", "75", "300"],
    "nf": ["1", "2", "3"],
    "if_freq": ["10.7", "21.4", "70"],
    "freq_range": ["100-200MHz", "400-500MHz", "800-1000MHz", "2.4-2.5GHz"],
    "phase_noise": ["-80", "-100", "-110"],
    "bandwidth": ["1", "5", "10", "20"],
    "rf_class": ["A", "AB", "B", "E", "F"],
    "power": ["10", "20", "27", "30"],
    "node_count": ["10", "50", "100", "500"],
    "standard": ["ISO 14443A", "ISO 15693", "NFC Forum Type 2/4"],
    "parameter": ["harmonic distortion", "output power", "spurious emissions"],
    "device": ["RF PA module", "antenna", "filter", "oscillator"],
    "application": ["IoT sensor", "automotive radar", "industrial telemetry", "medical wearable"],
    "board": ["Raspberry Pi CM4", "BeagleBone Black", "iMX8M", "STM32MP157", "Allwinner H3"],
    "soc": ["STM32MP157", "iMX8M Mini", "Allwinner H616", "Rockchip RK3588", "AM335x"],
    "sbc": ["Raspberry Pi 4", "BeagleBone", "Orange Pi", "NVIDIA Jetson Nano"],
    "peripheral": ["SPI NOR flash", "MIPI DSI display", "USB gadget", "Ethernet PHY", "CAN transceiver"],
    "driver_type": ["character device", "platform driver", "I2C client", "SPI driver", "GPIO interrupt"],
    "arch": ["aarch64", "armhf", "riscv64", "mips"],
    "display": ["HDMI", "MIPI DSI", "LVDS", "RGB parallel"],
    "codec": ["WM8960", "ES8388", "SGTL5000", "TLV320AIC3206"],
    "sensor": ["BMP280 pressure", "MPU6050 IMU", "ADS1115 ADC", "BME680 gas"],
    "latency": ["50", "100", "500"],
    "rule_category": ["mandatory (Required)", "advisory", "decidable", "undecidable"],
    "sil": ["1", "2", "3", "4"],
    "asil": ["A", "B", "C", "D"],
    "dal": ["A", "B", "C", "D", "E"],
    "class": ["Class A", "Class B", "Class C"],
    "system": ["automotive braking", "industrial valve controller", "medical infusion pump"],
    "failure_mode": ["sensor failure", "actuator stuck", "communication loss", "power loss"],
    "cells": ["2", "3", "4", "6", "8", "12"],
    "parallel": ["1", "2", "3"],
    "method": ["passive resistor", "active buck", "active flyback"],
    "chemistry": ["Li-ion (4.2V)", "LiFePO4 (3.6V)", "Li-polymer", "NiMH"],
    "panel": ["5", "10", "50", "100"],
    "mcu": ["STM32L476", "ESP32", "ATtiny1614", "nRF52840"],
    "source": ["piezoelectric vibration", "thermoelectric", "RF ambient", "indoor solar"],
    "duration": ["10", "30", "60", "300"],
    "package": ["SOT-23", "DPAK", "TO-220", "TO-247", "QFN-48", "TQFP-64"],
    "ic": ["LM7805", "LM317", "TPS54331", "LT3748", "STM32H743"],
    "temp": ["40", "60", "85", "105"],
    "component": ["power MOSFET", "voltage regulator", "LED driver", "motor driver"],
    "vco_type": ["triangle core (CEM3340/AS3340)", "sawtooth core", "relaxation", "digital (DDS)"],
    "filter_topology": ["state-variable", "Sallen-Key", "ladder (Moog)", "Steiner-Parker"],
    "filter_ic": ["CEM3320/AS3320", "SSI2164", "LM13700 OTA", "V2164"],
    "vca_type": ["SSI2164 (log)", "THAT2180 (linear)", "LM13700 OTA", "discrete JFET"],
    "cv_range": ["-5V to +5V", "0V to +5V", "0V to +10V"],
    "stages": ["4", "6", "8", "12"],
    "layers": ["2", "4", "6", "8", "10"],
    "impedance": ["50", "75", "90", "100"],
    "pitch": ["0.4", "0.5", "0.65", "0.8", "1.0"],
    "ball_count": ["144", "256", "484", "676"],
    "fab": ["JLCPCB standard", "JLCPCB 4-layer", "PCBWay", "Eurocircuits", "OSH Park"],
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
    prompt = f"""You are an expert electronics engineer writing training data.

Category: {category_name}
Topic: {topic}

Generate a detailed, technically accurate Q&A pair.
Include specific component values, formulas, code snippets, or design calculations.
The answer should be 200-600 words.

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
                "max_tokens": 900,
            })
            resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            if "question" in data and "answer" in data:
                return {
                    "conversations": [
                        {"from": "system", "value": f"You are an expert electronics engineer specializing in {category_name}."},
                        {"from": "human", "value": data["question"]},
                        {"from": "gpt", "value": data["answer"]},
                    ],
                    "domain": category_name.lower().replace(" ", "-"),
                    "category": category_name,
                    "source": "codestral-teacher-distillation",
                }
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    total_target = sum(c["count"] for c in CATEGORIES)
    print("=== Missing Domains Dataset Generator ===")
    print(f"Target: {total_target} Q&A pairs ({len(CATEGORIES)} categories)\n")

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

    print("\n=== SUMMARY ===")
    print(f"Total: {total} Q&A pairs")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT}")
    print(f"Size: {os.path.getsize(OUTPUT) / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
