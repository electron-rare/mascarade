#!/usr/bin/env python3
"""
Mascarade Finetune - Batch Dataset Cleanup
==========================================
STEP 1: Cross-dataset deduplication (global hash, priority-based)
STEP 2: Quality filter on Tier C datasets
STEP 3: Final stats report
"""

import json
import hashlib
import os
import re
from collections import OrderedDict

BASE = "/ai/saisail/mascarade/finetune/datasets"
HF = f"{BASE}/hf_imports"
OUT = f"{BASE}/cleaned_final"

os.makedirs(OUT, exist_ok=True)

# ── Dataset map: name -> path (priority order, highest first) ──
DATASETS = OrderedDict([
    ("spice",         f"{BASE}/spice_chat.jsonl"),
    ("ipc",           f"{BASE}/ipc_jlcpcb_standards_cleaned.jsonl"),
    ("kicad",         f"{BASE}/kicad10_features_cleaned.jsonl"),
    ("emc",           f"{BASE}/emc_chat.jsonl"),
    ("power",         f"{BASE}/power_chat.jsonl"),
    ("dsp",           f"{BASE}/dsp_chat.jsonl"),
    ("analog",        f"{BASE}/analog_audio_electronics_cleaned.jsonl"),
    ("embedded",      f"{BASE}/embedded_systems_full_cleaned.jsonl"),
    ("platformio",    f"{BASE}/platformio_chat.jsonl"),
    ("iot",           f"{BASE}/iot_chat.jsonl"),
    ("freecad",       f"{BASE}/freecad_chat.jsonl"),
    ("stm32",         f"{BASE}/stm32_chat.jsonl"),
    ("missing",       f"{BASE}/missing_domains_cleaned.jsonl"),
    ("rtlcoder3",     f"{HF}/rtlcoder3.jsonl"),
    ("semiconductor", f"{HF}/semiconductor_chat.jsonl"),
    ("kicad-v3",      f"{BASE}/kicad_chat_v3_multi.jsonl"),
])

# ── Domain-specific technical terms for quality filtering ──
DOMAIN_TERMS = {
    "spice": re.compile(
        r"(?i)\b(spice|netlist|subckt|transient|\.ac|\.dc|\.tran|ngspice|ltspice|"
        r"mosfet|bjt|diode|capacitor|inductor|resistor|voltage|current|impedance|"
        r"bode|frequency|gain|phase|simulation|node|ground|vcc|vdd|opamp|op.amp|"
        r"amplifier|feedback|filter|bandwidth|decoupling|bypass|power.supply|"
        r"schematic|circuit|waveform|oscilloscope|probe|sweep|monte.carlo|"
        r"parameter|tolerance|thermal|noise|THD|distortion|harmonic)\b"
    ),
    "dsp": re.compile(
        r"(?i)\b(dsp|fft|fir|iir|filter|convolution|sample|nyquist|aliasing|"
        r"frequency|spectrum|fourier|z.transform|laplace|transfer.function|"
        r"digital.signal|analog.signal|quantization|decimation|interpolation|"
        r"window|hamming|hanning|blackman|kaiser|butterworth|chebyshev|"
        r"bessel|elliptic|passband|stopband|cutoff|roll.off|attenuation|"
        r"modulation|demodulation|codec|audio|sampling|bitrate|SNR|"
        r"signal.processing|discrete|continuous|impulse.response|"
        r"pole|zero|magnitude|phase|bode|resonance|oscillator)\b"
    ),
    "iot": re.compile(
        r"(?i)\b(iot|mqtt|coap|zigbee|bluetooth|ble|wifi|lora|lorawan|"
        r"sensor|actuator|gateway|edge|cloud|firmware|ota|microcontroller|"
        r"esp32|esp8266|arduino|raspberry.pi|stm32|nrf52|protocol|"
        r"i2c|spi|uart|gpio|adc|dac|pwm|interrupt|timer|watchdog|"
        r"low.power|sleep|deep.sleep|battery|energy.harvesting|"
        r"mesh|network|node|hub|telemetry|dashboard|influxdb|grafana|"
        r"home.assistant|zigbee2mqtt|tasmota|esphome|platformio)\b"
    ),
    "platformio": re.compile(
        r"(?i)\b(platformio|pio|arduino|esp32|esp8266|stm32|avr|arm|"
        r"framework|library|board|upload|serial|monitor|debug|"
        r"build|compile|flash|firmware|bootloader|linker|"
        r"cmake|makefile|toolchain|gcc|gdb|openocd|jtag|swd|"
        r"i2c|spi|uart|gpio|adc|dac|pwm|interrupt|timer|"
        r"freertos|rtos|task|mutex|semaphore|queue|"
        r"platformio\.ini|lib_deps|board_build|upload_speed|"
        r"monitor_speed|env|src|include|test)\b"
    ),
    "semiconductor": re.compile(
        r"(?i)\b(semiconductor|wafer|fabrication|lithography|etching|"
        r"doping|diffusion|ion.implant|cmos|nmos|pmos|finfet|"
        r"transistor|diode|mosfet|bjt|gate|drain|source|"
        r"threshold|oxide|silicon|gallium|arsenide|"
        r"process|node|nm|foundry|tsmc|samsung|intel|"
        r"yield|defect|clean.room|photoresist|mask)\b"
    ),
}


