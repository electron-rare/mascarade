#!/usr/bin/env python3
"""Build fine-tuning dataset for PlatformIO / Arduino / ESP32 domain.

Covers: platformio.ini, ESP32/ESP8266 Arduino, library mgmt, OTA,
        sensors, actuators, WiFi, BLE, serial, debugging, unit tests.

Sources:
  - gavmac00/arduino-docs (14.3k)
  - gouthamsk/esp_idf_code (13.7k)
  - bshada/arduino.stackexchange.com
  - Hand-crafted seed examples for PlatformIO-specific workflows

Usage:
  python build_platformio_dataset.py                    # Seeds only
  python build_platformio_dataset.py --with-hf          # Seeds + HF
  python build_platformio_dataset.py --max-samples 2000
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert embedded developer specializing in PlatformIO, "
    "Arduino framework, and ESP32/ESP8266 development. You write clean, "
    "production-ready C++ code with proper error handling, efficient memory "
    "usage, and best practices for IoT devices. You know platformio.ini "
    "configuration, library management, OTA updates, unit testing, "
    "multi-environment builds, and debugging with PlatformIO."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a complete platformio.ini for an ESP32 project with WiFi, MQTT, DHT22 sensor, OTA updates, and separate debug/release environments.",
            },
            {
                "from": "gpt",
                "value": """Here's a production-ready `platformio.ini`:

```ini
; platformio.ini — ESP32 Sensor Node
[platformio]
default_envs = release

[common]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
    knolleary/PubSubClient@^2.8        ; MQTT client
    adafruit/DHT sensor library@^1.4   ; DHT22
    adafruit/Adafruit Unified Sensor   ; Required by DHT
    bblanchon/ArduinoJson@^7.0         ; JSON serialization
    ayushsharma82/ElegantOTA@^3.1      ; Web-based OTA
build_flags =
    -DMQTT_MAX_PACKET_SIZE=512
    -DCORE_DEBUG_LEVEL=0
    -Wall -Wextra

[env:release]
extends = common
build_type = release
board_build.partitions = min_spiffs.csv
upload_protocol = espota
upload_port = 192.168.1.50
upload_flags =
    --port=3232
    --auth=${sysenv.OTA_PASSWORD}
build_flags =
    ${common.build_flags}
    -DRELEASE=1
    -Os

[env:debug]
extends = common
build_type = debug
upload_speed = 921600
build_flags =
    ${common.build_flags}
    -DDEBUG=1
    -DCORE_DEBUG_LEVEL=4
    -Og -g
monitor_filters = esp32_exception_decoder
debug_tool = esp-prog
debug_init_break = tbreak setup

[env:test]
extends = common
platform = native
lib_deps =
    bblanchon/ArduinoJson@^7.0
build_flags =
    -DUNIT_TEST=1
    -std=c++17
test_framework = unity
```

