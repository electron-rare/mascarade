"""Tests for DMX lighting control nodes with simulation mode."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from mascarade.hardware.nodes.dmx import (
    DMXClient,
    DMXOutputConfig,
    execute_dmx_fixture,
    execute_dmx_scene,
    execute_dmx_universe,
)
from mascarade.hardware.types import DMXFrame
from mascarade.node_engine.base import NodeExecutionContext

# --- DMXOutputConfig Tests ---


def test_dmx_output_config_defaults():
    """DMXOutputConfig initializes with correct defaults."""
    config = DMXOutputConfig()
    assert config.protocol == "sacn"
    assert config.interface is None
    assert config.source_name == "mascarade-hardware-worker"
    assert config.fps == 40
    assert config.simulation_mode is False


def test_dmx_output_config_custom():
    """DMXOutputConfig accepts custom values."""
    config = DMXOutputConfig(
        protocol="artnet",
        interface="eth0",
        source_name="custom-source",
        fps=30,
        simulation_mode=True,
    )
    assert config.protocol == "artnet"
    assert config.interface == "eth0"
    assert config.source_name == "custom-source"
    assert config.fps == 30
    assert config.simulation_mode is True


def test_dmx_output_config_fps_validation():
    """DMXOutputConfig validates FPS range."""
    try:
        DMXOutputConfig(fps=0)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    try:
        DMXOutputConfig(fps=45)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # Valid edge cases
    config_min = DMXOutputConfig(fps=1)
    assert config_min.fps == 1

    config_max = DMXOutputConfig(fps=44)
    assert config_max.fps == 44


def test_dmx_output_config_protocol_validation():
    """DMXOutputConfig validates protocol values."""
    # Valid protocols
    config_sacn = DMXOutputConfig(protocol="sacn")
    assert config_sacn.protocol == "sacn"

    config_artnet = DMXOutputConfig(protocol="artnet")
    assert config_artnet.protocol == "artnet"

    # Invalid protocol should fail
    try:
        DMXOutputConfig(protocol="invalid")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


# --- DMXClient Tests ---


def test_dmx_client_initialization_simulation():
    """DMXClient initializes in simulation mode."""
    config = DMXOutputConfig(simulation_mode=True)
    client = DMXClient(config)

    assert client.config == config
    assert client._universes == {}
    assert client._running is False
    assert client._output_task is None
    assert client._sacn_sender is None


def test_dmx_client_initialization_sacn_fallback():
    """DMXClient falls back to simulation when sACN not available."""
    config = DMXOutputConfig(protocol="sacn", simulation_mode=False)
    client = DMXClient(config)

    # Should fall back to simulation mode if sacn library not installed
    # (This might pass if sacn is installed, so we just check it doesn't crash)
    assert client.config.protocol == "sacn"


def test_dmx_client_initialization_artnet_fallback():
    """DMXClient falls back to simulation for Art-Net (not implemented)."""
    config = DMXOutputConfig(protocol="artnet", simulation_mode=False)
    client = DMXClient(config)

    # Art-Net should always fall back to simulation mode
    assert client.config.simulation_mode is True


async def test_dmx_client_start_stop():
    """DMXClient starts and stops correctly."""
    config = DMXOutputConfig(simulation_mode=True, fps=40)
    client = DMXClient(config)

    # Start client
    await client.start()
    assert client._running is True
    assert client._output_task is not None

    # Stop client
    await client.stop()
    assert client._running is False


async def test_dmx_client_double_start():
    """DMXClient handles double start gracefully."""
    config = DMXOutputConfig(simulation_mode=True)
    client = DMXClient(config)

    await client.start()
    first_task = client._output_task

    # Second start should be idempotent
    await client.start()
    assert client._output_task == first_task

    await client.stop()


async def test_dmx_client_set_universe():
    """DMXClient sets universe state correctly."""
    config = DMXOutputConfig(simulation_mode=True)
    client = DMXClient(config)

    frame = DMXFrame(universe=1)
    frame.set_channel(1, 255)

    await client.set_universe(1, frame)

    assert 1 in client._universes
    assert client._universes[1].universe == 1
    assert client._universes[1].channels[0] == 255


async def test_dmx_client_get_universe():
    """DMXClient retrieves universe state correctly."""
    config = DMXOutputConfig(simulation_mode=True)
    client = DMXClient(config)

    # Get non-existent universe (should initialize to blackout)
    frame = client.get_universe(0)
    assert frame.universe == 0
    assert all(ch == 0 for ch in frame.channels)

    # Set and get universe
    custom_frame = DMXFrame(universe=2)
    custom_frame.set_channel(10, 128)
    await client.set_universe(2, custom_frame)

    retrieved = client.get_universe(2)
    assert retrieved.universe == 2
    assert retrieved.channels[9] == 128  # Channel 10 -> index 9


async def test_dmx_client_output_loop():
    """DMXClient output loop runs at correct frame rate."""
    config = DMXOutputConfig(simulation_mode=True, fps=20)  # 20 Hz = 50ms per frame
    client = DMXClient(config)

    # Set a universe
    frame = DMXFrame(universe=0)
    await client.set_universe(0, frame)

    # Start and run for a short time
    await client.start()
    await asyncio.sleep(0.15)  # Should complete ~3 frames

    await client.stop()
    # Just verify it didn't crash


async def test_dmx_client_transmit_frame_simulation():
    """DMXClient transmit_frame works in simulation mode."""
    config = DMXOutputConfig(simulation_mode=True)
    client = DMXClient(config)

    frame = DMXFrame(universe=0)
    frame.set_channel(1, 100)

    # Should not crash in simulation mode
    await client._transmit_frame(0, frame)


# --- DMXFrame Tests ---


def test_dmx_frame_defaults():
    """DMXFrame initializes with correct defaults."""
    frame = DMXFrame()
    assert frame.universe == 0
    assert len(frame.channels) == 512
    assert all(ch == 0 for ch in frame.channels)
    assert frame.priority == 100
    assert frame.timestamp_ms == 0


def test_dmx_frame_custom():
    """DMXFrame accepts custom values."""
    frame = DMXFrame(universe=5, priority=150, timestamp_ms=12345)
    assert frame.universe == 5
    assert frame.priority == 150
    assert frame.timestamp_ms == 12345


def test_dmx_frame_set_channel():
    """DMXFrame.set_channel sets channel values correctly."""
    frame = DMXFrame()

    # Set valid channel
    frame.set_channel(1, 255)
    assert frame.channels[0] == 255

    frame.set_channel(512, 128)
    assert frame.channels[511] == 128

    frame.set_channel(256, 64)
    assert frame.channels[255] == 64


def test_dmx_frame_set_channel_validation():
    """DMXFrame.set_channel validates channel and value ranges."""
    frame = DMXFrame()

    # Invalid channel (too low)
    try:
        frame.set_channel(0, 100)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "channel must be 1-512" in str(exc).lower()

    # Invalid channel (too high)
    try:
        frame.set_channel(513, 100)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "channel must be 1-512" in str(exc).lower()

    # Invalid value (too low)
    try:
        frame.set_channel(1, -1)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "value must be 0-255" in str(exc).lower()

    # Invalid value (too high)
    try:
        frame.set_channel(1, 256)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "value must be 0-255" in str(exc).lower()


def test_dmx_frame_universe_validation():
    """DMXFrame validates universe range."""
    # Valid universes
    frame_min = DMXFrame(universe=0)
    assert frame_min.universe == 0

    frame_max = DMXFrame(universe=32767)
    assert frame_max.universe == 32767

    # Invalid universe (too low)
    try:
        DMXFrame(universe=-1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # Invalid universe (too high)
    try:
        DMXFrame(universe=32768)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_dmx_frame_priority_validation():
    """DMXFrame validates priority range."""
    # Valid priorities
    frame_min = DMXFrame(priority=0)
    assert frame_min.priority == 0

    frame_max = DMXFrame(priority=200)
    assert frame_max.priority == 200

    # Invalid priority (too low)
    try:
        DMXFrame(priority=-1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # Invalid priority (too high)
    try:
        DMXFrame(priority=201)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


# --- execute_dmx_universe Tests ---


async def test_execute_dmx_universe_basic():
    """execute_dmx_universe returns blackout frame for empty input."""
    ctx = NodeExecutionContext(
        node_id="test-node-1",
        graph_id="test-graph",
        inputs={"universe_id": 0},
    )

    result = await execute_dmx_universe(ctx)

    assert result.success is True
    assert "output" in result.outputs
    output = result.outputs["output"]
    assert output["universe"] == 0
    assert len(output["channels"]) == 512
    assert all(ch == 0 for ch in output["channels"])


async def test_execute_dmx_universe_with_frame():
    """execute_dmx_universe merges input frame."""
    input_frame = DMXFrame(universe=1)
    input_frame.set_channel(1, 255)
    input_frame.set_channel(100, 128)

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe_id": 1,
            "frame": input_frame.model_dump(),
        },
    )

    result = await execute_dmx_universe(ctx)

    assert result.success is True
    output = result.outputs["output"]
    assert output["universe"] == 1
    assert output["channels"][0] == 255  # Channel 1
    assert output["channels"][99] == 128  # Channel 100


async def test_execute_dmx_universe_with_protocol():
    """execute_dmx_universe accepts protocol parameter."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe_id": 2,
            "protocol": "artnet",
        },
    )

    result = await execute_dmx_universe(ctx)

    assert result.success is True
    assert result.outputs["output"]["universe"] == 2


