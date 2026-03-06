#!/usr/bin/env python3
"""Build fine-tuning dataset for IoT/embedded domain.

Covers: MQTT, ESP-IDF, FreeRTOS, Home Assistant, PlatformIO, domotique.

Usage:
  python build_iot_dataset.py                    # Seeds only (~5 examples)
  python build_iot_dataset.py --with-hf          # Seeds + HuggingFace datasets
  python build_iot_dataset.py --max-samples 2000 # Limit HF samples per source
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert IoT and embedded systems engineer specializing in "
    "MQTT protocols, ESP32/ESP8266 with ESP-IDF, FreeRTOS, Home Assistant "
    "integration, PlatformIO, and smart home automation. You provide "
    "production-ready code with proper error handling, secure connections "
    "(TLS/mTLS), and energy-efficient designs for battery-powered devices."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write ESP-IDF code for an MQTT client that publishes sensor data to a broker with TLS and auto-reconnection."},
            {"from": "gpt", "value": """ESP-IDF MQTT client with TLS and auto-reconnect:

```c
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_event.h"
#include "mqtt_client.h"
#include "esp_tls.h"

static const char *TAG = "MQTT";
static esp_mqtt_client_handle_t client = NULL;
static bool mqtt_connected = false;

// Embedded CA certificate (PEM format)
extern const uint8_t mqtt_ca_pem_start[] asm("_binary_mqtt_ca_pem_start");
extern const uint8_t mqtt_ca_pem_end[]   asm("_binary_mqtt_ca_pem_end");

static void mqtt_event_handler(void *arg, esp_event_base_t base,
                                int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = event_data;

    switch (event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Connected to broker");
        mqtt_connected = true;
        // Subscribe to command topics
        esp_mqtt_client_subscribe(client, "home/device1/cmd", 1);
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Disconnected — auto-reconnect enabled");
        mqtt_connected = false;
        break;

    case MQTT_EVENT_DATA:
        ESP_LOGI(TAG, "Received: topic=%.*s data=%.*s",
                 event->topic_len, event->topic,
                 event->data_len, event->data);
        // Handle commands here
        break;

    case MQTT_EVENT_ERROR:
        if (event->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
            ESP_LOGE(TAG, "TLS error: 0x%x", event->error_handle->esp_tls_last_esp_err);
        }
        break;

    default:
        break;
    }
}

void mqtt_init(void) {
    esp_mqtt_client_config_t cfg = {
        .broker = {
            .address.uri = "mqtts://mqtt.example.com:8883",
            .verification.certificate = (const char *)mqtt_ca_pem_start,
        },
        .credentials = {
            .username = "device1",
            .authentication.password = "secret",
            .client_id = "esp32-device1",
        },
        .session = {
            .keepalive = 30,
            .last_will = {
                .topic = "home/device1/status",
                .msg = "offline",
                .qos = 1,
                .retain = true,
            },
        },
        .network = {
            .reconnect_timeout_ms = 5000,
        },
    };

    client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(client);
}

void sensor_publish_task(void *pvParameters) {
    char payload[128];
    float temperature, humidity;

    for (;;) {
        if (mqtt_connected) {
            // Read sensors (replace with actual sensor code)
            temperature = read_temperature();
            humidity = read_humidity();

            snprintf(payload, sizeof(payload),
                     "{\"temp\":%.1f,\"hum\":%.1f,\"rssi\":%d}",
                     temperature, humidity, esp_wifi_get_rssi());

            int msg_id = esp_mqtt_client_publish(
                client, "home/device1/sensor",
                payload, 0, 1, 0  // QoS 1, no retain
            );
            ESP_LOGI(TAG, "Published msg_id=%d: %s", msg_id, payload);
        }
        vTaskDelay(pdMS_TO_TICKS(30000));  // Every 30 seconds
    }
}
```