def entry_hash(entry):
    """Hash based on the human message content (the question)."""
    convs = entry.get("conversations", entry.get("messages", []))
    for msg in convs:
        role = msg.get("from", msg.get("role", ""))
        if role in ("human", "user"):
            text = msg.get("value", msg.get("content", ""))
            return hashlib.md5(text.strip().lower().encode()).hexdigest()
    # Fallback: hash entire entry
    return hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def get_answer_text(entry):
    """Extract the assistant/gpt answer text."""
    convs = entry.get("conversations", entry.get("messages", []))
    for msg in convs:
        role = msg.get("from", msg.get("role", ""))
        if role in ("gpt", "assistant"):
            return msg.get("value", msg.get("content", ""))
    return ""


def load_jsonl(path):
    entries = []
    bad = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad > 0:
        print(f"  WARNING: {bad} malformed lines in {os.path.basename(path)}")
    return entries


def save_jsonl(entries, path):
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════
# STEP 1: Cross-dataset deduplication
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("STEP 1: Cross-dataset deduplication")
print("=" * 70)

global_hashes = set()       # hashes from higher-priority datasets
all_data = OrderedDict()    # name -> list of entries
original_counts = {}
dedup_counts = {}
dedup_removed = {}

for name, path in DATASETS.items():
    print(f"\n  Loading {name} ({os.path.basename(path)})...")
    entries = load_jsonl(path)
    original_counts[name] = len(entries)

    kept = []
    dups = 0
    local_hashes = set()

    for entry in entries:
        h = entry_hash(entry)
        if h in global_hashes or h in local_hashes:
            dups += 1
        else:
            local_hashes.add(h)
            kept.append(entry)

    # Add this dataset's hashes to global set for lower-priority datasets
    global_hashes.update(local_hashes)

    all_data[name] = kept
    dedup_counts[name] = len(kept)
    dedup_removed[name] = dups
    print(f"    {original_counts[name]:>6} -> {len(kept):>6}  (removed {dups} cross-dataset dupes)")

total_removed_dedup = sum(dedup_removed.values())
print(f"\n  TOTAL cross-dataset duplicates removed: {total_removed_dedup}")


# ═══════════════════════════════════════════════════════════
# STEP 2: Quality filter on Tier C datasets
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 2: Quality filtering (Tier C datasets)")
print("=" * 70)

TIER_C_FILTER = ["spice", "dsp", "iot", "platformio"]
TIER_C_REMOVE = ["semiconductor"]

quality_removed = {}

for name in TIER_C_FILTER:
    entries = all_data[name]
    domain = name
    term_regex = DOMAIN_TERMS.get(domain)

    before = len(entries)
    kept = []
    short_removed = 0
    noterm_removed = 0

    for entry in entries:
        answer = get_answer_text(entry)

        # Filter 1: answer length >= 200 chars
        if len(answer) < 200:
            short_removed += 1
            continue

        # Filter 2: must contain at least 1 domain-relevant technical term
        if term_regex and not term_regex.search(answer):
            noterm_removed += 1
            continue

        kept.append(entry)

    all_data[name] = kept
    removed_total = before - len(kept)
    quality_removed[name] = removed_total
    print(f"\n  {name}: {before} -> {len(kept)}")
    print(f"    short answers (<200 chars): {short_removed}")
    print(f"    no technical terms:         {noterm_removed}")

for name in TIER_C_REMOVE:
    before = len(all_data[name])
    all_data[name] = []
    quality_removed[name] = before
    print(f"\n  {name}: {before} -> 0  (REMOVED - score 3.0, not usable)")


# ═══════════════════════════════════════════════════════════
# STEP 3: Save final files and print report
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 3: Saving final datasets & report")
print("=" * 70)

total_original = 0
total_final = 0

print(f"\n  {'Dataset':<20} {'Original':>10} {'Post-Dedup':>12} {'Final':>10} {'Removed':>10}")
print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")

for name in DATASETS:
    entries = all_data[name]
    outpath = os.path.join(OUT, f"{name}_final.jsonl")

    if len(entries) > 0:
        save_jsonl(entries, outpath)
    else:
        # Write empty file for removed datasets
        with open(outpath, "w") as f:
            pass

    orig = original_counts[name]
    deduped = dedup_counts[name]
    final = len(entries)
    removed = orig - final
    total_original += orig
    total_final += final

    flag = ""
    if name in TIER_C_REMOVE:
        flag = " [REMOVED]"
    elif name in TIER_C_FILTER:
        flag = " [FILTERED]"

    print(f"  {name:<20} {orig:>10} {deduped:>12} {final:>10} {removed:>10}{flag}")

print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")
print(f"  {'TOTAL':<20} {total_original:>10} {'':>12} {total_final:>10} {total_original - total_final:>10}")

print(f"\n  Output directory: {OUT}/")
print(f"  Total entries removed: {total_original - total_final}")
print(f"  Reduction: {(total_original - total_final) / total_original * 100:.1f}%")

# List output files
print(f"\n  Final files:")
for name in DATASETS:
    outpath = os.path.join(OUT, f"{name}_final.jsonl")
    if os.path.exists(outpath):
        size = os.path.getsize(outpath)
        count = len(all_data[name])
        if size > 1024*1024:
            print(f"    {name}_final.jsonl  ({count} entries, {size/1024/1024:.1f} MB)")
        else:
            print(f"    {name}_final.jsonl  ({count} entries, {size/1024:.1f} KB)")

print("\nDone.")