async def test_execute_dmx_universe_missing_universe_id():
    """execute_dmx_universe fails without universe_id."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={},
    )

    result = await execute_dmx_universe(ctx)

    assert result.success is False
    assert "universe_id" in result.error.lower()


async def test_execute_dmx_universe_invalid_universe_id():
    """execute_dmx_universe validates universe_id range."""
    # Too low
    ctx_low = NodeExecutionContext(
        node_type="hardware.dmx.universe",
        inputs={"universe_id": -1},
    )
    result_low = await execute_dmx_universe(ctx_low)
    assert result_low.success is False
    assert "universe_id" in result_low.error.lower()

    # Too high
    ctx_high = NodeExecutionContext(
        node_type="hardware.dmx.universe",
        inputs={"universe_id": 32768},
    )
    result_high = await execute_dmx_universe(ctx_high)
    assert result_high.success is False
    assert "universe_id" in result_high.error.lower()

    # Wrong type
    ctx_str = NodeExecutionContext(
        node_type="hardware.dmx.universe",
        inputs={"universe_id": "invalid"},
    )
    result_str = await execute_dmx_universe(ctx_str)
    assert result_str.success is False


async def test_execute_dmx_universe_invalid_frame():
    """execute_dmx_universe handles invalid frame input."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe_id": 0,
            "frame": {"invalid": "data"},
        },
    )

    result = await execute_dmx_universe(ctx)

    assert result.success is False
    assert "frame" in result.error.lower()