Key design choices:
- **QoS 1** for sensor data: guaranteed delivery, no duplicates concern
- **Last Will**: broker publishes "offline" if device disconnects unexpectedly
- **TLS**: server certificate verification prevents MITM attacks
- **Keepalive 30s**: detects broken connections within ~45s (1.5× keepalive)
- **Auto-reconnect**: ESP-IDF MQTT client handles this natively with backoff"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Create a Home Assistant YAML configuration for a custom ESP32 sensor with MQTT auto-discovery."},
            {"from": "gpt", "value": """Home Assistant MQTT auto-discovery for ESP32 sensor:

**ESP32 side** — publish discovery config on connect:

```c
// MQTT discovery topic format:
// homeassistant/<component>/<node_id>/<object_id>/config

void publish_ha_discovery(void) {
    // Temperature sensor
    const char *temp_config =
        "{"
        "\"name\":\"Living Room Temperature\","
        "\"unique_id\":\"esp32_lr_temp\","
        "\"state_topic\":\"home/livingroom/sensor\","
        "\"value_template\":\"{{ value_json.temp }}\","
        "\"unit_of_measurement\":\"°C\","
        "\"device_class\":\"temperature\","
        "\"state_class\":\"measurement\","
        "\"device\":{"
            "\"identifiers\":[\"esp32_livingroom\"],"
            "\"name\":\"ESP32 Living Room\","
            "\"model\":\"ESP32-WROOM-32\","
            "\"manufacturer\":\"Espressif\","
            "\"sw_version\":\"1.0.0\""
        "}"
        "}";

    esp_mqtt_client_publish(client,
        "homeassistant/sensor/esp32_lr/temperature/config",
        temp_config, 0, 1, 1);  // QoS 1, retain=true

    // Humidity sensor
    const char *hum_config =
        "{"
        "\"name\":\"Living Room Humidity\","
        "\"unique_id\":\"esp32_lr_hum\","
        "\"state_topic\":\"home/livingroom/sensor\","
        "\"value_template\":\"{{ value_json.hum }}\","
        "\"unit_of_measurement\":\"%\","
        "\"device_class\":\"humidity\","
        "\"state_class\":\"measurement\","
        "\"device\":{"
            "\"identifiers\":[\"esp32_livingroom\"],"
            "\"name\":\"ESP32 Living Room\""
        "}"
        "}";

    esp_mqtt_client_publish(client,
        "homeassistant/sensor/esp32_lr/humidity/config",
        hum_config, 0, 1, 1);

    // Binary sensor (motion)
    const char *motion_config =
        "{"
        "\"name\":\"Living Room Motion\","
        "\"unique_id\":\"esp32_lr_motion\","
        "\"state_topic\":\"home/livingroom/motion\","
        "\"device_class\":\"motion\","
        "\"payload_on\":\"ON\","
        "\"payload_off\":\"OFF\","
        "\"device\":{"
            "\"identifiers\":[\"esp32_livingroom\"],"
            "\"name\":\"ESP32 Living Room\""
        "}"
        "}";

    esp_mqtt_client_publish(client,
        "homeassistant/binary_sensor/esp32_lr/motion/config",
        motion_config, 0, 1, 1);
}
```

**Home Assistant side** — only needs MQTT integration enabled:

```yaml
# configuration.yaml — minimal config needed
mqtt:
  broker: 192.168.1.100
  port: 1883
  username: homeassistant
  password: !secret mqtt_password
  discovery: true  # This is the key — auto-discovers ESP32 entities
```

No manual sensor configuration needed in HA — the discovery messages handle everything. The `device` block groups all sensors under one device in the HA UI.

To remove a discovered entity, publish empty payload to its config topic:
```c
esp_mqtt_client_publish(client,
    "homeassistant/sensor/esp32_lr/temperature/config",
    "", 0, 1, 1);  // Empty payload = remove
```"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a FreeRTOS application with ESP-IDF that manages WiFi reconnection, MQTT, and deep sleep for a battery-powered sensor."},
            {"from": "gpt", "value": """Battery-optimized ESP32 sensor with WiFi, MQTT, and deep sleep:

```c
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "mqtt_client.h"
#include "driver/adc.h"

#define WIFI_CONNECTED_BIT BIT0
#define MQTT_PUBLISHED_BIT BIT1
#define SLEEP_INTERVAL_US  (300 * 1000000ULL)  // 5 minutes
#define WIFI_TIMEOUT_MS    10000
#define MQTT_TIMEOUT_MS    5000

static const char *TAG = "SENSOR";
static EventGroupHandle_t event_group;
static esp_mqtt_client_handle_t mqtt_client;
RTC_DATA_ATTR static int boot_count = 0;  // Survives deep sleep

static void wifi_event_handler(void *arg, esp_event_base_t base,
                                int32_t id, void *data) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(event_group, WIFI_CONNECTED_BIT);
    }
}

static void mqtt_event_handler(void *arg, esp_event_base_t base,
                                int32_t id, void *data) {
    if (id == MQTT_EVENT_CONNECTED) {
        // Publish immediately
        esp_mqtt_event_handle_t event = data;
        (void)event;

        float temp = read_temperature();
        float batt = read_battery_voltage();

        char payload[96];
        snprintf(payload, sizeof(payload),
                 "{\"temp\":%.1f,\"batt\":%.2f,\"boot\":%d,\"rssi\":%d}",
                 temp, batt, boot_count, get_wifi_rssi());

        esp_mqtt_client_publish(mqtt_client,
            "home/outdoor/sensor", payload, 0, 1, 0);

        ESP_LOGI(TAG, "Published: %s", payload);
        xEventGroupSetBits(event_group, MQTT_PUBLISHED_BIT);
    }
}

static float read_battery_voltage(void) {
    // ADC1_CH0 (GPIO36) with voltage divider 100k/100k
    int raw = adc1_get_raw(ADC1_CHANNEL_0);
    return (raw / 4095.0f) * 3.3f * 2.0f;  // ×2 for divider
}

static void enter_deep_sleep(void) {
    ESP_LOGI(TAG, "Entering deep sleep for %llu seconds", SLEEP_INTERVAL_US / 1000000);

    // Disconnect cleanly
    esp_mqtt_client_stop(mqtt_client);
    esp_wifi_stop();

    // Configure wakeup source
    esp_sleep_enable_timer_wakeup(SLEEP_INTERVAL_US);

    // Optional: GPIO wakeup (e.g., PIR sensor on GPIO33)
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_33, 1);  // Wake on HIGH

    esp_deep_sleep_start();
}

void app_main(void) {
    boot_count++;
    ESP_LOGI(TAG, "Boot #%d, wakeup cause: %d", boot_count, esp_sleep_get_wakeup_cause());

    event_group = xEventGroupCreate();

    // Init WiFi (fast reconnect using stored credentials in NVS)
    wifi_init_sta();

    // Wait for WiFi connection
    EventBits_t bits = xEventGroupWaitBits(event_group,
        WIFI_CONNECTED_BIT, pdFALSE, pdFALSE,
        pdMS_TO_TICKS(WIFI_TIMEOUT_MS));

    if (!(bits & WIFI_CONNECTED_BIT)) {
        ESP_LOGW(TAG, "WiFi timeout — sleeping");
        enter_deep_sleep();
        return;
    }

    // Init and start MQTT
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = "mqtt://192.168.1.100:1883",
        .credentials.client_id = "esp32-outdoor",
    };
    mqtt_client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID,
                                    mqtt_event_handler, NULL);
    esp_mqtt_client_start(mqtt_client);

    // Wait for publish confirmation
    bits = xEventGroupWaitBits(event_group,
        MQTT_PUBLISHED_BIT, pdFALSE, pdFALSE,
        pdMS_TO_TICKS(MQTT_TIMEOUT_MS));

    if (!(bits & MQTT_PUBLISHED_BIT)) {
        ESP_LOGW(TAG, "MQTT timeout — sleeping anyway");
    }

    // Mission complete — sleep
    vTaskDelay(pdMS_TO_TICKS(100));  // Let MQTT finish sending
    enter_deep_sleep();
}
```

Power budget:
| Phase | Duration | Current | Energy |
|-------|----------|---------|--------|
| Deep sleep | 300s | 10µA | 3mJ |
| Boot + WiFi | ~2s | 160mA | 1056mJ |
| MQTT publish | ~0.5s | 120mA | 198mJ |
| **Total per cycle** | **302.5s** | | **1257mJ** |

With 2× 18650 (6600mAh @ 3.7V = 24.4Wh):
- Cycles: 24.4Wh / 1.257Wh×1000 ≈ 19,400 cycles
- Battery life: 19,400 × 302.5s ≈ 68 days"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "Write a PlatformIO project configuration for an ESP32 with MQTT, DHT22, and OTA updates."},
            {"from": "gpt", "value": """PlatformIO configuration for ESP32 sensor node:

```ini
; platformio.ini
[env:esp32-sensor]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
upload_speed = 921600

; OTA upload (after first flash via USB)
upload_protocol = espota
upload_port = 192.168.1.50
upload_flags =
    --port=3232
    --auth=ota_password_here

; Libraries
lib_deps =
    knolleary/PubSubClient@^2.8      ; MQTT
    adafruit/DHT sensor library@^1.4  ; DHT22
    adafruit/Adafruit Unified Sensor  ; Required by DHT
    ayushsharma82/ElegantOTA@^3.1     ; Web-based OTA

; Build flags
build_flags =
    -DMQTT_BROKER=\"192.168.1.100\"
    -DMQTT_PORT=1883
    -DDEVICE_NAME=\"esp32-salon\"
    -DOTA_PASSWORD=\"ota_password_here\"
    -DSENSOR_INTERVAL=30000
```

```cpp
// src/main.cpp
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ElegantOTA.h>
#include <WebServer.h>

#define DHT_PIN 4
#define DHT_TYPE DHT22

WiFiClient espClient;
PubSubClient mqtt(espClient);
DHT dht(DHT_PIN, DHT_TYPE);
WebServer server(80);

unsigned long lastPublish = 0;

void mqtt_callback(char *topic, byte *payload, unsigned int length) {
    String msg;
    for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
    Serial.printf("MQTT [%s]: %s\\n", topic, msg.c_str());
}

void mqtt_reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(DEVICE_NAME, "home/" DEVICE_NAME "/status", 1, true, "offline")) {
            mqtt.publish("home/" DEVICE_NAME "/status", "online", true);
            mqtt.subscribe("home/" DEVICE_NAME "/cmd");
        } else {
            delay(5000);
        }
    }
}

void setup() {
    Serial.begin(115200);
    dht.begin();

    WiFi.begin("SSID", "password");
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.printf("IP: %s\\n", WiFi.localIP().toString().c_str());

    // MQTT
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(mqtt_callback);

    // OTA via web browser (http://device-ip/update)
    ElegantOTA.begin(&server, "admin", OTA_PASSWORD);
    server.begin();
}

void loop() {
    if (!mqtt.connected()) mqtt_reconnect();
    mqtt.loop();
    server.handleClient();
    ElegantOTA.loop();

    if (millis() - lastPublish > SENSOR_INTERVAL) {
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t) && !isnan(h)) {
            char payload[64];
            snprintf(payload, sizeof(payload),
                     "{\"temp\":%.1f,\"hum\":%.1f}", t, h);
            mqtt.publish("home/" DEVICE_NAME "/sensor", payload);
        }
        lastPublish = millis();
    }
}
```

Upload workflow:
1. First flash: `pio run -t upload` (USB)
2. Subsequent: `pio run -t upload` (OTA via WiFi)
3. Web OTA: browse to `http://device-ip/update`"""}
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": "How do I implement MQTT QoS levels properly and when to use each one?"},
            {"from": "gpt", "value": """MQTT QoS levels explained with implementation:

**QoS 0 — At most once (fire and forget)**
```
Publisher → PUBLISH → Broker → PUBLISH → Subscriber
```
- No acknowledgment, no retry
- Message may be lost if network fails
- **Use for**: telemetry with frequent updates where losing one reading is OK (temperature every 5s)

**QoS 1 — At least once (acknowledged)**
```
Publisher → PUBLISH → Broker → PUBACK → Publisher
                   ↓
            Broker → PUBLISH → Subscriber → PUBACK → Broker
```
- Broker ACKs receipt; publisher retries with DUP flag until ACK received
- Message guaranteed delivered but may arrive twice
- **Use for**: sensor data, status updates, commands where duplicates are harmless

**QoS 2 — Exactly once (4-step handshake)**
```
Publisher → PUBLISH → Broker → PUBREC → Publisher → PUBREL → Broker → PUBCOMP → Publisher
```
- Highest overhead (4 packets per message)
- Guaranteed exactly once delivery
- **Use for**: billing, critical commands (open/close valve), state changes

**Implementation example** (ESP-IDF):
```c
// QoS 0: high-frequency telemetry (every 1s)
esp_mqtt_client_publish(client, "sensor/accel",
    accel_json, 0, /*qos=*/0, /*retain=*/0);

// QoS 1: important sensor data (every 30s)
int msg_id = esp_mqtt_client_publish(client, "sensor/environment",
    env_json, 0, /*qos=*/1, /*retain=*/0);
// msg_id > 0 means queued; MQTT_EVENT_PUBLISHED fires on broker ACK

// QoS 2: critical command
esp_mqtt_client_publish(client, "actuator/valve/set",
    "{\"state\":\"close\"}", 0, /*qos=*/2, /*retain=*/0);
```

**Subscribing with QoS**:
```c
// QoS of subscription = maximum QoS broker will deliver
esp_mqtt_client_subscribe(client, "commands/#", 2);

// If publisher sends QoS 2 but subscriber subscribed QoS 1:
// → broker downgrades to QoS 1 for that subscriber
```

**Retain flag**: last message stored by broker, sent to new subscribers immediately:
```c
// Device status with retain — new HA instances see current state immediately
esp_mqtt_client_publish(client, "home/device/status",
    "online", 0, 1, /*retain=*/1);
```

**Performance impact**:
| QoS | Packets/msg | Latency | Bandwidth | Battery |
|-----|-------------|---------|-----------|---------|
| 0 | 1 | Lowest | Lowest | Best |
| 1 | 2 | Medium | Medium | Good |
| 2 | 4 | Highest | Highest | Worst |

Rule of thumb: use QoS 0 for >1Hz data, QoS 1 for everything else, QoS 2 only when you absolutely cannot have duplicates."""}
        ]
    },
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert IoT datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. ESP-IDF code examples (13.7k rows)
    print("  Downloading gouthamsk/esp_idf_code...")
    try:
        ds = load_dataset("gouthamsk/esp_idf_code", split="train", streaming=True)
        count = 0
        for row in ds:
            # Adapt columns based on dataset structure
            code = row.get("code", "") or row.get("content", "") or row.get("text", "")
            title = row.get("title", "") or row.get("name", "") or row.get("file_name", "")
            if not code or len(code) < 80:
                continue
            question = f"Write ESP-IDF code for: {title}" if title else "Write this ESP-IDF C code and explain its purpose."
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": f"```c\n{code.strip()}\n```"},
                ]
            })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} ESP-IDF code examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. Home Assistant requests (35.8k rows)
    # Columns: conversations (already ShareGPT format: list of {from, value})
    print("  Downloading acon96/Home-Assistant-Requests...")
    try:
        ds = load_dataset("acon96/Home-Assistant-Requests", split="train", streaming=True)
        count = 0
        for row in ds:
            convos = row.get("conversations", [])
            if not convos or len(convos) < 2:
                continue
            # Already in ShareGPT format, just add system prompt if missing
            has_system = any(c.get("from") == "system" for c in convos)
            if has_system:
                samples.append({"conversations": convos})
            else:
                samples.append({
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                    ] + convos
                })
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Home Assistant examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. Arduino docs (14.3k rows)
    print("  Downloading gavmac00/arduino-docs...")
    try:
        ds = load_dataset("gavmac00/arduino-docs", split="train", streaming=True)
        count = 0
        for row in ds:
            text = row.get("text", "") or row.get("content", "")
            title = row.get("title", "") or row.get("name", "")
            if not text or len(text) < 100:
                continue
            question = f"Explain the Arduino concept: {title}" if title else "Explain this Arduino documentation."
            samples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": question},
                    {"from": "gpt", "value": text.strip()},
                ]
            })
            count += 1
            if count >= max_samples // 2:  # Less priority than ESP-IDF
                break
        print(f"    Got {count} Arduino doc examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 4. Arduino StackExchange Q&A
    # Columns: Id, Tags, Answer, Body, Title, CreationDate (same as electronics SE)
    print("  Downloading bshada/arduino.stackexchange.com...")
    try:
        ds = load_dataset("bshada/arduino.stackexchange.com", split="train", streaming=True)
        count = 0
        for row in ds:
            title = row.get("Title", "")
            body = row.get("Body", "")
            answer = row.get("Answer", "")
            if not title or not answer or len(answer) < 100:
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
            if count >= max_samples // 2:
                break
        print(f"    Got {count} Arduino SE examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(description="Build IoT/embedded fine-tuning dataset")
    parser.add_argument("--with-hf", action="store_true", help="Include HuggingFace datasets")
    parser.add_argument("--max-samples", type=int, default=2000, help="Max HF samples per source")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "iot_chat.jsonl")

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
        print(f"\n  To enrich: python build_iot_dataset.py --with-hf --max-samples 2000")


if __name__ == "__main__":
    main()