Key design choices:
- **3 environments**: `release` (OTA deploy), `debug` (USB + JTAG), `test` (native unit tests)
- **`[common]` section**: shared config avoids duplication
- **`min_spiffs.csv`** partition: maximizes app space for OTA (two app partitions)
- **`esp32_exception_decoder`**: auto-decodes stack traces in monitor
- **`${sysenv.OTA_PASSWORD}`**: reads password from env var, not hardcoded
- **Native test env**: runs unit tests on host machine without hardware""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a PlatformIO ESP32 project with WiFi manager (captive portal for config), MQTT auto-reconnect, and deep sleep.",
            },
            {
                "from": "gpt",
                "value": """Complete ESP32 project with WiFiManager captive portal + MQTT + deep sleep:

**platformio.ini:**
```ini
[env:esp32-sensor]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
    tzapu/WiFiManager@^2.0
    knolleary/PubSubClient@^2.8
    bblanchon/ArduinoJson@^7.0
build_flags =
    -DMQTT_BROKER="192.168.1.100"
    -DSLEEP_SECONDS=300
```

**src/main.cpp:**
```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Config stored in RTC memory (survives deep sleep)
RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR char mqtt_server[40] = MQTT_BROKER;

WiFiClient espClient;
PubSubClient mqtt(espClient);
WiFiManager wm;

// Custom MQTT server parameter for WiFiManager
WiFiManagerParameter custom_mqtt("mqtt", "MQTT Server", mqtt_server, 40);

void setup_wifi() {
    wm.addParameter(&custom_mqtt);
    wm.setConfigPortalTimeout(120);  // 2 min timeout

    // Try auto-connect; if fails, start captive portal "ESP32-Setup"
    if (!wm.autoConnect("ESP32-Setup", "configure")) {
        Serial.println("Portal timeout — sleeping");
        esp_deep_sleep(SLEEP_SECONDS * 1000000ULL);
    }

    // Save custom params
    strncpy(mqtt_server, custom_mqtt.getValue(), sizeof(mqtt_server) - 1);
}

bool mqtt_connect() {
    mqtt.setServer(mqtt_server, 1883);

    for (int i = 0; i < 3; i++) {
        String clientId = "esp32-" + String(ESP.getEfuseMac(), HEX);
        if (mqtt.connect(clientId.c_str(),
                         "home/sensor/status", 1, true, "offline")) {
            mqtt.publish("home/sensor/status", "online", true);
            return true;
        }
        delay(1000);
    }
    return false;
}

void publish_sensor_data() {
    JsonDocument doc;
    doc["boot"] = bootCount;
    doc["temp"] = temperatureRead();  // Internal temp sensor
    doc["hall"] = hallRead();         // Built-in hall sensor
    doc["heap"] = ESP.getFreeHeap();
    doc["rssi"] = WiFi.RSSI();

    char payload[200];
    serializeJson(doc, payload);
    mqtt.publish("home/sensor/data", payload);
    Serial.printf("Published: %s\n", payload);
}

void enter_sleep() {
    mqtt.publish("home/sensor/status", "sleeping", true);
    mqtt.disconnect();
    WiFi.disconnect(true);
    delay(100);

    esp_sleep_enable_timer_wakeup(SLEEP_SECONDS * 1000000ULL);
    // Optional: wake on button press (GPIO0)
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, LOW);

    Serial.printf("Sleeping %d seconds...\n", SLEEP_SECONDS);
    esp_deep_sleep_start();
}

void setup() {
    Serial.begin(115200);
    bootCount++;
    Serial.printf("Boot #%d, reason: %d\n", bootCount,
                  esp_sleep_get_wakeup_cause());

    setup_wifi();

    if (mqtt_connect()) {
        publish_sensor_data();
    } else {
        Serial.println("MQTT failed");
    }

    enter_sleep();
}

void loop() {
    // Never reached — deep sleep resets to setup()
}
```

**How it works:**
1. First boot: no WiFi credentials → opens captive portal "ESP32-Setup" on 192.168.4.1
2. User connects, enters WiFi + MQTT server in browser
3. Credentials saved in NVS flash (survives deep sleep and power cycles)
4. Subsequent boots: auto-connects WiFi → MQTT publish → deep sleep 5 min
5. Hold GPIO0 during sleep → immediate wakeup

Power: ~10uA in deep sleep, ~150mA for ~3s active = months on 18650.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to write unit tests for an Arduino/PlatformIO project that can run on both native and embedded targets?",
            },
            {
                "from": "gpt",
                "value": """PlatformIO unit testing with Unity framework — cross-platform approach:

**platformio.ini:**
```ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
test_framework = unity
lib_deps = bblanchon/ArduinoJson@^7.0

[env:native]
platform = native
test_framework = unity
lib_deps = bblanchon/ArduinoJson@^7.0
build_flags = -std=c++17 -DUNIT_TEST
```

**Project structure:**
```
project/
├── lib/
│   └── SensorFilter/
│       ├── SensorFilter.h
│       └── SensorFilter.cpp
├── src/
│   └── main.cpp
├── test/
│   ├── test_native/          # Runs on PC (pio test -e native)
│   │   └── test_filter.cpp
│   └── test_embedded/        # Runs on ESP32 (pio test -e esp32)
│       └── test_hw.cpp
└── platformio.ini
```

**lib/SensorFilter/SensorFilter.h:**
```cpp
#pragma once
#include <cstdint>
#include <cstddef>

class SensorFilter {
public:
    explicit SensorFilter(size_t window_size);
    float addSample(float value);
    float getAverage() const;
    float getMin() const;
    float getMax() const;
    void reset();
    bool isFull() const;

private:
    float* buffer_;
    size_t size_;
    size_t count_;
    size_t index_;
    float sum_;
};
```

**lib/SensorFilter/SensorFilter.cpp:**
```cpp
#include "SensorFilter.h"
#include <cfloat>
#include <algorithm>

SensorFilter::SensorFilter(size_t window_size)
    : size_(window_size), count_(0), index_(0), sum_(0) {
    buffer_ = new float[size_]();
}

float SensorFilter::addSample(float value) {
    if (count_ >= size_) {
        sum_ -= buffer_[index_];
    } else {
        count_++;
    }
    buffer_[index_] = value;
    sum_ += value;
    index_ = (index_ + 1) % size_;
    return getAverage();
}

float SensorFilter::getAverage() const {
    return count_ > 0 ? sum_ / count_ : 0.0f;
}

float SensorFilter::getMin() const {
    float min_val = FLT_MAX;
    for (size_t i = 0; i < count_; i++) min_val = std::min(min_val, buffer_[i]);
    return min_val;
}

float SensorFilter::getMax() const {
    float max_val = -FLT_MAX;
    for (size_t i = 0; i < count_; i++) max_val = std::max(max_val, buffer_[i]);
    return max_val;
}

void SensorFilter::reset() { count_ = index_ = 0; sum_ = 0; }
bool SensorFilter::isFull() const { return count_ >= size_; }
```

**test/test_native/test_filter.cpp:**
```cpp
#include <unity.h>
#include "SensorFilter.h"

SensorFilter* filter;

void setUp() {
    filter = new SensorFilter(5);
}

void tearDown() {
    delete filter;
}

void test_empty_average() {
    TEST_ASSERT_EQUAL_FLOAT(0.0f, filter->getAverage());
}

void test_single_sample() {
    filter->addSample(42.0f);
    TEST_ASSERT_EQUAL_FLOAT(42.0f, filter->getAverage());
    TEST_ASSERT_FALSE(filter->isFull());
}

void test_full_window() {
    for (int i = 1; i <= 5; i++) filter->addSample(i * 10.0f);
    TEST_ASSERT_TRUE(filter->isFull());
    TEST_ASSERT_EQUAL_FLOAT(30.0f, filter->getAverage());  // (10+20+30+40+50)/5
    TEST_ASSERT_EQUAL_FLOAT(10.0f, filter->getMin());
    TEST_ASSERT_EQUAL_FLOAT(50.0f, filter->getMax());
}

void test_sliding_window() {
    for (int i = 1; i <= 5; i++) filter->addSample(i * 10.0f);
    filter->addSample(60.0f);  // Pushes out 10.0
    TEST_ASSERT_EQUAL_FLOAT(40.0f, filter->getAverage());  // (20+30+40+50+60)/5
}

void test_reset() {
    filter->addSample(100.0f);
    filter->reset();
    TEST_ASSERT_EQUAL_FLOAT(0.0f, filter->getAverage());
    TEST_ASSERT_FALSE(filter->isFull());
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_empty_average);
    RUN_TEST(test_single_sample);
    RUN_TEST(test_full_window);
    RUN_TEST(test_sliding_window);
    RUN_TEST(test_reset);
    return UNITY_END();
}
```

**Run tests:**
```bash
# On PC (instant, no hardware needed)
pio test -e native

# On ESP32 (uploads, runs, reads serial output)
pio test -e esp32

# Specific test folder only
pio test -e native --filter test_native
```

Key patterns:
- **Pure logic in `lib/`**: no Arduino.h dependency → testable on PC
- **HAL abstraction**: wrap `analogRead()` etc. behind interfaces for mocking
- **`test_native/` vs `test_embedded/`**: PlatformIO auto-selects by env
- **CI integration**: `pio test -e native` in GitHub Actions""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write PlatformIO code for an ESP32 BLE scanner that reports nearby devices via MQTT.",
            },
            {
                "from": "gpt",
                "value": """ESP32 BLE scanner with MQTT reporting:

**platformio.ini:**
```ini
[env:esp32-ble-scanner]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
    knolleary/PubSubClient@^2.8
    bblanchon/ArduinoJson@^7.0
build_flags =
    -DCONFIG_BT_NIMBLE_ENABLED=0
```

**src/main.cpp:**
```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

const char* WIFI_SSID = "your-ssid";
const char* WIFI_PASS = "your-pass";
const char* MQTT_SERVER = "192.168.1.100";
const char* TOPIC_DEVICES = "home/ble/devices";
const char* TOPIC_STATUS = "home/ble/scanner/status";

const int SCAN_DURATION = 10;  // seconds
const int SCAN_INTERVAL = 30;  // seconds between scans

WiFiClient espClient;
PubSubClient mqtt(espClient);
BLEScan* bleScan;

struct BLEResult {
    String address;
    String name;
    int rssi;
    int txPower;
    bool isPublic;
};

std::vector<BLEResult> scanResults;

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice device) override {
        BLEResult r;
        r.address = device.getAddress().toString().c_str();
        r.name = device.haveName() ? device.getName().c_str() : "";
        r.rssi = device.getRSSI();
        r.txPower = device.haveTXPower() ? device.getTXPower() : -127;
        r.isPublic = device.getAddressType() == BLE_ADDR_PUBLIC;
        scanResults.push_back(r);
    }
};

void wifi_connect() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int timeout = 20;
    while (WiFi.status() != WL_CONNECTED && timeout-- > 0) {
        delay(500);
    }
    if (WiFi.status() != WL_CONNECTED) {
        ESP.restart();
    }
}

void mqtt_connect() {
    mqtt.setServer(MQTT_SERVER, 1883);
    mqtt.setBufferSize(2048);  // Large buffer for JSON array
    for (int i = 0; i < 3 && !mqtt.connected(); i++) {
        mqtt.connect("esp32-ble-scanner",
                     TOPIC_STATUS, 1, true, "offline");
        delay(1000);
    }
    if (mqtt.connected()) {
        mqtt.publish(TOPIC_STATUS, "online", true);
    }
}

void publish_results() {
    JsonDocument doc;
    doc["scanner"] = WiFi.macAddress();
    doc["scan_time"] = SCAN_DURATION;
    doc["device_count"] = scanResults.size();

    JsonArray devices = doc["devices"].to<JsonArray>();
    for (const auto& r : scanResults) {
        JsonObject dev = devices.add<JsonObject>();
        dev["mac"] = r.address;
        if (r.name.length() > 0) dev["name"] = r.name;
        dev["rssi"] = r.rssi;
        if (r.txPower != -127) dev["tx_power"] = r.txPower;

        // Estimate distance from RSSI (rough, indoor)
        if (r.txPower != -127) {
            float ratio = (r.txPower - r.rssi) / 20.0f;
            dev["distance_m"] = round(pow(10, ratio) * 10) / 10.0;
        }
    }

    char buffer[2048];
    size_t len = serializeJson(doc, buffer);
    mqtt.publish(TOPIC_DEVICES, buffer, len);

    Serial.printf("Published %d devices (%d bytes)\n",
                  scanResults.size(), len);
}

void do_scan() {
    Serial.println("Starting BLE scan...");
    scanResults.clear();

    bleScan->setActiveScan(true);
    bleScan->setInterval(100);
    bleScan->setWindow(99);
    bleScan->start(SCAN_DURATION, false);
    bleScan->clearResults();

    Serial.printf("Found %d devices\n", scanResults.size());
}

void setup() {
    Serial.begin(115200);
    wifi_connect();
    mqtt_connect();

    BLEDevice::init("ESP32-Scanner");
    bleScan = BLEDevice::getScan();
    bleScan->setAdvertisedDeviceCallbacks(new ScanCallbacks());
}

void loop() {
    if (!mqtt.connected()) mqtt_connect();
    mqtt.loop();

    do_scan();
    publish_results();

    delay(SCAN_INTERVAL * 1000);
}
```

MQTT output example:
```json
{
  "scanner": "AA:BB:CC:DD:EE:FF",
  "scan_time": 10,
  "device_count": 5,
  "devices": [
    {"mac": "11:22:33:44:55:66", "name": "Mi Band 7", "rssi": -65, "tx_power": -7, "distance_m": 1.2},
    {"mac": "AA:BB:CC:DD:EE:FF", "rssi": -82}
  ]
}
```

Use in Home Assistant: subscribe to `home/ble/devices` for room-level presence detection.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to create a custom PlatformIO board definition for a custom ESP32-S3 PCB?",
            },
            {
                "from": "gpt",
                "value": """Custom board definition for an ESP32-S3 based PCB:

**Step 1: Create board JSON file**

Create `boards/myboard_s3.json` in your project root:

```json
{
  "build": {
    "arduino": {
      "ldscript": "esp32s3_out.ld",
      "partitions": "default_16MB.csv",
      "memory_type": "qio_opi"
    },
    "core": "esp32",
    "extra_flags": [
      "-DARDUINO_MYBOARD_S3",
      "-DBOARD_HAS_PSRAM"
    ],
    "f_cpu": "240000000L",
    "f_flash": "80000000L",
    "flash_mode": "qio",
    "hwids": [
      ["0x303A", "0x1001"]
    ],
    "mcu": "esp32s3",
    "variant": "esp32s3"
  },
  "connectivity": [
    "wifi",
    "bluetooth"
  ],
  "debug": {
    "default_tool": "esp-builtin",
    "onboard_tools": ["esp-builtin"],
    "openocd_target": "esp32s3.cfg"
  },
  "frameworks": [
    "arduino",
    "espidf"
  ],
  "name": "My Custom ESP32-S3 Board",
  "upload": {
    "flash_size": "16MB",
    "maximum_ram_size": 327680,
    "maximum_size": 16777216,
    "require_upload_port": true,
    "speed": 921600
  },
  "url": "https://example.com/myboard",
  "vendor": "MyCompany"
}
```

**Step 2: Custom partition table**

Create `partitions/custom_16MB.csv`:
```csv
# Name,   Type, SubType, Offset,   Size,     Flags
nvs,      data, nvs,     0x9000,   0x5000,
otadata,  data, ota,     0xe000,   0x2000,
app0,     app,  ota_0,   0x10000,  0x640000,
app1,     app,  ota_1,   0x650000, 0x640000,
spiffs,   data, spiffs,  0xC90000, 0x370000,
```

**Step 3: Custom pin mapping (optional)**

Create `variants/myboard_s3/pins_arduino.h`:
```cpp
#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>

// User LEDs
#define LED_BUILTIN   48  // WS2812 on GPIO48
#define RGB_BUILTIN   48

// I2C - Sensor bus
#define SDA           8
#define SCL           9

// SPI - SD Card
#define SS            10
#define MOSI          11
#define MISO          13
#define SCK           12

// UART - Debug
#define TX            43
#define RX            44

// ADC - Battery monitoring
#define BATTERY_ADC   1   // GPIO1, ADC1_CH0
#define BATTERY_EN    2   // Enable voltage divider

// Custom peripherals
#define IMU_INT       3   // IMU interrupt
#define SD_DETECT     4   // SD card detect
#define BUZZER        5   // PWM buzzer
#define BUTTON        0   // Boot button

// PSRAM
#define BOARD_HAS_PSRAM 1

// USB
static const uint8_t USB_DN = 19;
static const uint8_t USB_DP = 20;

#endif
```

**Step 4: platformio.ini**
```ini
[env:myboard]
platform = espressif32
board = myboard_s3
board_build.partitions = partitions/custom_16MB.csv
framework = arduino
monitor_speed = 115200

; Custom variant with pin definitions
board_build.variant = myboard_s3
board_build.variants_dir = variants
```

**Step 5: Using the board**
```bash
pio boards myboard    # Verify board is found
pio run               # Build
pio run -t upload     # Flash
```

PlatformIO searches for board definitions in:
1. `boards/` in project root (highest priority)
2. `~/.platformio/boards/` (user-global)
3. Platform package `boards/` (built-in)""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a PlatformIO ESP32 web server with REST API to control GPIOs and read ADC values.",
            },
            {
                "from": "gpt",
                "value": """ESP32 REST API server for GPIO control and ADC reading:

**platformio.ini:**
```ini
[env:esp32-api]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
    me-no-dev/ESP Async WebServer@^1.2.3
    me-no-dev/AsyncTCP@^1.1.1
    bblanchon/ArduinoJson@^7.0
build_flags = -DASYNCWEBSERVER_REGEX
```

**src/main.cpp:**
```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>

const char* SSID = "your-ssid";
const char* PASS = "your-pass";

AsyncWebServer server(80);

// Allowed GPIO pins for digital control
const uint8_t ALLOWED_PINS[] = {2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33};
const size_t NUM_PINS = sizeof(ALLOWED_PINS) / sizeof(ALLOWED_PINS[0]);

// ADC pins
const uint8_t ADC_PINS[] = {32, 33, 34, 35, 36, 39};
const size_t NUM_ADC = sizeof(ADC_PINS) / sizeof(ADC_PINS[0]);

bool is_allowed_pin(uint8_t pin) {
    for (size_t i = 0; i < NUM_PINS; i++) {
        if (ALLOWED_PINS[i] == pin) return true;
    }
    return false;
}

bool is_adc_pin(uint8_t pin) {
    for (size_t i = 0; i < NUM_ADC; i++) {
        if (ADC_PINS[i] == pin) return true;
    }
    return false;
}

void send_json(AsyncWebServerRequest* req, int code, JsonDocument& doc) {
    String response;
    serializeJson(doc, response);
    req->send(code, "application/json", response);
}

void send_error(AsyncWebServerRequest* req, int code, const char* msg) {
    JsonDocument doc;
    doc["error"] = msg;
    send_json(req, code, doc);
}

void setup_routes() {
    // GET /api/status — System info
    server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* req) {
        JsonDocument doc;
        doc["heap"] = ESP.getFreeHeap();
        doc["uptime_s"] = millis() / 1000;
        doc["cpu_mhz"] = ESP.getCpuFreqMHz();
        doc["mac"] = WiFi.macAddress();
        doc["ip"] = WiFi.localIP().toString();
        doc["rssi"] = WiFi.RSSI();
        send_json(req, 200, doc);
    });

    // GET /api/gpio/:pin — Read digital pin
    server.on("^\\/api\\/gpio\\/(\\d+)$", HTTP_GET,
        [](AsyncWebServerRequest* req) {
        uint8_t pin = req->pathArg(0).toInt();
        if (!is_allowed_pin(pin)) {
            return send_error(req, 400, "Pin not allowed");
        }
        JsonDocument doc;
        doc["pin"] = pin;
        doc["value"] = digitalRead(pin);
        send_json(req, 200, doc);
    });

    // POST /api/gpio/:pin — Set digital pin
    server.on("^\\/api\\/gpio\\/(\\d+)$", HTTP_POST,
        [](AsyncWebServerRequest* req) {
        uint8_t pin = req->pathArg(0).toInt();
        if (!is_allowed_pin(pin)) {
            return send_error(req, 400, "Pin not allowed");
        }
        String val = req->hasParam("value") ?
            req->getParam("value")->value() : "toggle";

        pinMode(pin, OUTPUT);
        int new_val;
        if (val == "toggle") {
            new_val = !digitalRead(pin);
        } else {
            new_val = val.toInt() ? HIGH : LOW;
        }
        digitalWrite(pin, new_val);

        JsonDocument doc;
        doc["pin"] = pin;
        doc["value"] = new_val;
        doc["action"] = "set";
        send_json(req, 200, doc);
    });

    // GET /api/adc/:pin — Read ADC
    server.on("^\\/api\\/adc\\/(\\d+)$", HTTP_GET,
        [](AsyncWebServerRequest* req) {
        uint8_t pin = req->pathArg(0).toInt();
        if (!is_adc_pin(pin)) {
            return send_error(req, 400, "Not an ADC pin");
        }
        int raw = analogRead(pin);
        float voltage = raw * 3.3f / 4095.0f;

        JsonDocument doc;
        doc["pin"] = pin;
        doc["raw"] = raw;
        doc["voltage"] = round(voltage * 1000) / 1000.0;
        send_json(req, 200, doc);
    });

    // GET /api/adc — Read all ADC pins
    server.on("/api/adc", HTTP_GET, [](AsyncWebServerRequest* req) {
        JsonDocument doc;
        JsonArray channels = doc["channels"].to<JsonArray>();
        for (size_t i = 0; i < NUM_ADC; i++) {
            JsonObject ch = channels.add<JsonObject>();
            int raw = analogRead(ADC_PINS[i]);
            ch["pin"] = ADC_PINS[i];
            ch["raw"] = raw;
            ch["voltage"] = round(raw * 3.3f / 4095.0f * 1000) / 1000.0;
        }
        send_json(req, 200, doc);
    });

    // POST /api/pwm/:pin?duty=128&freq=5000 — PWM output
    server.on("^\\/api\\/pwm\\/(\\d+)$", HTTP_POST,
        [](AsyncWebServerRequest* req) {
        uint8_t pin = req->pathArg(0).toInt();
        if (!is_allowed_pin(pin)) {
            return send_error(req, 400, "Pin not allowed");
        }
        int duty = req->hasParam("duty") ?
            req->getParam("duty")->value().toInt() : 128;
        int freq = req->hasParam("freq") ?
            req->getParam("freq")->value().toInt() : 5000;

        static uint8_t next_channel = 0;
        uint8_t ch = next_channel++ % 16;
        ledcSetup(ch, freq, 8);  // 8-bit resolution
        ledcAttachPin(pin, ch);
        ledcWrite(ch, duty);

        JsonDocument doc;
        doc["pin"] = pin;
        doc["duty"] = duty;
        doc["freq"] = freq;
        doc["channel"] = ch;
        send_json(req, 200, doc);
    });

    server.onNotFound([](AsyncWebServerRequest* req) {
        send_error(req, 404, "Not found");
    });
}

void setup() {
    Serial.begin(115200);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.printf("IP: %s\\n", WiFi.localIP().toString().c_str());

    setup_routes();
    server.begin();
}

void loop() {
    // AsyncWebServer handles requests in background
    delay(1000);
}
```

**API usage:**
```bash
curl http://192.168.1.50/api/status
curl http://192.168.1.50/api/gpio/2
curl -X POST 'http://192.168.1.50/api/gpio/2?value=1'
curl http://192.168.1.50/api/adc/34
curl -X POST 'http://192.168.1.50/api/pwm/5?duty=128&freq=1000'
```""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to set up PlatformIO CI/CD with GitHub Actions for automated testing and OTA deployment?",
            },
            {
                "from": "gpt",
                "value": """PlatformIO CI/CD pipeline with GitHub Actions:

**.github/workflows/firmware.yml:**
```yaml
name: Firmware CI/CD

on:
  push:
    branches: [main, develop]
    paths: ['firmware/**']
  pull_request:
    branches: [main]

env:
  PLATFORMIO_CORE_DIR: ~/.platformio

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Cache PlatformIO
        uses: actions/cache@v4
        with:
          path: ~/.platformio
          key: pio-${{ hashFiles('firmware/platformio.ini') }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install PlatformIO
        run: pip install platformio

      - name: Run native tests
        working-directory: firmware
        run: pio test -e native --verbose

      - name: Build all environments
        working-directory: firmware
        run: |
          pio run -e release
          pio run -e debug

      - name: Check firmware size
        working-directory: firmware
        run: |
          pio run -e release -t size
          # Fail if firmware exceeds 1.5MB (OTA partition limit)
          SIZE=$(stat -c%s .pio/build/release/firmware.bin)
          if [ $SIZE -gt 1572864 ]; then
            echo "Firmware too large: $SIZE bytes (max 1.5MB)"
            exit 1
          fi

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: firmware-${{ github.sha }}
          path: firmware/.pio/build/release/firmware.bin

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Download firmware
        uses: actions/download-artifact@v4
        with:
          name: firmware-${{ github.sha }}
          path: firmware/

      - name: OTA Deploy
        env:
          OTA_PASSWORD: ${{ secrets.OTA_PASSWORD }}
          DEVICE_IP: ${{ secrets.DEVICE_IP }}
        run: |
          pip install platformio
          cd firmware
          python -m platformio device upload \
            --upload-port $DEVICE_IP \
            -t upload \
            -e release

      - name: Verify deployment
        env:
          DEVICE_IP: ${{ secrets.DEVICE_IP }}
        run: |
          sleep 10  # Wait for reboot
          curl -sf http://$DEVICE_IP/api/status | python -m json.tool
```

**Required GitHub Secrets:**
- `OTA_PASSWORD`: OTA authentication password
- `DEVICE_IP`: Device IP for deployment

**Alternative: OTA via MQTT (fleet deployment):**
```yaml
  deploy-fleet:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Upload firmware to S3/server
        run: |
          aws s3 cp firmware/firmware.bin s3://ota-bucket/firmware-${{ github.sha }}.bin

      - name: Notify devices via MQTT
        run: |
          pip install paho-mqtt
          python -c "
          import paho.mqtt.publish as publish
          publish.single(
              'ota/update',
              '{\"url\": \"https://ota.example.com/firmware-${{ github.sha }}.bin\", \"version\": \"${{ github.sha }}\"}',
              hostname='${{ secrets.MQTT_BROKER }}',
              port=1883
          )"
```

This gives you: commit → test on PC → build → size check → OTA deploy → verify.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a PlatformIO library for a modular sensor abstraction with I2C auto-detection.",
            },
            {
                "from": "gpt",
                "value": """Modular sensor library with I2C auto-detection:

**lib/SensorHub/library.json:**
```json
{
  "name": "SensorHub",
  "version": "1.0.0",
  "description": "Auto-detecting I2C sensor hub",
  "frameworks": ["arduino"],
  "platforms": ["espressif32", "espressif8266", "atmelavr"]
}
```

**lib/SensorHub/SensorHub.h:**
```cpp
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <vector>
#include <memory>

// Base sensor interface
class ISensor {
public:
    virtual ~ISensor() = default;
    virtual const char* name() const = 0;
    virtual uint8_t address() const = 0;
    virtual bool begin() = 0;
    virtual bool read() = 0;
    virtual float temperature() { return NAN; }
    virtual float humidity() { return NAN; }
    virtual float pressure() { return NAN; }
    virtual float light() { return NAN; }

    // JSON serialization
    virtual void toJson(char* buf, size_t len) {
        snprintf(buf, len, "{\"sensor\":\"%s\",\"addr\":\"0x%02X\"}",
                 name(), address());
    }
};

// BME280 (temp + humidity + pressure)
class BME280Sensor : public ISensor {
    uint8_t addr_;
    float temp_, hum_, press_;
    // Calibration data
    uint16_t dig_T1_; int16_t dig_T2_, dig_T3_;

public:
    explicit BME280Sensor(uint8_t addr = 0x76) : addr_(addr) {}
    const char* name() const override { return "BME280"; }
    uint8_t address() const override { return addr_; }

    bool begin() override {
        Wire.beginTransmission(addr_);
        Wire.write(0xD0);  // ID register
        Wire.endTransmission();
        Wire.requestFrom(addr_, (uint8_t)1);
        uint8_t id = Wire.read();
        if (id != 0x60 && id != 0x58) return false;  // BME280=0x60, BMP280=0x58

        // Read calibration, set oversampling
        read_calibration();
        write_reg(0xF2, 0x01);  // ctrl_hum: x1
        write_reg(0xF4, 0x27);  // ctrl_meas: T x1, P x1, normal
        return true;
    }

    bool read() override {
        uint8_t data[8];
        Wire.beginTransmission(addr_);
        Wire.write(0xF7);
        Wire.endTransmission();
        Wire.requestFrom(addr_, (uint8_t)8);
        for (int i = 0; i < 8; i++) data[i] = Wire.read();

        int32_t adc_T = ((int32_t)data[3] << 12) | ((int32_t)data[4] << 4) | (data[5] >> 4);
        temp_ = compensate_temp(adc_T);
        return true;
    }

    float temperature() override { return temp_; }
    float humidity() override { return hum_; }
    float pressure() override { return press_; }

    void toJson(char* buf, size_t len) override {
        snprintf(buf, len,
            "{\"sensor\":\"BME280\",\"temp\":%.1f,\"hum\":%.1f,\"press\":%.1f}",
            temp_, hum_, press_);
    }

private:
    void write_reg(uint8_t reg, uint8_t val) {
        Wire.beginTransmission(addr_);
        Wire.write(reg);
        Wire.write(val);
        Wire.endTransmission();
    }
    void read_calibration() {
        Wire.beginTransmission(addr_);
        Wire.write(0x88);
        Wire.endTransmission();
        Wire.requestFrom(addr_, (uint8_t)6);
        dig_T1_ = Wire.read() | (Wire.read() << 8);
        dig_T2_ = Wire.read() | (Wire.read() << 8);
        dig_T3_ = Wire.read() | (Wire.read() << 8);
    }
    float compensate_temp(int32_t adc_T) {
        int32_t var1 = ((((adc_T >> 3) - ((int32_t)dig_T1_ << 1))) * dig_T2_) >> 11;
        int32_t var2 = (((((adc_T >> 4) - (int32_t)dig_T1_) *
                          ((adc_T >> 4) - (int32_t)dig_T1_)) >> 12) * dig_T3_) >> 14;
        return ((var1 + var2) * 5 + 128) / 25600.0f;
    }
};

// BH1750 (light sensor)
class BH1750Sensor : public ISensor {
    uint8_t addr_;
    float lux_;
public:
    explicit BH1750Sensor(uint8_t addr = 0x23) : addr_(addr), lux_(0) {}
    const char* name() const override { return "BH1750"; }
    uint8_t address() const override { return addr_; }
    bool begin() override {
        Wire.beginTransmission(addr_);
        Wire.write(0x10);  // Continuous high-res mode
        return Wire.endTransmission() == 0;
    }
    bool read() override {
        Wire.requestFrom(addr_, (uint8_t)2);
        if (Wire.available() < 2) return false;
        uint16_t raw = (Wire.read() << 8) | Wire.read();
        lux_ = raw / 1.2f;
        return true;
    }
    float light() override { return lux_; }
    void toJson(char* buf, size_t len) override {
        snprintf(buf, len, "{\"sensor\":\"BH1750\",\"lux\":%.1f}", lux_);
    }
};

// Auto-detecting sensor hub
class SensorHub {
    std::vector<std::unique_ptr<ISensor>> sensors_;

    // Known I2C addresses → sensor constructors
    struct KnownSensor {
        uint8_t addr;
        std::unique_ptr<ISensor> (*create)(uint8_t);
    };

    static std::unique_ptr<ISensor> make_bme280(uint8_t a) {
        return std::make_unique<BME280Sensor>(a);
    }
    static std::unique_ptr<ISensor> make_bh1750(uint8_t a) {
        return std::make_unique<BH1750Sensor>(a);
    }

    static constexpr KnownSensor known[] = {
        {0x76, make_bme280}, {0x77, make_bme280},  // BME280
        {0x23, make_bh1750}, {0x5C, make_bh1750},  // BH1750
    };

public:
    size_t scan(TwoWire& wire = Wire) {
        sensors_.clear();
        for (const auto& k : known) {
            wire.beginTransmission(k.addr);
            if (wire.endTransmission() == 0) {
                auto sensor = k.create(k.addr);
                if (sensor->begin()) {
                    Serial.printf("  Found: %s @ 0x%02X\n", sensor->name(), k.addr);
                    sensors_.push_back(std::move(sensor));
                }
            }
        }
        return sensors_.size();
    }

    void readAll() {
        for (auto& s : sensors_) s->read();
    }

    size_t count() const { return sensors_.size(); }
    ISensor* get(size_t i) { return sensors_[i].get(); }

    void toJson(char* buf, size_t len) {
        int pos = snprintf(buf, len, "[");
        for (size_t i = 0; i < sensors_.size(); i++) {
            if (i > 0) pos += snprintf(buf + pos, len - pos, ",");
            sensors_[i]->toJson(buf + pos, len - pos);
            pos = strlen(buf);
        }
        snprintf(buf + pos, len - pos, "]");
    }
};
```

**Usage in main.cpp:**
```cpp
#include <SensorHub.h>

SensorHub hub;

void setup() {
    Serial.begin(115200);
    Wire.begin(21, 22);  // SDA, SCL

    Serial.println("Scanning I2C sensors...");
    size_t found = hub.scan();
    Serial.printf("Found %d sensors\n", found);
}

void loop() {
    hub.readAll();
    char json[512];
    hub.toJson(json, sizeof(json));
    Serial.println(json);
    delay(2000);
}
```

Add new sensors by implementing `ISensor` and registering in `known[]`.""",
            },
        ]
    },
]