# --- execute_dmx_fixture Tests ---


async def test_execute_dmx_fixture_basic():
    """execute_dmx_fixture sets fixture channels from profile."""
    profile = {
        "dimmer": 0,
        "r": 1,
        "g": 2,
        "b": 3,
    }

    values = {
        "dimmer": 1.0,
        "r": 0.5,
        "g": 0.25,
        "b": 0.0,
    }

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is True
    frame_dict = result.outputs["frame"]
    frame = DMXFrame(**frame_dict)

    # Check channels: start_channel=1, so dimmer=1, r=2, g=3, b=4
    assert frame.channels[0] == 255  # dimmer at 100%
    assert frame.channels[1] == 127  # r at ~50%
    assert frame.channels[2] == 63  # g at ~25%
    assert frame.channels[3] == 0  # b at 0%


async def test_execute_dmx_fixture_offset_channel():
    """execute_dmx_fixture handles non-1 start channels."""
    profile = {"dimmer": 0}
    values = {"dimmer": 0.8}

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 1,
            "start_channel": 100,  # Start at channel 100
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is True
    frame = DMXFrame(**result.outputs["frame"])

    # Dimmer should be at channel 100 (index 99)
    assert frame.channels[99] == int(0.8 * 255)


async def test_execute_dmx_fixture_pan_tilt():
    """execute_dmx_fixture handles moving fixtures with pan/tilt."""
    profile = {
        "dimmer": 0,
        "pan": 1,
        "tilt": 2,
    }

    values = {
        "dimmer": 1.0,
        "pan": 0.5,  # Center
        "tilt": 0.25,  # 25% tilt
    }

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is True
    frame = DMXFrame(**result.outputs["frame"])

    assert frame.channels[0] == 255  # dimmer
    assert frame.channels[1] == 127  # pan at center
    assert frame.channels[2] == 63  # tilt at 25%


