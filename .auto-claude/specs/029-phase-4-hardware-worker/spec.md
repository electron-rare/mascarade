# Phase 4 — Hardware Runtime Worker Specification

**Document:** SPEC-029-P4 — Universal Node Engine Phase 4 Hardware Runtime Worker
**Date:** 2026-03-16
**Version:** 1.0
**Status:** Draft
**Parent:** SPEC-029 (Universal Node Engine Architecture)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Hardware-Specific Port Types](#2-hardware-specific-port-types)
3. [ESP32 Control Nodes](#3-esp32-control-nodes)
4. [MIDI I/O Nodes](#4-midi-io-nodes)
5. [DMX Lighting Nodes](#5-dmx-lighting-nodes)
6. [Serial Communication Nodes](#6-serial-communication-nodes)
7. [Real-Time Control Loop Nodes](#7-real-time-control-loop-nodes)
8. [Device Discovery Protocol](#8-device-discovery-protocol)
9. [Resource Constraints and Scheduling](#9-resource-constraints-and-scheduling)
10. [Safety Constraints](#10-safety-constraints)
11. [Acceptance Criteria](#11-acceptance-criteria)

---

## 1. Overview

Phase 4 introduces the Hardware Runtime Worker — the domain worker responsible for bridging the Universal Node Engine with physical hardware devices. This worker enables graph-based workflows to interact with ESP32 microcontrollers, MIDI instruments, DMX lighting fixtures, serial devices, and real-time control systems.

### 1.1 Goals

- Implement ESP32 control nodes for device discovery, GPIO manipulation, sensor reading, and OTA firmware updates
- Implement MIDI I/O nodes for input capture, output generation, CC mapping, note triggering, and clock synchronization
- Implement DMX lighting nodes for universe management, fixture control, and scene programming
- Implement serial communication nodes for protocol adaptation, baud rate configuration, and data parsing
- Implement real-time control loop nodes with PID controllers, timing constraints, and safety interlocks
- Define hardware-specific port types: `MIDIMessage`, `DMXFrame`, `SerialData`, `GPIOState`, `SensorReading`
- Establish a device discovery protocol with mDNS/UDP broadcast
- Handle graceful degradation when hardware devices are absent or unreachable

### 1.2 Non-Goals

- Custom PCB design or schematic capture (Phase 3 — Electronics Worker)
- FPGA programming or ASIC design
- Audio DSP processing (handled by dedicated audio nodes if needed)
- Direct kernel-level driver development

### 1.3 Dependencies

- Phase 0 Foundations (core type system, graph execution runtime, NodeWorker interface, node registry)
- Phase 3 Electronics Worker (for `FirmwareBinary` type used in OTA updates)
- Python 3.11+ with Pydantic (existing Mascarade core stack)
- `pyserial` for serial communication
- `python-rtmidi` or `mido` for MIDI I/O
- `sacn` or `pyartnet` for DMX/Art-Net output
- `zeroconf` for mDNS-based device discovery
- `httpx` for ESP32 HTTP OTA and REST APIs
- `websockets` for ESP32 WebSocket communication
- `aiomqtt` for MQTT-based ESP32 communication

---

## 2. Hardware-Specific Port Types

The Hardware Runtime Worker registers five domain-specific port types with the core type system during worker initialization. These types are validated at both connection time and execution time.

### 2.1 Type Definitions

```python
"""Hardware Runtime Worker — Domain-specific port types.

Registered with the NodeTypeRegistry at worker startup.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- GPIOState ---

class GPIODirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"

class GPIOPull(StrEnum):
    NONE = "none"
    UP = "up"
    DOWN = "down"

class GPIOState(BaseModel):
    """State of a single GPIO pin on a microcontroller."""
    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["GPIOState"] = "GPIOState"

    pin: int = Field(ge=0, le=39, description="GPIO pin number (ESP32: 0-39)")
    direction: GPIODirection = GPIODirection.INPUT
    value: bool = False
    pull: GPIOPull = GPIOPull.NONE
    pwm_duty: float | None = Field(None, ge=0.0, le=1.0, description="PWM duty cycle 0.0-1.0")
    pwm_freq: int | None = Field(None, ge=1, le=40_000_000, description="PWM frequency in Hz")


# --- SensorReading ---

class SensorReading(BaseModel):
    """A timestamped reading from a hardware sensor."""
    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["SensorReading"] = "SensorReading"

    sensor_id: str = Field(description="Unique sensor identifier")
    sensor_type: str = Field(description="Sensor type (temperature, humidity, distance, etc.)")
    value: float = Field(description="Numeric reading value")
    unit: str = Field(description="Unit of measurement (°C, %, mm, lux, etc.)")
    timestamp_ms: int = Field(description="Unix timestamp in milliseconds")
    quality: float = Field(1.0, ge=0.0, le=1.0, description="Reading quality/confidence 0.0-1.0")
    raw: int | None = Field(None, description="Raw ADC value if applicable")


# --- MIDIMessage ---

class MIDIStatus(IntEnum):
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLY_AFTERTOUCH = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_AFTERTOUCH = 0xD0
    PITCH_BEND = 0xE0
    SYSTEM = 0xF0

class MIDIMessage(BaseModel):
    """A single MIDI message."""
    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["MIDIMessage"] = "MIDIMessage"

    status: int = Field(ge=0, le=255, description="MIDI status byte")
    channel: int = Field(0, ge=0, le=15, description="MIDI channel 0-15")
    data1: int = Field(0, ge=0, le=127, description="First data byte")
    data2: int = Field(0, ge=0, le=127, description="Second data byte")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")

    @property
    def message_type(self) -> MIDIStatus:
        return MIDIStatus(self.status & 0xF0)


# --- DMXFrame ---

class DMXFrame(BaseModel):
    """A single DMX512 frame (up to 512 channels per universe)."""
    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["DMXFrame"] = "DMXFrame"

    universe: int = Field(0, ge=0, le=32767, description="DMX universe number")
    channels: list[int] = Field(
        default_factory=lambda: [0] * 512,
        description="512 channel values (0-255)",
    )
    priority: int = Field(100, ge=0, le=200, description="sACN priority")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")

    def set_channel(self, channel: int, value: int) -> None:
        if not (1 <= channel <= 512):
            raise ValueError(f"DMX channel must be 1-512, got {channel}")
        if not (0 <= value <= 255):
            raise ValueError(f"DMX value must be 0-255, got {value}")
        self.channels[channel - 1] = value


# --- SerialData ---

class SerialParity(StrEnum):
    NONE = "none"
    EVEN = "even"
    ODD = "odd"

class SerialData(BaseModel):
    """A chunk of serial communication data."""
    kind: Literal["domain"] = "domain"
    domain: Literal["hardware"] = "hardware"
    name: Literal["SerialData"] = "SerialData"

    port: str = Field(description="Serial port identifier (e.g., /dev/ttyUSB0)")
    data: str = Field(description="Base64-encoded byte payload")
    baud_rate: int = Field(115200, description="Baud rate")
    parity: SerialParity = SerialParity.NONE
    stop_bits: float = Field(1.0, description="Stop bits (1, 1.5, 2)")
    timestamp_ms: int = Field(0, description="Timestamp in milliseconds")


# DomainType registration entries for the NodeTypeRegistry
HARDWARE_DOMAIN_TYPES = [
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "GPIOState",
        "schema": GPIOState.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "SensorReading",
        "schema": SensorReading.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "MIDIMessage",
        "schema": MIDIMessage.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "DMXFrame",
        "schema": DMXFrame.model_json_schema(),
    },
    {
        "kind": "domain",
        "domain": "hardware",
        "name": "SerialData",
        "schema": SerialData.model_json_schema(),
    },
]
```

### 2.2 Type Coercion Rules (Hardware Domain)

| From | To | Rule |
|------|----|------|
| `GPIOState` | `SensorReading` | Extract `value` as float (0.0/1.0 for digital) |
| `SensorReading` | `number` | Extract `value` field |
| `MIDIMessage` | `array<integer>` | Serialize as `[status, data1, data2]` |
| `DMXFrame` | `array<integer>` | Extract `channels` array |
| `SerialData` | `binary` | Decode Base64 `data` field |

Cross-domain coercion (e.g., `MIDIMessage` → `LLMResponse`) is **prohibited** without an explicit Phase 5 adapter node.

---

## 3. ESP32 Control Nodes

ESP32 nodes communicate with ESP32 microcontrollers over HTTP, WebSocket, or MQTT. All ESP32 nodes share a common device connection model.

### 3.1 Connection Model

ESP32 devices are identified by a combination of `device_id` (mDNS hostname or IP address) and `protocol` (http, websocket, mqtt). Each node maintains a connection pool managed by the Hardware Worker's device registry.

```python
class ESP32ConnectionConfig(BaseModel):
    """Connection configuration for an ESP32 device."""
    device_id: str = Field(description="mDNS hostname or IP address")
    protocol: Literal["http", "websocket", "mqtt"] = "http"
    port: int = Field(80, description="TCP port for HTTP/WS, or MQTT broker port")
    mqtt_broker: str | None = Field(None, description="MQTT broker address if protocol=mqtt")
    mqtt_topic_prefix: str = Field("mascarade/esp32", description="MQTT topic prefix")
    timeout_ms: int = Field(5000, ge=100, le=30000, description="Connection timeout")
    retry_count: int = Field(3, ge=0, le=10, description="Retry attempts on failure")
```

### 3.2 Node Catalog

#### 3.2.1 `hardware.esp32.discover`

Discovers ESP32 devices on the local network via mDNS (`_mascarade._tcp`) and UDP broadcast.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `trigger` | Input | `void` | Trigger discovery scan |
| `network` | Input | `optional<string>` | Network CIDR to scan (default: auto-detect) |
| `timeout_ms` | Input | `optional<integer>` | Discovery timeout (default: 5000) |
| `devices` | Output | `array<json>` | Discovered device descriptors |
| `count` | Output | `integer` | Number of devices found |

#### 3.2.2 `hardware.esp32.gpio`

Reads or writes GPIO pin state on a connected ESP32.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `device` | Input | `json` | ESP32 connection config |
| `pin_config` | Input | `GPIOState` | Desired GPIO configuration |
| `state` | Output | `GPIOState` | Actual GPIO state after operation |
| `error` | Output | `optional<string>` | Error message if operation failed |

#### 3.2.3 `hardware.esp32.sensor`

Reads sensor data from an ESP32 device.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `device` | Input | `json` | ESP32 connection config |
| `sensor_id` | Input | `string` | Sensor identifier on the device |
| `interval_ms` | Input | `optional<integer>` | Polling interval for stream mode |
| `reading` | Output | `SensorReading` | Latest sensor reading |
| `stream` | Output | `stream<SensorReading>` | Continuous sensor stream (if interval set) |

#### 3.2.4 `hardware.esp32.ota`

Performs over-the-air firmware update on an ESP32 device.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `device` | Input | `json` | ESP32 connection config |
| `firmware` | Input | `binary` | Firmware binary (or `FirmwareBinary` from Phase 3) |
| `verify` | Input | `optional<boolean>` | Verify firmware hash after upload (default: true) |
| `progress` | Output | `stream<number>` | Upload progress 0.0-1.0 |
| `success` | Output | `boolean` | Whether OTA completed successfully |
| `error` | Output | `optional<string>` | Error details if failed |

### 3.3 Graceful Degradation

When an ESP32 device is absent or unreachable:

1. **Discovery nodes** return an empty `devices` array — no error raised
2. **GPIO/Sensor nodes** enter a configurable fallback mode:
   - `error` — emit error on output port, halt downstream (default)
   - `mock` — return simulated data (for development/testing)
   - `last_known` — return the last successfully read value with degraded `quality`
3. **OTA nodes** always fail explicitly with a descriptive error message
4. All connection failures are reported to the Metrics subsystem with device ID, failure reason, and timestamp

---

## 4. MIDI I/O Nodes

MIDI nodes interface with MIDI hardware and software ports via the system's MIDI subsystem (ALSA on Linux, CoreMIDI on macOS).

### 4.1 Node Catalog

#### 4.1.1 `hardware.midi.input`

Captures MIDI messages from a hardware or virtual MIDI input port.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `port_name` | Input | `string` | MIDI input port name or pattern |
| `channel_filter` | Input | `optional<integer>` | Filter by MIDI channel (0-15, null = all) |
| `message_filter` | Input | `optional<array<string>>` | Filter by message type (note_on, cc, etc.) |
| `messages` | Output | `stream<MIDIMessage>` | Stream of incoming MIDI messages |

#### 4.1.2 `hardware.midi.output`

Sends MIDI messages to a hardware or virtual MIDI output port.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `port_name` | Input | `string` | MIDI output port name or pattern |
| `message` | Input | `MIDIMessage` | MIDI message to send |
| `batch` | Input | `optional<array<MIDIMessage>>` | Batch of messages to send atomically |
| `sent` | Output | `boolean` | Whether the message was sent successfully |

#### 4.1.3 `hardware.midi.cc_map`

Maps incoming MIDI Control Change messages to normalized float values.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `input` | Input | `MIDIMessage` | Incoming MIDI message |
| `cc_number` | Input | `integer` | CC number to map (0-127) |
| `range_min` | Input | `optional<number>` | Output range minimum (default: 0.0) |
| `range_max` | Input | `optional<number>` | Output range maximum (default: 1.0) |
| `value` | Output | `number` | Mapped value |
| `raw` | Output | `integer` | Raw CC value (0-127) |

#### 4.1.4 `hardware.midi.note_trigger`

Generates MIDI note on/off messages from trigger inputs.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `trigger` | Input | `void` | Fire a note |
| `note` | Input | `integer` | MIDI note number (0-127) |
| `velocity` | Input | `optional<integer>` | Note velocity (default: 100) |
| `channel` | Input | `optional<integer>` | MIDI channel (default: 0) |
| `duration_ms` | Input | `optional<integer>` | Auto note-off after duration (default: null = manual) |
| `message` | Output | `MIDIMessage` | Generated MIDI message |

#### 4.1.5 `hardware.midi.clock`

Synchronizes MIDI clock — generates or follows MIDI timing clock messages.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `mode` | Input | `string` | "leader" (generate clock) or "follower" (receive clock) |
| `bpm` | Input | `optional<number>` | BPM for leader mode (default: 120.0) |
| `port_name` | Input | `string` | MIDI port for clock I/O |
| `tick` | Output | `stream<void>` | 24-ppqn tick stream |
| `beat` | Output | `stream<integer>` | Beat counter (resets on start) |
| `current_bpm` | Output | `number` | Actual BPM (measured in follower mode) |

### 4.2 Graceful Degradation

When MIDI hardware is absent:

1. **Input nodes** emit no messages and log a warning — they do not block graph execution
2. **Output nodes** silently discard messages and set `sent = false`
3. A `hardware.midi.virtual` utility node can create virtual MIDI ports for testing without hardware

---

## 5. DMX Lighting Nodes

DMX nodes control lighting fixtures via DMX512 protocol, using Art-Net or sACN (E1.31) over Ethernet.

### 5.1 Node Catalog

#### 5.1.1 `hardware.dmx.universe`

Manages a single DMX512 universe (512 channels).

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `universe_id` | Input | `integer` | Universe number (0-32767) |
| `protocol` | Input | `optional<string>` | "artnet" or "sacn" (default: "sacn") |
| `interface` | Input | `optional<string>` | Network interface to bind |
| `frame` | Input | `optional<DMXFrame>` | Frame to merge into universe |
| `output` | Output | `DMXFrame` | Current universe state |

#### 5.1.2 `hardware.dmx.fixture`

Controls a single DMX fixture with named channel attributes.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `universe` | Input | `integer` | Universe number |
| `start_channel` | Input | `integer` | Fixture start address (1-512) |
| `profile` | Input | `json` | Fixture profile (channel map: dimmer, r, g, b, pan, tilt, etc.) |
| `values` | Input | `map<string, number>` | Named attribute values (0.0-1.0) |
| `frame` | Output | `DMXFrame` | DMX frame with fixture channels set |

#### 5.1.3 `hardware.dmx.scene`

Programs and recalls DMX scenes (snapshots of fixture states).

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `scene_id` | Input | `string` | Scene identifier |
| `action` | Input | `string` | "store", "recall", "crossfade" |
| `fixtures` | Input | `optional<array<json>>` | Fixture states for store action |
| `fade_ms` | Input | `optional<integer>` | Crossfade duration in milliseconds |
| `frame` | Output | `DMXFrame` | Resulting DMX frame |

### 5.2 Graceful Degradation

When no DMX interface is available:

1. **Universe nodes** operate in simulation mode — they maintain internal state but do not transmit
2. A `hardware.dmx.visualizer` utility node renders a preview of the DMX output for development
3. DMX output is rate-limited to the protocol-mandated 44 Hz maximum refresh rate

---

## 6. Serial Communication Nodes

Serial nodes provide configurable serial port communication for interfacing with arbitrary hardware.

### 6.1 Node Catalog

#### 6.1.1 `hardware.serial.port`

Opens and manages a serial port connection.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `port_path` | Input | `string` | Serial port path (e.g., `/dev/ttyUSB0`) |
| `baud_rate` | Input | `integer` | Baud rate (9600, 115200, etc.) |
| `parity` | Input | `optional<string>` | Parity: "none", "even", "odd" (default: "none") |
| `stop_bits` | Input | `optional<number>` | Stop bits: 1, 1.5, 2 (default: 1) |
| `data` | Input | `optional<SerialData>` | Data to write |
| `received` | Output | `stream<SerialData>` | Received data stream |
| `connected` | Output | `boolean` | Connection status |

#### 6.1.2 `hardware.serial.parser`

Parses incoming serial data according to a configurable protocol.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `input` | Input | `SerialData` | Raw serial data |
| `delimiter` | Input | `optional<string>` | Message delimiter (default: "\n") |
| `format` | Input | `optional<string>` | Parse format: "line", "json", "csv", "binary_struct" |
| `struct_def` | Input | `optional<string>` | Python struct format string for binary parsing |
| `parsed` | Output | `json` | Parsed data |
| `raw_line` | Output | `optional<string>` | Raw line before parsing |

#### 6.1.3 `hardware.serial.protocol_adapter`

Adapts between common serial protocols (Modbus RTU, NMEA, custom framing).

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `input` | Input | `SerialData` | Raw serial data |
| `protocol` | Input | `string` | Protocol name: "modbus_rtu", "nmea", "custom" |
| `config` | Input | `optional<json>` | Protocol-specific configuration |
| `messages` | Output | `stream<json>` | Decoded protocol messages |
| `errors` | Output | `stream<string>` | Protocol decode errors |

### 6.2 Graceful Degradation

When serial ports are unavailable:

1. **Port nodes** report `connected = false` and emit no data
2. A `hardware.serial.mock` node can simulate serial data from a file or pattern for testing
3. Permission errors (common on Linux without `dialout` group) produce actionable error messages

---

## 7. Real-Time Control Loop Nodes

Real-time control nodes implement feedback control loops for hardware automation. These nodes have stricter timing requirements than other node types.

### 7.1 Node Catalog

#### 7.1.1 `hardware.control.pid`

A PID (Proportional-Integral-Derivative) controller node.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `setpoint` | Input | `number` | Desired target value |
| `measurement` | Input | `number` | Current measured value (from sensor) |
| `kp` | Input | `number` | Proportional gain |
| `ki` | Input | `number` | Integral gain |
| `kd` | Input | `number` | Derivative gain |
| `output_min` | Input | `optional<number>` | Output clamp minimum |
| `output_max` | Input | `optional<number>` | Output clamp maximum |
| `output` | Output | `number` | Control output value |
| `error` | Output | `number` | Current error (setpoint - measurement) |

#### 7.1.2 `hardware.control.timer`

Generates periodic trigger signals with configurable timing constraints.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `interval_ms` | Input | `integer` | Trigger interval in milliseconds |
| `max_jitter_ms` | Input | `optional<integer>` | Maximum acceptable jitter (default: 10) |
| `tick` | Output | `stream<void>` | Periodic trigger |
| `actual_interval_ms` | Output | `number` | Measured actual interval |
| `jitter_exceeded` | Output | `stream<boolean>` | Emits true when jitter exceeds threshold |

#### 7.1.3 `hardware.control.interlock`

Safety interlock node that gates control signals based on safety conditions.

| Port | Direction | Type | Description |
|------|-----------|------|-------------|
| `signal` | Input | `number` | Control signal to gate |
| `conditions` | Input | `array<boolean>` | Safety conditions (all must be true to pass) |
| `safe_value` | Input | `number` | Value to output when interlocked (default: 0) |
| `output` | Output | `number` | Gated control signal |
| `interlocked` | Output | `boolean` | Whether the interlock is active |
| `violation_log` | Output | `stream<json>` | Log of interlock activations |

### 7.2 Timing Constraints

Real-time control nodes declare timing requirements in their node definitions:

```python
class TimingConstraint(BaseModel):
    """Timing requirement for a real-time control node."""
    max_latency_ms: int = Field(description="Maximum acceptable execution latency")
    max_jitter_ms: int = Field(description="Maximum acceptable timing jitter")
    priority: Literal["hard", "soft"] = Field(
        "soft",
        description="hard = fail if violated, soft = warn and continue",
    )
```

The Graph Execution Runtime respects these constraints by:

1. Scheduling real-time nodes on a dedicated high-priority thread pool
2. Pre-allocating resources before execution begins
3. Bypassing the standard node queue when latency constraints are tight
4. Logging timing violations to the Metrics subsystem

### 7.3 Safety Interlocks

All hardware control loops **must** include at least one `hardware.control.interlock` node in the graph path between sensor input and actuator output. The graph validator enforces this rule:

- Graphs containing PID → GPIO/actuator paths without an interlock node fail validation
- Interlock nodes cannot be bypassed through graph topology
- Interlock activation events are persisted to the audit log
- A global emergency stop (`hardware.control.estop`) node can halt all hardware outputs across all active graphs

---

## 8. Device Discovery Protocol

### 8.1 Discovery Methods

The Hardware Worker supports three device discovery methods, tried in order:

1. **mDNS (primary):** Devices advertise `_mascarade._tcp.local` service records. The discovery node listens for mDNS announcements and queries for available services.

2. **UDP broadcast (fallback):** A broadcast message on port `9472` triggers devices to respond with their capability descriptors. Used on networks where mDNS is unreliable.

3. **Static configuration:** Devices can be manually registered in the Hardware Worker's configuration file for air-gapped or restricted networks.

### 8.2 Device Descriptor

Discovered devices report a standard descriptor:

```python
class HardwareDeviceDescriptor(BaseModel):
    """Descriptor reported by a discovered hardware device."""
    device_id: str = Field(description="Unique device identifier")
    device_type: str = Field(description="Device type (esp32, midi_interface, dmx_adapter, etc.)")
    hostname: str = Field(description="Network hostname or IP")
    port: int = Field(description="Primary communication port")
    protocols: list[str] = Field(description="Supported protocols (http, ws, mqtt, serial)")
    capabilities: list[str] = Field(description="Device capabilities (gpio, sensor, ota, etc.)")
    firmware_version: str | None = Field(None, description="Current firmware version")
    last_seen_ms: int = Field(description="Last seen timestamp in milliseconds")
    online: bool = Field(True, description="Whether device is currently reachable")
```

### 8.3 Device Registry

The Hardware Worker maintains a `DeviceRegistry` (modeled on the existing `AgentRegistry` pattern) that:

- Caches discovered devices with a configurable TTL (default: 60 seconds)
- Monitors device health via periodic ping/heartbeat
- Emits events when devices appear, disappear, or change state
- Provides device lookup by ID, type, or capability

---

## 9. Resource Constraints and Scheduling

### 9.1 Infrastructure Context

The target deployment environment is resource-constrained: **4 vCPU, 6.8 GiB RAM** (VMware Photon OS VM at `192.168.0.119`), shared with the full Mascarade stack (27+ active containers). The Hardware Worker must operate within strict resource budgets.

### 9.2 Resource Budgets

| Resource | Hardware Worker Budget | Rationale |
|----------|----------------------|-----------|
| CPU | ≤ 0.5 vCPU (sustained) | Leave headroom for core services |
| Memory | ≤ 256 MiB RSS | Aggressive limit due to swap pressure |
| Threads | ≤ 4 (2 general + 1 RT + 1 I/O) | Minimize context switching |
| Network | ≤ 10 Mbps sustained | Shared LAN with other services |
| Open file descriptors | ≤ 64 | Serial ports + sockets |

### 9.3 Scheduling Strategy

The Hardware Worker uses a tiered scheduling approach:

1. **Real-time tier:** PID controllers and timing-critical nodes run on a dedicated thread with elevated priority. Maximum 2 concurrent real-time graphs.

2. **I/O tier:** MIDI, DMX, and serial I/O nodes run on an asyncio event loop optimized for I/O-bound operations. Uses `asyncio.PriorityQueue` to prioritize time-sensitive I/O (MIDI clock, DMX frame output).

3. **Standard tier:** ESP32 HTTP communication, OTA updates, device discovery, and scene management run on the standard graph execution pool.

### 9.4 Backpressure and Throttling

When resource limits are approached:

1. **Sensor streams** reduce polling frequency automatically (adaptive backoff)
2. **DMX output** drops to minimum acceptable frame rate (10 Hz)
3. **OTA updates** are queued — only one concurrent OTA operation is allowed
4. **New graph executions** involving hardware nodes are rejected with a `ResourceExhausted` error if all slots are occupied

---

## 10. Safety Constraints

### 10.1 Hardware Control Safety Rules

1. **No unguarded actuator control:** Any graph path from sensor to actuator must include an interlock node. The graph validator enforces this at validation time.

2. **Fail-safe defaults:** All actuator nodes define a safe default state (GPIO LOW, PWM 0%, DMX blackout). On worker crash, connection loss, or emergency stop, outputs revert to safe defaults.

3. **Rate limiting:** GPIO writes are rate-limited to 100 Hz per pin. DMX output is capped at 44 Hz per universe. MIDI output is capped at 3125 bytes/second per port (MIDI DIN spec).

4. **Watchdog timer:** The Hardware Worker includes a watchdog that monitors control loop execution. If a control loop fails to execute within 5× its declared interval, the watchdog triggers a safe shutdown of that loop's outputs.

5. **Audit logging:** All hardware state changes (GPIO writes, DMX scene changes, OTA updates, interlock activations) are logged to the persistence layer with timestamps and originating graph/node IDs.

### 10.2 Emergency Stop Protocol

The `hardware.control.estop` node provides a global emergency stop:

1. Activated via API call, UI button, or hardware input (dedicated GPIO pin)
2. Immediately sets all active hardware outputs to safe defaults
3. Halts all running hardware control graphs
4. Requires explicit manual reset before hardware control can resume
5. Logs the E-stop event with full context (active graphs, output states, trigger source)

### 10.3 Permissions Model

Hardware nodes require explicit capability grants in the graph execution context:

| Capability | Description | Default |
|------------|-------------|---------|
| `hardware.gpio.write` | Write GPIO pins | Denied |
| `hardware.gpio.read` | Read GPIO pins | Granted |
| `hardware.ota.flash` | Perform OTA firmware updates | Denied |
| `hardware.serial.write` | Write to serial ports | Denied |
| `hardware.dmx.output` | Transmit DMX frames | Denied |
| `hardware.midi.output` | Send MIDI messages | Denied |

Write capabilities must be explicitly granted per-graph. Read capabilities are granted by default.

---

## 11. Acceptance Criteria

### 11.1 Functional Requirements

- [ ] All five hardware domain types (`GPIOState`, `SensorReading`, `MIDIMessage`, `DMXFrame`, `SerialData`) are registered with the NodeTypeRegistry
- [ ] ESP32 discovery node returns device descriptors via mDNS within 5 seconds
- [ ] ESP32 GPIO read/write round-trip completes within 100ms over HTTP
- [ ] ESP32 OTA update streams progress and verifies firmware hash
- [ ] MIDI input node captures messages from a connected MIDI device
- [ ] MIDI clock node maintains ±1ms jitter at 120 BPM in leader mode
- [ ] DMX universe node outputs sACN frames at 40 Hz
- [ ] DMX fixture node correctly maps named attributes to channel values
- [ ] Serial port node connects, sends, and receives data at configured baud rate
- [ ] Serial parser node correctly parses line-delimited, JSON, and CSV formats
- [ ] PID controller node converges on setpoint within acceptable bounds
- [ ] Interlock node blocks output when any safety condition is false
- [ ] Emergency stop halts all hardware outputs within 50ms

### 11.2 Graceful Degradation Requirements

- [ ] All hardware nodes operate without errors when no hardware is connected (mock/fallback mode)
- [ ] Device discovery returns empty results (not errors) when no devices are found
- [ ] MIDI nodes log warnings but do not block graph execution when ports are unavailable
- [ ] DMX nodes operate in simulation mode when no network interface is bound

### 11.3 Resource Constraint Requirements

- [ ] Hardware Worker RSS stays below 256 MiB under normal operation
- [ ] Real-time control loops maintain ≤10ms jitter on the target VM
- [ ] Maximum 2 concurrent real-time graphs enforced
- [ ] Backpressure mechanisms activate before resource exhaustion

### 11.4 Safety Requirements

- [ ] Graph validator rejects graphs with unguarded actuator paths (no interlock)
- [ ] Watchdog timer triggers safe shutdown on control loop timeout
- [ ] All hardware state changes are persisted to the audit log
- [ ] Emergency stop halts all outputs and requires manual reset
- [ ] Write capabilities are denied by default and require explicit grants