PIO_KEYWORDS = [
    "platformio",
    "pio",
    "arduino",
    "esp32",
    "esp8266",
    "esp-idf",
    "wemos",
    "nodemcu",
    "teensy",
    "stm32duino",
    "platformio.ini",
    ".ino",
    "sketch",
    "wire.h",
    "spi.h",
    "serial",
    "i2c",
    "uart",
    "digitalread",
    "digitalwrite",
    "analogread",
    "pinmode",
    "wifi.h",
    "wificlient",
    "webserver",
    "asyncwebserver",
    "pubsubclient",
    "mqtt",
    "ota",
    "elegantota",
    "arduinoota",
    "adafruit",
    "sparkfun",
    "dht",
    "bme280",
    "neopixel",
    "freertos",
    "vtaskdelay",
    "xtaskcreate",
    "deep sleep",
    "esp_sleep",
    "esp_deep_sleep",
    "platformio test",
    "unity test",
    "lib_deps",
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert PlatformIO/Arduino datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets -- skipping HF download")
        return []

    samples = []

    # 1. Arduino docs (14.3k)
    print("  Downloading gavmac00/arduino-docs...")
    try:
        ds = load_dataset("gavmac00/arduino-docs", split="train", streaming=True)
        count = 0
        for row in ds:
            text = row.get("text", "") or row.get("content", "")
            title = row.get("title", "") or row.get("name", "")
            if not text or len(text) < 100:
                continue
            question = (
                f"Explain and provide Arduino/PlatformIO code for: {title}"
                if title
                else "Explain this Arduino concept and provide example code."
            )
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": text.strip()},
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Arduino doc examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. ESP-IDF code (13.7k) — filtered for Arduino-relevant
    print("  Downloading gouthamsk/esp_idf_code (Arduino filter)...")
    try:
        ds = load_dataset("gouthamsk/esp_idf_code", split="train", streaming=True)
        count = 0
        for row in ds:
            code = row.get("code", "") or row.get("content", "") or row.get("text", "")
            title = (
                row.get("title", "") or row.get("name", "") or row.get("file_name", "")
            )
            if not code or len(code) < 80:
                continue
            question = (
                f"Write PlatformIO/ESP-IDF code for: {title}"
                if title
                else "Write this ESP32 code and explain it."
            )
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question},
                        {"from": "gpt", "value": f"```c\n{code.strip()}\n```"},
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} ESP-IDF code examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. Arduino StackExchange
    print("  Downloading bshada/arduino.stackexchange.com...")
    try:
        ds = load_dataset(
            "bshada/arduino.stackexchange.com", split="train", streaming=True
        )
        count = 0
        for row in ds:
            title = row.get("Title", "")
            body = row.get("Body", "")
            answer = row.get("Answer", "")
            if not title or not answer or len(answer) < 100:
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
        print(f"    Got {count} Arduino SE examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 4. Electronics SE (PlatformIO/Arduino filter)
    print("  Downloading bshada/electronics.stackexchange.com (PIO filter)...")
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
            if not any(kw in combined for kw in PIO_KEYWORDS):
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
            if count >= max_samples // 2:
                break
        print(f"    Got {count} Electronics SE (PIO) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Build PlatformIO/Arduino fine-tuning dataset"
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
    output_path = args.output or os.path.join(output_dir, "platformio_chat.jsonl")

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
            "\n  To enrich: python build_platformio_dataset.py --with-hf --max-samples 2000"
        )


if __name__ == "__main__":
    main()