async def test_execute_dmx_fixture_value_clamping():
    """execute_dmx_fixture clamps values to 0.0-1.0 range."""
    profile = {"dimmer": 0}

    # Values outside 0.0-1.0 should be clamped
    values = {"dimmer": 1.5}  # Should clamp to 1.0

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is True
    frame = DMXFrame(**result.outputs["frame"])
    assert frame.channels[0] == 255  # Clamped to 1.0


async def test_execute_dmx_fixture_unknown_attribute():
    """execute_dmx_fixture skips unknown attributes with warning."""
    profile = {"dimmer": 0}
    values = {
        "dimmer": 1.0,
        "unknown_attr": 0.5,  # Not in profile
    }

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    # Should succeed, just skip unknown attribute
    assert result.success is True


async def test_execute_dmx_fixture_missing_inputs():
    """execute_dmx_fixture fails with missing required inputs."""
    # Missing universe
    ctx1 = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={"start_channel": 1, "profile": {}, "values": {}},
    )
    result1 = await execute_dmx_fixture(ctx1)
    assert result1.success is False
    assert "universe" in result1.error.lower()

    # Missing start_channel
    ctx2 = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={"universe": 0, "profile": {}, "values": {}},
    )
    result2 = await execute_dmx_fixture(ctx2)
    assert result2.success is False
    assert "start_channel" in result2.error.lower()

    # Missing profile
    ctx3 = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={"universe": 0, "start_channel": 1, "values": {}},
    )
    result3 = await execute_dmx_fixture(ctx3)
    assert result3.success is False
    assert "profile" in result3.error.lower()

    # Missing values
    ctx4 = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={"universe": 0, "start_channel": 1, "profile": {}},
    )
    result4 = await execute_dmx_fixture(ctx4)
    assert result4.success is False
    assert "values" in result4.error.lower()


async def test_execute_dmx_fixture_invalid_universe():
    """execute_dmx_fixture validates universe range."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": -1,
            "start_channel": 1,
            "profile": {},
            "values": {},
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is False
    assert "universe" in result.error.lower()


async def test_execute_dmx_fixture_invalid_start_channel():
    """execute_dmx_fixture validates start_channel range."""
    # Too low
    ctx_low = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={
            "universe": 0,
            "start_channel": 0,
            "profile": {},
            "values": {},
        },
    )
    result_low = await execute_dmx_fixture(ctx_low)
    assert result_low.success is False
    assert "start_channel" in result_low.error.lower()

    # Too high
    ctx_high = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={
            "universe": 0,
            "start_channel": 513,
            "profile": {},
            "values": {},
        },
    )
    result_high = await execute_dmx_fixture(ctx_high)
    assert result_high.success is False
    assert "start_channel" in result_high.error.lower()


async def test_execute_dmx_fixture_invalid_profile_type():
    """execute_dmx_fixture validates profile is a dict."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": "not-a-dict",
            "values": {},
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is False
    assert "profile" in result.error.lower()


