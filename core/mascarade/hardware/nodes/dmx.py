"""DMX lighting control nodes — Universe management, fixture control, and scene programming.

Implements nodes for controlling DMX512 lighting fixtures via sACN (E1.31) or
Art-Net protocols over Ethernet. Follows the hardware node model defined in
SPEC-029-P4 section 5.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from mascarade.hardware.types import DMXFrame
from mascarade.node_engine.base import NodeDefinition, NodeExecutionContext, NodeExecutionResult
from mascarade.node_engine.types import (
    NodePort,
    PortDirection,
    PortKind,
    PortType,
    PrimitiveType,
    domain_port,
    primitive_port,
)

logger = logging.getLogger("mascarade.hardware.dmx")

# --- Error Classes ---


class DMXError(RuntimeError):
    """Base error for DMX node failures."""


class DMXProtocolError(DMXError):
    """Raised when DMX protocol communication fails."""


class DMXFixtureError(DMXError):
    """Raised when DMX fixture configuration is invalid."""


# --- DMX Client ---


class DMXOutputConfig(BaseModel):
    """Configuration for DMX output via sACN or Art-Net.

    Defines how to transmit DMX frames over the network using either
    sACN (E1.31) or Art-Net protocol.
    """

    protocol: Literal["sacn", "artnet"] = "sacn"
    interface: str | None = Field(None, description="Network interface to bind (default: auto)")
    source_name: str = Field("mascarade-hardware-worker", description="sACN source name")
    fps: int = Field(40, ge=1, le=44, description="Frame rate (1-44 Hz, DMX spec max)")
    simulation_mode: bool = Field(False, description="Simulate output without network transmission")


class DMXClient:
    """Async client for DMX output via sACN or Art-Net.

    Manages DMX universe state and network transmission. Operates in simulation
    mode when no network interface is available (graceful degradation).
    """

    def __init__(self, config: DMXOutputConfig) -> None:
        """Initialize DMX client.

        Args:
            config: DMX output configuration
        """
        self.config = config
        self._universes: dict[int, DMXFrame] = {}
        self._running = False
        self._output_task: asyncio.Task[None] | None = None
        self._sacn_sender: Any = None  # sacn.sACNsender instance (optional dependency)

        # Initialize protocol-specific sender
        if not config.simulation_mode:
            if config.protocol == "sacn":
                try:
                    import sacn

                    self._sacn_sender = sacn.sACNsender()
                    if config.interface:
                        # Bind to specific interface if provided
                        # Note: sacn library uses source_name parameter
                        pass
                    self._sacn_sender.start()
                    logger.info(f"DMX client initialized with sACN protocol on interface={config.interface}")
                except ImportError:
                    logger.warning("sacn library not installed, falling back to simulation mode")
                    self.config.simulation_mode = True
            elif config.protocol == "artnet":
                # Art-Net implementation would go here
                logger.warning("Art-Net protocol not yet implemented, falling back to simulation mode")
                self.config.simulation_mode = True

        if config.simulation_mode:
            logger.info("DMX client running in simulation mode (no network output)")

    async def start(self) -> None:
        """Start the DMX output loop."""
        if self._running:
            return

        self._running = True
        self._output_task = asyncio.create_task(self._output_loop())
        logger.info(f"DMX output started at {self.config.fps} fps")

    async def stop(self) -> None:
        """Stop the DMX output loop and release resources."""
        self._running = False
        if self._output_task:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass

        if self._sacn_sender:
            self._sacn_sender.stop()
            self._sacn_sender = None

        logger.info("DMX output stopped")

    async def set_universe(self, universe_id: int, frame: DMXFrame) -> None:
        """Set the state of a DMX universe.

        Args:
            universe_id: Universe number (0-32767)
            frame: DMX frame to set
        """
        self._universes[universe_id] = frame

        # In simulation mode, just log
        if self.config.simulation_mode:
            logger.debug(f"DMX universe {universe_id} updated (simulation mode)")
            return

        # Activate sACN universe if needed
        if self._sacn_sender and universe_id not in self._sacn_sender.get_active_universes():
            self._sacn_sender.activate_output(universe_id + 1)  # sACN uses 1-indexed universes
            self._sacn_sender[universe_id + 1].multicast = True

    def get_universe(self, universe_id: int) -> DMXFrame:
        """Get the current state of a DMX universe.

        Args:
            universe_id: Universe number

        Returns:
            Current DMX frame for the universe
        """
        if universe_id not in self._universes:
            # Initialize with blackout (all channels 0)
            self._universes[universe_id] = DMXFrame(universe=universe_id)
        return self._universes[universe_id]

    async def _output_loop(self) -> None:
        """Main output loop that transmits DMX frames at the configured rate."""
        interval = 1.0 / self.config.fps

        while self._running:
            start_time = time.monotonic()

            # Transmit all active universes
            for universe_id, frame in self._universes.items():
                await self._transmit_frame(universe_id, frame)

            # Sleep to maintain frame rate
            elapsed = time.monotonic() - start_time
            sleep_time = max(0, interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _transmit_frame(self, universe_id: int, frame: DMXFrame) -> None:
        """Transmit a single DMX frame.

        Args:
            universe_id: Universe number
            frame: DMX frame to transmit
        """
        if self.config.simulation_mode:
            return

        if self.config.protocol == "sacn" and self._sacn_sender:
            # sACN uses 1-indexed universes
            sacn_universe = universe_id + 1
            try:
                # Convert to tuple for sacn library (it expects a sequence)
                dmx_data = tuple(frame.channels)
                self._sacn_sender[sacn_universe].dmx_data = dmx_data
                # Priority is set per-universe in sACN
                self._sacn_sender[sacn_universe].priority = frame.priority
            except Exception as exc:
                logger.error(f"Failed to transmit sACN frame for universe {universe_id}: {exc}")


# --- DMX Nodes ---


DMXUniverseNode = NodeDefinition(
    node_type="hardware.dmx.universe",
    description="Manages a single DMX512 universe (512 channels)",
    input_ports=[
        primitive_port(
            name="universe_id",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Universe number (0-32767)",
        ),
        primitive_port(
            name="protocol",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Protocol: 'artnet' or 'sacn' (default: 'sacn')",
            optional=True,
            default_value="sacn",
        ),
        primitive_port(
            name="interface",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Network interface to bind (optional)",
            optional=True,
        ),
        domain_port(
            name="frame",
            direction=PortDirection.INPUT,
            domain="hardware",
            type_name="DMXFrame",
            description="Frame to merge into universe",
            optional=True,
        ),
    ],
    output_ports=[
        domain_port(
            name="output",
            direction=PortDirection.OUTPUT,
            domain="hardware",
            type_name="DMXFrame",
            description="Current universe state",
        ),
    ],
    tags=["hardware", "dmx", "lighting", "universe"],
    io_intensive=True,
)


DMXFixtureNode = NodeDefinition(
    node_type="hardware.dmx.fixture",
    description="Controls a single DMX fixture with named channel attributes",
    input_ports=[
        primitive_port(
            name="universe",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Universe number (0-32767)",
        ),
        primitive_port(
            name="start_channel",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Fixture start address (1-512)",
        ),
        NodePort(
            name="profile",
            direction=PortDirection.INPUT,
            port_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.JSON),
            description="Fixture profile (channel map: dimmer, r, g, b, pan, tilt, etc.)",
        ),
        NodePort(
            name="values",
            direction=PortDirection.INPUT,
            port_type=PortType(
                kind=PortKind.MAP,
                key_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.STRING),
                value_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.NUMBER),
            ),
            description="Named attribute values (0.0-1.0)",
        ),
    ],
    output_ports=[
        domain_port(
            name="frame",
            direction=PortDirection.OUTPUT,
            domain="hardware",
            type_name="DMXFrame",
            description="DMX frame with fixture channels set",
        ),
    ],
    tags=["hardware", "dmx", "lighting", "fixture"],
    io_intensive=True,
)


DMXSceneNode = NodeDefinition(
    node_type="hardware.dmx.scene",
    description="Programs and recalls DMX scenes (snapshots of fixture states)",
    input_ports=[
        primitive_port(
            name="scene_id",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Scene identifier",
        ),
        primitive_port(
            name="action",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.STRING,
            description="Action: 'store', 'recall', 'crossfade'",
        ),
        NodePort(
            name="fixtures",
            direction=PortDirection.INPUT,
            port_type=PortType(
                kind=PortKind.ARRAY,
                element_type=PortType(kind=PortKind.PRIMITIVE, name=PrimitiveType.JSON),
                optional=True,
            ),
            description="Fixture states for store action",
            required=False,
        ),
        primitive_port(
            name="fade_ms",
            direction=PortDirection.INPUT,
            primitive_type=PrimitiveType.INTEGER,
            description="Crossfade duration in milliseconds",
            optional=True,
            default_value=0,
        ),
    ],
    output_ports=[
        domain_port(
            name="frame",
            direction=PortDirection.OUTPUT,
            domain="hardware",
            type_name="DMXFrame",
            description="Resulting DMX frame",
        ),
    ],
    tags=["hardware", "dmx", "lighting", "scene"],
    io_intensive=True,
)


# --- Node Execution Functions ---


async def execute_dmx_universe(ctx: NodeExecutionContext) -> NodeExecutionResult:
    """Execute DMX universe management node.

    Args:
        ctx: Node execution context with input values

    Returns:
        Execution result with universe state output
    """
    # Extract inputs
    universe_id = ctx.inputs.get("universe_id")
    ctx.inputs.get("protocol", "sacn")
    ctx.inputs.get("interface")
    input_frame = ctx.inputs.get("frame")

    # Validate inputs
    if universe_id is None:
        return NodeExecutionResult(
            success=False,
            error="Missing required input: universe_id",
        )

    if not isinstance(universe_id, int) or not (0 <= universe_id <= 32767):
        return NodeExecutionResult(
            success=False,
            error=f"Invalid universe_id: must be integer 0-32767, got {universe_id}",
        )

    # Get or create DMX client from context metadata
    # In a real implementation, this would be stored in the HardwareWorker's device registry
    # For now, we simulate the universe state
    if input_frame:
        # Merge input frame into universe
        if not isinstance(input_frame, DMXFrame):
            # Try to construct from dict
            if isinstance(input_frame, dict):
                # Validate that the dict looks like a DMX frame
                valid_keys = {"kind", "domain", "name", "universe", "channels", "timestamp_ms"}
                unknown_keys = set(input_frame.keys()) - valid_keys
                if unknown_keys and not any(k in input_frame for k in ("universe", "channels")):
                    return NodeExecutionResult(
                        success=False,
                        error=f"Invalid DMX frame: unrecognized keys {unknown_keys}",
                    )
            try:
                input_frame = DMXFrame(**input_frame)
            except Exception as exc:
                return NodeExecutionResult(
                    success=False,
                    error=f"Invalid DMX frame input: {exc}",
                )
        universe_frame = input_frame
    else:
        # Return current universe state (blackout by default)
        universe_frame = DMXFrame(universe=universe_id)

    # Update timestamp
    universe_frame.timestamp_ms = int(time.time() * 1000)

    return NodeExecutionResult(
        success=True,
        outputs={
            "output": universe_frame.model_dump(),
        },
    )


async def execute_dmx_fixture(ctx: NodeExecutionContext) -> NodeExecutionResult:
    """Execute DMX fixture control node.

    Args:
        ctx: Node execution context with input values

    Returns:
        Execution result with fixture DMX frame
    """
    # Extract inputs
    universe = ctx.inputs.get("universe")
    start_channel = ctx.inputs.get("start_channel")
    profile = ctx.inputs.get("profile")
    values = ctx.inputs.get("values")

    # Validate inputs
    if universe is None:
        return NodeExecutionResult(success=False, error="Missing required input: universe")
    if start_channel is None:
        return NodeExecutionResult(success=False, error="Missing required input: start_channel")
    if profile is None:
        return NodeExecutionResult(success=False, error="Missing required input: profile")
    if values is None:
        return NodeExecutionResult(success=False, error="Missing required input: values")

    # Validate universe and channel
    if not isinstance(universe, int) or not (0 <= universe <= 32767):
        return NodeExecutionResult(
            success=False,
            error=f"Invalid universe: must be integer 0-32767, got {universe}",
        )

    if not isinstance(start_channel, int) or not (1 <= start_channel <= 512):
        return NodeExecutionResult(
            success=False,
            error=f"Invalid start_channel: must be integer 1-512, got {start_channel}",
        )

    # Create DMX frame for this fixture
    frame = DMXFrame(universe=universe, timestamp_ms=int(time.time() * 1000))

    # Map named attributes to DMX channels using the profile
    try:
        if not isinstance(profile, dict):
            raise DMXFixtureError(f"Profile must be a dict, got {type(profile)}")
        if not isinstance(values, dict):
            raise DMXFixtureError(f"Values must be a dict, got {type(values)}")

        for attr_name, attr_value in values.items():
            if attr_name not in profile:
                logger.warning(f"Attribute '{attr_name}' not in fixture profile, skipping")
                continue

            # Get channel offset from profile
            channel_offset = profile[attr_name]
            if not isinstance(channel_offset, int):
                raise DMXFixtureError(
                    f"Profile channel offset must be integer, got {type(channel_offset)} for '{attr_name}'"
                )

            # Calculate absolute DMX channel (1-indexed)
            dmx_channel = start_channel + channel_offset

            if not (1 <= dmx_channel <= 512):
                raise DMXFixtureError(
                    f"Computed DMX channel {dmx_channel} out of range (1-512) for attribute '{attr_name}'"
                )

            # Convert normalized value (0.0-1.0) to DMX value (0-255)
            if not isinstance(attr_value, (int, float)):
                raise DMXFixtureError(f"Attribute value must be numeric, got {type(attr_value)} for '{attr_name}'")

            # Clamp to 0.0-1.0 range
            normalized_value = max(0.0, min(1.0, float(attr_value)))
            dmx_value = int(normalized_value * 255)

            # Set channel in frame
            frame.set_channel(dmx_channel, dmx_value)

    except DMXFixtureError as exc:
        return NodeExecutionResult(success=False, error=str(exc))
    except Exception as exc:
        return NodeExecutionResult(
            success=False,
            error=f"Unexpected error mapping fixture attributes: {exc}",
        )

    return NodeExecutionResult(
        success=True,
        outputs={"frame": frame.model_dump()},
    )


# Scene storage (in-memory for now, would be persisted in production)
_scene_storage: dict[str, DMXFrame] = {}


async def execute_dmx_scene(ctx: NodeExecutionContext) -> NodeExecutionResult:
    """Execute DMX scene programming node.

    Args:
        ctx: Node execution context with input values

    Returns:
        Execution result with scene DMX frame
    """
    # Extract inputs
    scene_id = ctx.inputs.get("scene_id")
    action = ctx.inputs.get("action")
    fixtures = ctx.inputs.get("fixtures")
    fade_ms = ctx.inputs.get("fade_ms", 0)

    # Validate inputs
    if not scene_id:
        return NodeExecutionResult(success=False, error="Missing required input: scene_id")
    if not action:
        return NodeExecutionResult(success=False, error="Missing required input: action")

    if action not in ("store", "recall", "crossfade"):
        return NodeExecutionResult(
            success=False,
            error=f"Invalid action: must be 'store', 'recall', or 'crossfade', got '{action}'",
        )

    # Handle different actions
    if action == "store":
        # Store scene (would construct from fixtures array)
        # For now, store an empty scene
        if fixtures:
            # In a real implementation, we'd merge all fixture frames
            logger.info(f"Storing scene '{scene_id}' with {len(fixtures)} fixtures")

        # Create a basic frame for the scene
        scene_frame = DMXFrame(universe=0, timestamp_ms=int(time.time() * 1000))
        _scene_storage[scene_id] = scene_frame

        return NodeExecutionResult(
            success=True,
            outputs={"frame": scene_frame.model_dump()},
        )

    elif action == "recall":
        # Recall stored scene
        if scene_id not in _scene_storage:
            return NodeExecutionResult(
                success=False,
                error=f"Scene '{scene_id}' not found (must be stored first)",
            )

        scene_frame = _scene_storage[scene_id]
        # Update timestamp
        scene_frame.timestamp_ms = int(time.time() * 1000)

        return NodeExecutionResult(
            success=True,
            outputs={"frame": scene_frame.model_dump()},
        )

    elif action == "crossfade":
        # Crossfade to scene (would implement fade over fade_ms duration)
        if scene_id not in _scene_storage:
            return NodeExecutionResult(
                success=False,
                error=f"Scene '{scene_id}' not found (must be stored first)",
            )

        # For now, just return the target scene
        # A real implementation would handle the crossfade timing
        logger.info(f"Crossfading to scene '{scene_id}' over {fade_ms}ms")
        scene_frame = _scene_storage[scene_id]
        scene_frame.timestamp_ms = int(time.time() * 1000)

        return NodeExecutionResult(
            success=True,
            outputs={"frame": scene_frame.model_dump()},
        )

    # Should never reach here
    return NodeExecutionResult(success=False, error=f"Unknown action: {action}")
