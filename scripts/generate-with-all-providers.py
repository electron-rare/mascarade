"""Generate datasets using ALL providers in parallel: Mistral agents + Claude + Codestral + OpenAI + Gemini."""

import json
import time
import os
import httpx
import random
import threading
from collections import defaultdict

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CODESTRAL_KEY = os.environ.get("CODESTRAL_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")

AGENT_IDS = {}
if os.path.exists("finetune/datasets/mistral_agent_ids.json"):
    AGENT_IDS = json.load(open("finetune/datasets/mistral_agent_ids.json"))

SCHEMATICS_FILE = "finetune/datasets/hf_imports/open_schematics.jsonl"
OUTPUT_KICAD = "finetune/datasets/kicad_chat_v3_multi.jsonl"
OUTPUT_EMBEDDED = "finetune/datasets/embedded_chat_v2_multi.jsonl"

stats = defaultdict(lambda: {"success": 0, "errors": 0})
lock = threading.Lock()


def call_mistral_agent(agent_id, prompt, timeout=60.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post("https://api.mistral.ai/v1/conversations", headers={
                "Authorization": f"Bearer {MISTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={"agent_id": agent_id, "inputs": prompt, "stream": False})
            r.raise_for_status()
            return r.json().get("outputs", [{}])[0].get("content", "")
    except Exception:
        return None


def call_anthropic(system, prompt, timeout=60.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post("https://api.anthropic.com/v1/messages", headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 700,
                "temperature": 0.3,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            })
            r.raise_for_status()
            return r.json()["content"][0]["text"]
    except Exception:
        return None


def call_codestral(system, prompt, timeout=30.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post("https://codestral.mistral.ai/v1/chat/completions", headers={
                "Authorization": f"Bearer {CODESTRAL_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "codestral-latest",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            })
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def call_openai(system, prompt, timeout=30.0):
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post("https://api.openai.com/v1/chat/completions", headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            }, json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 700,
            })
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def call_gemini(prompt, timeout=30.0):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_KEY}"
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
            })
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


# Build provider list
PROVIDERS = []
if AGENT_IDS.get("mascarade-kicad-teacher"):
    PROVIDERS.append(("mistral-kicad-agent", lambda s, p: call_mistral_agent(AGENT_IDS["mascarade-kicad-teacher"], p)))
if AGENT_IDS.get("mascarade-embedded-teacher"):
    PROVIDERS.append(("mistral-embedded-agent", lambda s, p: call_mistral_agent(AGENT_IDS["mascarade-embedded-teacher"], p)))
if AGENT_IDS.get("mascarade-analog-teacher"):
    PROVIDERS.append(("mistral-analog-agent", lambda s, p: call_mistral_agent(AGENT_IDS["mascarade-analog-teacher"], p)))
if ANTHROPIC_KEY and len(ANTHROPIC_KEY) > 20:
    PROVIDERS.append(("claude-sonnet", call_anthropic))
if CODESTRAL_KEY and len(CODESTRAL_KEY) > 10:
    PROVIDERS.append(("codestral", call_codestral))
if OPENAI_KEY and len(OPENAI_KEY) > 20:
    PROVIDERS.append(("openai-4o-mini", call_openai))
if GOOGLE_KEY and len(GOOGLE_KEY) > 10:
    PROVIDERS.append(("gemini-flash", lambda s, p: call_gemini(f"{s}\n\n{p}")))


def generate_one(system, prompt, domain, source_ref=""):
    """Try providers in round-robin until one works."""
    provider_name, fn = random.choice(PROVIDERS)
    result = fn(system, prompt)
    if result and len(result) > 100:
        with lock:
            stats[provider_name]["success"] += 1
        return result, provider_name
    with lock:
        stats[provider_name]["errors"] += 1
    # Fallback to another
    for pname, pfn in PROVIDERS:
        if pname != provider_name:
            result = pfn(system, prompt)
            if result and len(result) > 100:
                with lock:
                    stats[pname]["success"] += 1
                return result, pname
            with lock:
                stats[pname]["errors"] += 1
    return None, "none"


def load_schematics(max_count=5000):
    schematics = []
    if not os.path.exists(SCHEMATICS_FILE):
        return schematics
    with open(SCHEMATICS_FILE) as f:
        for line in f:
            try:
                r = json.loads(line.strip())
                desc = r.get("description", "")
                comps = r.get("components_used") or []
                name = r.get("name", "")
                if desc and len(desc) > 50 and len(comps) >= 3 and name:
                    schematics.append({
                        "name": name,
                        "description": desc[:500],
                        "components": ", ".join(comps[:15]),
                    })
            except json.JSONDecodeError:
                continue
            if len(schematics) >= max_count:
                break
    return schematics


KICAD_TEMPLATES = [
    "Based on this KiCad schematic '{name}': {description}\nComponents: {components}\n\nExplain design choices and suggest improvements.",
    "Review this KiCad project '{name}' for DRC issues before JLCPCB manufacturing.\nComponents: {components}\nDescription: {description}",
    "A KiCad project '{name}' uses: {components}\n\nWhat is each component's purpose? Any missing components?",
    "Design a PCB layout strategy for '{name}': {description}\nComponents: {components}\n\nPlacement priorities, routing, and stackup recommendations.",
    "Write the BOM with manufacturer part numbers for '{name}' using: {components}",
    "What test points and measurements should I add for bring-up of '{name}'?\nComponents: {components}",
    "How would I modify '{name}' ({description}) for lower power consumption?\nCurrent components: {components}",
    "Analyze the power distribution in '{name}': {description}\nComponents: {components}\n\nDecoupling strategy and power consumption estimate.",
]

EMBEDDED_TEMPLATES = [
    "Write a complete PlatformIO project for {board} with {peripheral}: platformio.ini + main.cpp with error handling.",
    "Configure STM32 {stm32} {peripheral} with DMA using HAL. Show complete initialization code.",
    "ESP-IDF project for {chip}: {feature} with proper error handling and FreeRTOS tasks.",
    "Implement {protocol} communication on {mcu} with interrupt-driven buffering. Full working code.",
    "Design a battery-powered sensor node with {mcu}: deep sleep, wake on {wakeup}, read {sensor}, send via {radio}.",
    "Write a FreeRTOS application on {mcu} with 3 tasks: sensor read, display update, and WiFi transmit. Show task creation and IPC.",
    "Configure {mcu} for {application}: clock tree, peripherals, and power management. Complete register-level setup.",
    "Debug guide: {mcu} {problem}. Step-by-step diagnosis with SWD, logic analyzer, and oscilloscope.",
]

EMBEDDED_VARS = {
    "board": ["esp32dev", "esp32-s3-devkitc-1", "nucleo_f446re", "nucleo_h743zi", "pico", "teensy41", "adafruit_feather_nrf52840"],
    "peripheral": ["UART DMA", "SPI with CS", "I2C multi-device", "ADC continuous", "Timer PWM", "CAN bus", "USB CDC"],
    "stm32": ["STM32F446RE", "STM32H743ZI", "STM32L476RG", "STM32G431KB"],
    "chip": ["ESP32-S3", "ESP32-C3", "ESP32-C6"],
    "feature": ["WiFi station + MQTT + TLS", "BLE GATT server", "OTA update with rollback", "deep sleep + ULP"],
    "protocol": ["Modbus RTU", "CAN 2.0B", "RS-485", "MIDI", "DMX512", "1-Wire"],
    "mcu": ["STM32F446", "ESP32", "nRF52840", "RP2040", "ATtiny1614"],
    "wakeup": ["RTC alarm", "GPIO interrupt", "timer", "touch pad"],
    "sensor": ["BME280", "MPU6050", "ADS1115", "VL53L1X"],
    "radio": ["LoRa SX1262", "BLE", "WiFi MQTT", "ESP-NOW"],
    "application": ["motor controller", "data logger", "sensor node", "audio processor"],
    "problem": ["HardFault on SPI DMA transfer", "I2C hangs after NAK", "ADC reading noisy", "timer interrupt not firing"],
}


def fill_vars(template, vars_dict):
    result = template
    for key, values in vars_dict.items():
        ph = "{" + key + "}"
        while ph in result:
            result = result.replace(ph, random.choice(values), 1)
    return result


def main():
    print("=== Multi-Provider Dataset Generator ===")
    print(f"Providers: {[p[0] for p in PROVIDERS]}")

    schematics = load_schematics(5000)
    print(f"Loaded {len(schematics)} schematics\n")

    # Generate KiCad dataset
    print("=== KICAD DATASET (grounded) ===")
    kicad_count = 0
    kicad_target = 2000
    os.makedirs(os.path.dirname(OUTPUT_KICAD), exist_ok=True)

    with open(OUTPUT_KICAD, "w") as f:
        for i in range(kicad_target):
            sch = random.choice(schematics)
            template = random.choice(KICAD_TEMPLATES)
            question = template.format(**sch)
            system = "You are an expert KiCad PCB designer. Base answers on the schematic data provided. Never invent specs — say 'check the datasheet' if unsure."

            answer, provider = generate_one(system, question, "kicad", sch["name"])
            if answer:
                record = {
                    "conversations": [
                        {"from": "system", "value": system},
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": answer},
                    ],
                    "domain": "kicad",
                    "source": f"grounded-{provider}",
                    "reference_project": sch["name"],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                kicad_count += 1

            if (i + 1) % 100 == 0:
                print(f"  KiCad [{i+1}/{kicad_target}] generated={kicad_count}")
                print(f"  Stats: {dict(stats)}")
            time.sleep(0.3)

    print(f"  KiCad DONE: {kicad_count} examples -> {OUTPUT_KICAD}\n")

    # Generate Embedded dataset
    print("=== EMBEDDED DATASET ===")
    emb_count = 0
    emb_target = 2000

    with open(OUTPUT_EMBEDDED, "w") as f:
        for i in range(emb_target):
            template = random.choice(EMBEDDED_TEMPLATES)
            question = fill_vars(template, EMBEDDED_VARS)
            system = "You are an expert embedded systems engineer. Write compilable code with real API functions. Include error handling."

            answer, provider = generate_one(system, question, "embedded")
            if answer:
                record = {
                    "conversations": [
                        {"from": "system", "value": system},
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": answer},
                    ],
                    "domain": "embedded",
                    "source": f"multi-provider-{provider}",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                emb_count += 1

            if (i + 1) % 100 == 0:
                print(f"  Embedded [{i+1}/{emb_target}] generated={emb_count}")
                print(f"  Stats: {dict(stats)}")
            time.sleep(0.3)

    print(f"  Embedded DONE: {emb_count} examples -> {OUTPUT_EMBEDDED}\n")

    # Final stats
    print("=== FINAL STATS ===")
    print(f"KiCad: {kicad_count}/{kicad_target}")
    print(f"Embedded: {emb_count}/{emb_target}")
    print(f"Provider stats: {json.dumps(dict(stats), indent=2)}")


if __name__ == "__main__":
    main()