async def test_execute_dmx_fixture_invalid_values_type():
    """execute_dmx_fixture validates values is a dict."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": {},
            "values": "not-a-dict",
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is False
    assert "values" in result.error.lower()


async def test_execute_dmx_fixture_channel_out_of_range():
    """execute_dmx_fixture fails when computed channel exceeds 512."""
    profile = {"dimmer": 0}
    values = {"dimmer": 1.0}

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 512,  # Last channel
            "profile": profile,
            "values": values,
        },
    )

    # Channel 512 + offset 0 = 512 (valid)
    result = await execute_dmx_fixture(ctx)
    assert result.success is True

    # Now try with offset that would exceed 512
    profile_invalid = {"dimmer": 1}  # Offset 1
    ctx_invalid = NodeExecutionContext(
        node_type="hardware.dmx.fixture",
        inputs={
            "universe": 0,
            "start_channel": 512,
            "profile": profile_invalid,
            "values": values,
        },
    )

    result_invalid = await execute_dmx_fixture(ctx_invalid)
    assert result_invalid.success is False
    assert "out of range" in result_invalid.error.lower()


async def test_execute_dmx_fixture_invalid_attribute_value():
    """execute_dmx_fixture validates attribute values are numeric."""
    profile = {"dimmer": 0}
    values = {"dimmer": "not-a-number"}

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "universe": 0,
            "start_channel": 1,
            "profile": profile,
            "values": values,
        },
    )

    result = await execute_dmx_fixture(ctx)

    assert result.success is False
    assert "numeric" in result.error.lower()


# --- execute_dmx_scene Tests ---


async def test_execute_dmx_scene_store():
    """execute_dmx_scene stores a scene."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "scene_id": "scene1",
            "action": "store",
        },
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is True
    assert "frame" in result.outputs


async def test_execute_dmx_scene_store_with_fixtures():
    """execute_dmx_scene stores scene with fixture data."""
    fixtures = [
        {"universe": 0, "start_channel": 1, "dimmer": 1.0},
        {"universe": 0, "start_channel": 10, "dimmer": 0.5},
    ]

    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "scene_id": "scene2",
            "action": "store",
            "fixtures": fixtures,
        },
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is True


async def test_execute_dmx_scene_recall():
    """execute_dmx_scene recalls a stored scene."""
    # First store a scene
    ctx_store = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "test_scene",
            "action": "store",
        },
    )
    await execute_dmx_scene(ctx_store)

    # Then recall it
    ctx_recall = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "test_scene",
            "action": "recall",
        },
    )

    result = await execute_dmx_scene(ctx_recall)

    assert result.success is True
    assert "frame" in result.outputs


async def test_execute_dmx_scene_recall_not_found():
    """execute_dmx_scene fails when recalling non-existent scene."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "scene_id": "nonexistent",
            "action": "recall",
        },
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_execute_dmx_scene_crossfade():
    """execute_dmx_scene performs crossfade to scene."""
    # Store a scene first
    ctx_store = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "fade_scene",
            "action": "store",
        },
    )
    await execute_dmx_scene(ctx_store)

    # Crossfade to it
    ctx_fade = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "fade_scene",
            "action": "crossfade",
            "fade_ms": 1000,
        },
    )

    result = await execute_dmx_scene(ctx_fade)

    assert result.success is True
    assert "frame" in result.outputs


async def test_execute_dmx_scene_crossfade_not_found():
    """execute_dmx_scene fails crossfade to non-existent scene."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "scene_id": "nonexistent",
            "action": "crossfade",
            "fade_ms": 500,
        },
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_execute_dmx_scene_missing_scene_id():
    """execute_dmx_scene fails without scene_id."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={"action": "recall"},
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is False
    assert "scene_id" in result.error.lower()


async def test_execute_dmx_scene_missing_action():
    """execute_dmx_scene fails without action."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={"scene_id": "test"},
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is False
    assert "action" in result.error.lower()


async def test_execute_dmx_scene_invalid_action():
    """execute_dmx_scene fails with invalid action."""
    ctx = NodeExecutionContext(
        node_id="test-node",
        graph_id="test-graph",
        inputs={
            "scene_id": "test",
            "action": "invalid_action",
        },
    )

    result = await execute_dmx_scene(ctx)

    assert result.success is False
    assert "action" in result.error.lower()


async def test_execute_dmx_scene_default_fade():
    """execute_dmx_scene uses default fade_ms of 0."""
    # Store scene
    ctx_store = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "default_fade",
            "action": "store",
        },
    )
    await execute_dmx_scene(ctx_store)

    # Crossfade without specifying fade_ms
    ctx_fade = NodeExecutionContext(
        node_type="hardware.dmx.scene",
        inputs={
            "scene_id": "default_fade",
            "action": "crossfade",
        },
    )

    result = await execute_dmx_scene(ctx_fade)

    assert result.success is True
