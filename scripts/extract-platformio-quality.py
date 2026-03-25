"""Extract high-quality PlatformIO/Arduino/ESP32/STM32 training data from production repos."""
import os
import json
import re
from pathlib import Path

SOURCES = "finetune/sources"
OUTPUT = "finetune/datasets/cleaned_final/platformio_final.jsonl"
MIN_LINES = 15
MAX_LINES = 500

def extract_ini_files(base_path):
    """Extract platformio.ini configs as Q&A."""
    results = []
    for ini in Path(base_path).rglob("platformio.ini"):
        content = ini.read_text(errors="ignore")
        if len(content) < 50:
            continue
        # Parse environments
        envs = re.findall(r'\[env:(\w+)\]', content)
        boards = re.findall(r'board\s*=\s*(.+)', content)
        frameworks = re.findall(r'framework\s*=\s*(.+)', content)

        desc = f"PlatformIO config with envs: {', '.join(envs[:5])}"
        if boards:
            desc += f", boards: {', '.join(set(b.strip() for b in boards[:3]))}"
        if frameworks:
            desc += f", frameworks: {', '.join(set(f.strip() for f in frameworks[:3]))}"

        results.append({
            "conversations": [
                {"from": "system", "value": "You are an expert PlatformIO developer. You write production-ready platformio.ini configurations."},
                {"from": "human", "value": f"Write a platformio.ini configuration for: {desc}"},
                {"from": "gpt", "value": f"```ini\n{content[:2000]}\n```"},
            ],
            "domain": "platformio",
            "source": str(ini.relative_to(base_path)),
        })
    return results

def extract_cpp_examples(base_path, project_name):
    """Extract C/C++ examples as Q&A pairs."""
    results = []
    for ext in ["*.cpp", "*.c", "*.ino", "*.h"]:
        for src in Path(base_path).rglob(ext):
            try:
                content = src.read_text(errors="ignore")
            except Exception:
                continue

            lines = content.split("\n")
            if len(lines) < MIN_LINES or len(lines) > MAX_LINES:
                continue

            # Skip auto-generated, test files, etc.
            if any(skip in str(src) for skip in ["test_", "CMake", "build/", ".pio/", "node_modules"]):
                continue

            # Extract purpose from comments or filename
            header_comments = []
            for line in lines[:20]:
                if line.strip().startswith("//") or line.strip().startswith("/*") or line.strip().startswith("*"):
                    header_comments.append(line.strip().lstrip("/*/ "))

            purpose = " ".join(header_comments[:3])[:200] if header_comments else ""
            filename = src.name
            rel_path = str(src.relative_to(base_path))

            # Detect what the code does
            features = []
            if re.search(r'WiFi\.|wifi_', content): features.append("WiFi")
            if re.search(r'BLE|ble_', content): features.append("BLE")
            if re.search(r'MQTT|mqtt', content, re.I): features.append("MQTT")
            if re.search(r'Serial\.|UART|uart', content): features.append("Serial/UART")
            if re.search(r'SPI\.|spi_', content): features.append("SPI")
            if re.search(r'Wire\.|I2C|i2c', content): features.append("I2C")
            if re.search(r'GPIO|gpio|pinMode|digitalWrite', content): features.append("GPIO")
            if re.search(r'ADC|adc|analogRead', content): features.append("ADC")
            if re.search(r'PWM|pwm|analogWrite|ledcWrite', content): features.append("PWM")
            if re.search(r'Timer|timer|millis|delay', content): features.append("Timer")
            if re.search(r'DMA|dma', content): features.append("DMA")
            if re.search(r'FreeRTOS|xTask|vTask|xQueue', content): features.append("FreeRTOS")
            if re.search(r'display|oled|lcd|tft|LVGL', content, re.I): features.append("Display")
            if re.search(r'sensor|temperature|humidity|accel', content, re.I): features.append("Sensor")
            if re.search(r'motor|stepper|servo|pwm', content, re.I): features.append("Motor")
            if re.search(r'OTA|ota|update', content, re.I): features.append("OTA")
            if re.search(r'sleep|deepsleep|light_sleep', content, re.I): features.append("Sleep")
            if re.search(r'CAN|can_', content): features.append("CAN")
            if re.search(r'Modbus|modbus', content): features.append("Modbus")
            if re.search(r'DMX|dmx', content, re.I): features.append("DMX")

            if not features:
                continue  # Skip generic files

            feat_str = ", ".join(features[:5])
            question = f"Write {filename} for {project_name} using {feat_str}"
            if purpose:
                question += f". Purpose: {purpose}"

            results.append({
                "conversations": [
                    {"from": "system", "value": "You are an expert embedded firmware developer. You write production-grade C/C++ code for microcontrollers with PlatformIO, Arduino, and ESP-IDF."},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": f"```cpp\n// {rel_path}\n{content[:3000]}\n```"},
                ],
                "domain": "platformio",
                "source": f"{project_name}/{rel_path}",
            })
    return results

def extract_yaml_configs(base_path, project_name):
    """Extract ESPHome YAML configs."""
    results = []
    for yml in Path(base_path).rglob("*.yaml"):
        try:
            content = yml.read_text(errors="ignore")
        except Exception:
            continue
        if len(content) < 100 or len(content) > 5000:
            continue
        if "esphome:" not in content and "platform:" not in content:
            continue

        results.append({
            "conversations": [
                {"from": "system", "value": "You are an expert ESPHome developer for home automation. You write clean YAML configurations for ESP32/ESP8266 devices."},
                {"from": "human", "value": f"Write an ESPHome YAML config for: {yml.stem}"},
                {"from": "gpt", "value": f"```yaml\n{content[:2500]}\n```"},
            ],
            "domain": "platformio",
            "source": f"{project_name}/{yml.relative_to(base_path)}",
        })
    return results


def main():
    all_results = []

    projects = [
        ("platformio-examples", "PlatformIO"),
        ("Tasmota", "Tasmota"),
        ("Marlin", "Marlin"),
        ("esphome", "ESPHome"),
        ("arduino-esp32", "Arduino-ESP32"),
        ("Arduino_Core_STM32", "STM32duino"),
    ]

    for dirname, name in projects:
        base = os.path.join(SOURCES, dirname)
        if not os.path.isdir(base):
            print(f"SKIP {name}: {base} not found")
            continue

        print(f"\n=== {name} ===")
        inis = extract_ini_files(base)
        cpps = extract_cpp_examples(base, name)
        yamls = extract_yaml_configs(base, name)
        total = len(inis) + len(cpps) + len(yamls)
        print(f"  INI: {len(inis)}, C/C++: {len(cpps)}, YAML: {len(yamls)}, Total: {total}")
        all_results.extend(inis)
        all_results.extend(cpps)
        all_results.extend(yamls)

    # Dedup
    seen = set()
    deduped = []
    for r in all_results:
        text = r["conversations"][-1]["value"][:300]
        import hashlib
        h = hashlib.md5(text.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            deduped.append(r)

    print(f"\n=== TOTAL ===")
    print(f"  Raw: {len(all_results)}")
    print(f"  After dedup: {len(deduped)}")

    # Write
    with open(OUTPUT, "w") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Output: {OUTPUT}")

if __name__ == "__main__":
    main()
