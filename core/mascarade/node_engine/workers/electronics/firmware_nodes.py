"""Firmware compilation nodes for electronics domain."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mascarade.node_engine.types import PortDirection, PortType

logger = logging.getLogger("mascarade.node_engine.workers.electronics.firmware_nodes")


@dataclass
class NodeConfig:
    """Base configuration for node execution parameters."""

    pass


@dataclass
class CompileConfig(NodeConfig):
    """Configuration for firmware compilation node."""

    timeout_seconds: int = 300
    idf_path: str = ""
    clean_build: bool = False


@dataclass
class FlashPrepareConfig(NodeConfig):
    """Configuration for flash preparation node."""

    pass


@dataclass
class SizeAnalysisConfig(NodeConfig):
    """Configuration for size analysis node."""

    pass


class BaseNode:
    """Base class for all executable nodes.

    Nodes are the fundamental execution units in the Universal Node Engine.
    Each node has input/output ports and an execute method.
    """

    node_type: str = ""
    description: str = ""

    def __init__(self, config: NodeConfig | None = None) -> None:
        """Initialize the node with optional configuration.

        Args:
            config: Node-specific configuration parameters
        """
        self.config = config or self._default_config()
        self._input_ports: list[PortType] = self._define_input_ports()
        self._output_ports: list[PortType] = self._define_output_ports()

    def _default_config(self) -> NodeConfig:
        """Return default configuration for this node type.

        Should be overridden by subclasses.
        """
        return NodeConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for this node.

        Should be overridden by subclasses.
        """
        return []

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for this node.

        Should be overridden by subclasses.
        """
        return []

    @property
    def input_ports(self) -> list[PortType]:
        """Get list of input ports."""
        return self._input_ports

    @property
    def output_ports(self) -> list[PortType]:
        """Get list of output ports."""
        return self._output_ports

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the node with given inputs.

        Args:
            inputs: Dictionary mapping input port names to values

        Returns:
            Dictionary mapping output port names to values

        Raises:
            ValueError: If required inputs are missing or invalid
        """
        raise NotImplementedError("Subclasses must implement execute()")


class CompileNode(BaseNode):
    """Compiles firmware from source using ESP-IDF or PlatformIO.

    Integrates with ESP-IDF or PlatformIO build systems to compile embedded
    firmware. Supports ESP32 family targets and extracts binary artifacts.

    Input Ports:
        source_path (string): Path to firmware project directory
        target (string): Build target (e.g., "esp32", "esp32s3", "esp32c3")
        framework (optional<string>): "esp-idf" (default) or "platformio"
        build_flags (optional<array<string>>): Additional build flags

    Output Ports:
        firmware (electronics.FirmwareBinary): Compiled firmware binary
        build_log (string): Full build output
        success (boolean): Whether build succeeded

    Configuration:
        timeout_seconds (integer): Maximum build time (default: 300)
        idf_path (string): ESP-IDF installation path (auto-detect if empty)
        clean_build (boolean): Force clean build (default: false)
    """

    node_type = "electronics.firmware.compile"
    description = "Compiles firmware from source using ESP-IDF or PlatformIO"

    def _default_config(self) -> CompileConfig:
        """Return default configuration for compilation."""
        return CompileConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for compilation."""
        return [
            PortType(
                name="source_path",
                direction=PortDirection.INPUT,
                port_type="string",
                description="Path to firmware project directory",
                optional=False,
            ),
            PortType(
                name="target",
                direction=PortDirection.INPUT,
                port_type="string",
                description='Build target (e.g., "esp32", "esp32s3", "esp32c3")',
                optional=False,
            ),
            PortType(
                name="framework",
                direction=PortDirection.INPUT,
                port_type="string",
                description='"esp-idf" (default) or "platformio"',
                optional=True,
                default_value="esp-idf",
            ),
            PortType(
                name="build_flags",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Additional build flags",
                optional=True,
                default_value=[],
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for compilation."""
        return [
            PortType(
                name="firmware",
                direction=PortDirection.OUTPUT,
                port_type="electronics.FirmwareBinary",
                description="Compiled firmware binary",
            ),
            PortType(
                name="build_log",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Full build output",
            ),
            PortType(
                name="success",
                direction=PortDirection.OUTPUT,
                port_type="boolean",
                description="Whether build succeeded",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute firmware compilation.

        Args:
            inputs: Dictionary with source_path, target, framework (optional), build_flags (optional)

        Returns:
            Dictionary with firmware (FirmwareBinary), build_log (string), success (boolean)

        Raises:
            ValueError: If source_path or target is missing
            RuntimeError: If build tools are not available
        """
        # Validate required inputs
        source_path = inputs.get("source_path")
        target = inputs.get("target")

        if not source_path:
            raise ValueError("source_path is required and cannot be empty")
        if not target:
            raise ValueError("target is required and cannot be empty")

        # Get optional inputs
        framework = inputs.get("framework", "esp-idf")
        build_flags = inputs.get("build_flags", [])

        # Get configuration
        config = self.config
        if not isinstance(config, CompileConfig):
            config = CompileConfig()

        # Validate source path exists
        source_path_obj = Path(source_path)
        if not source_path_obj.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        if not source_path_obj.is_dir():
            raise ValueError(f"Source path is not a directory: {source_path}")

        logger.info(
            f"Compiling firmware: target={target}, framework={framework}, source={source_path}"
        )

        # Compile based on framework
        if framework == "esp-idf":
            return await self._compile_esp_idf(
                source_path_obj, target, build_flags, config
            )
        elif framework == "platformio":
            return await self._compile_platformio(
                source_path_obj, target, build_flags, config
            )
        else:
            raise ValueError(
                f"Unsupported framework: {framework}. Must be 'esp-idf' or 'platformio'"
            )

    async def _compile_esp_idf(
        self,
        source_path: Path,
        target: str,
        build_flags: list[str],
        config: CompileConfig,
    ) -> dict[str, Any]:
        """Compile firmware using ESP-IDF.

        Args:
            source_path: Path to project directory
            target: Build target (e.g., esp32, esp32s3)
            build_flags: Additional build flags
            config: Compilation configuration

        Returns:
            Dictionary with firmware, build_log, success
        """
        # Check if idf.py is available
        idf_path = config.idf_path
        if idf_path:
            idf_py = Path(idf_path) / "tools" / "idf.py"
            if not idf_py.exists():
                raise RuntimeError(
                    f"ESP-IDF not found at {idf_path}. "
                    "Please install ESP-IDF or set correct idf_path."
                )
        else:
            # Try to find idf.py in PATH
            try:
                check_proc = await asyncio.create_subprocess_exec(
                    "idf.py",
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await check_proc.communicate()
                if check_proc.returncode != 0:
                    raise RuntimeError(
                        "idf.py not available. "
                        "Please install ESP-IDF and source export.sh."
                    )
                idf_py = "idf.py"
            except FileNotFoundError:
                raise RuntimeError(
                    "idf.py not found. "
                    "Please install ESP-IDF and source export.sh."
                )

        build_log_lines = []

        try:
            # Set target
            logger.info(f"Setting ESP-IDF target to {target}")
            set_target_proc = await asyncio.create_subprocess_exec(
                str(idf_py),
                "set-target",
                target,
                cwd=str(source_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _ = await asyncio.wait_for(
                set_target_proc.communicate(),
                timeout=config.timeout_seconds,
            )
            build_log_lines.append(f"=== Set Target {target} ===\n")
            build_log_lines.append(stdout.decode())

            if set_target_proc.returncode != 0:
                build_log = "\n".join(build_log_lines)
                logger.error(f"Failed to set target: {target}")
                return {
                    "firmware": None,
                    "build_log": build_log,
                    "success": False,
                }

            # Clean build if requested
            if config.clean_build:
                logger.info("Performing clean build")
                clean_proc = await asyncio.create_subprocess_exec(
                    str(idf_py),
                    "fullclean",
                    cwd=str(source_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await asyncio.wait_for(
                    clean_proc.communicate(),
                    timeout=60,
                )
                build_log_lines.append("\n=== Clean Build ===\n")
                build_log_lines.append(stdout.decode())

            # Build
            logger.info("Building firmware")
            build_cmd = [str(idf_py), "build"]
            build_cmd.extend(build_flags)

            build_proc = await asyncio.create_subprocess_exec(
                *build_cmd,
                cwd=str(source_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _ = await asyncio.wait_for(
                build_proc.communicate(),
                timeout=config.timeout_seconds,
            )
            build_log_lines.append("\n=== Build ===\n")
            build_log_lines.append(stdout.decode())
            build_log = "\n".join(build_log_lines)

            if build_proc.returncode != 0:
                logger.error("Build failed")
                return {
                    "firmware": None,
                    "build_log": build_log,
                    "success": False,
                }

            # Extract binary
            build_dir = source_path / "build"
            binary_path = build_dir / f"{source_path.name}.bin"

            # Try common binary names if project name binary not found
            if not binary_path.exists():
                for candidate in build_dir.glob("*.bin"):
                    binary_path = candidate
                    break

            if not binary_path.exists():
                logger.error(f"Binary not found in {build_dir}")
                return {
                    "firmware": None,
                    "build_log": build_log + f"\n\nError: Binary not found in {build_dir}",
                    "success": False,
                }

            # Read binary
            binary_data = binary_path.read_bytes()
            binary_base64 = base64.b64encode(binary_data).decode()

            # Parse size information from build log
            sections = self._parse_size_esp_idf(build_log)

            firmware = {
                "binary": binary_base64,
                "target": target,
                "framework": "esp-idf",
                "size_bytes": len(binary_data),
                "sections": sections,
            }

            logger.info(f"Build succeeded: {len(binary_data)} bytes")
            return {
                "firmware": firmware,
                "build_log": build_log,
                "success": True,
            }

        except TimeoutError:
            build_log = "\n".join(build_log_lines) + "\n\nError: Build timeout"
            logger.error(f"Build timeout after {config.timeout_seconds} seconds")
            return {
                "firmware": None,
                "build_log": build_log,
                "success": False,
            }
        except Exception as e:
            build_log = "\n".join(build_log_lines) + f"\n\nError: {e}"
            logger.error(f"Build failed with exception: {e}")
            return {
                "firmware": None,
                "build_log": build_log,
                "success": False,
            }

    async def _compile_platformio(
        self,
        source_path: Path,
        target: str,
        build_flags: list[str],
        config: CompileConfig,
    ) -> dict[str, Any]:
        """Compile firmware using PlatformIO.

        Args:
            source_path: Path to project directory
            target: Build target (PlatformIO environment name)
            build_flags: Additional build flags
            config: Compilation configuration

        Returns:
            Dictionary with firmware, build_log, success
        """
        # Check if pio is available
        try:
            check_proc = await asyncio.create_subprocess_exec(
                "pio",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await check_proc.communicate()
            if check_proc.returncode != 0:
                raise RuntimeError(
                    "PlatformIO not available. "
                    "Please install PlatformIO: pip install platformio"
                )
        except FileNotFoundError:
            raise RuntimeError(
                "PlatformIO not found. "
                "Please install PlatformIO: pip install platformio"
            )

        build_log_lines = []

        try:
            # Clean build if requested
            if config.clean_build:
                logger.info("Performing clean build")
                clean_proc = await asyncio.create_subprocess_exec(
                    "pio",
                    "run",
                    "-e",
                    target,
                    "-t",
                    "clean",
                    cwd=str(source_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await asyncio.wait_for(
                    clean_proc.communicate(),
                    timeout=60,
                )
                build_log_lines.append("=== Clean Build ===\n")
                build_log_lines.append(stdout.decode())

            # Build
            logger.info(f"Building firmware with PlatformIO: environment={target}")
            build_cmd = ["pio", "run", "-e", target]
            build_cmd.extend(build_flags)

            build_proc = await asyncio.create_subprocess_exec(
                *build_cmd,
                cwd=str(source_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout, _ = await asyncio.wait_for(
                build_proc.communicate(),
                timeout=config.timeout_seconds,
            )
            build_log_lines.append("=== Build ===\n")
            build_log_lines.append(stdout.decode())
            build_log = "\n".join(build_log_lines)

            if build_proc.returncode != 0:
                logger.error("Build failed")
                return {
                    "firmware": None,
                    "build_log": build_log,
                    "success": False,
                }

            # Extract binary
            build_dir = source_path / ".pio" / "build" / target
            binary_path = build_dir / "firmware.bin"

            if not binary_path.exists():
                logger.error(f"Binary not found at {binary_path}")
                return {
                    "firmware": None,
                    "build_log": build_log + f"\n\nError: Binary not found at {binary_path}",
                    "success": False,
                }

            # Read binary
            binary_data = binary_path.read_bytes()
            binary_base64 = base64.b64encode(binary_data).decode()

            # Parse size information from build log
            sections = self._parse_size_platformio(build_log)

            firmware = {
                "binary": binary_base64,
                "target": target,
                "framework": "platformio",
                "size_bytes": len(binary_data),
                "sections": sections,
            }

            logger.info(f"Build succeeded: {len(binary_data)} bytes")
            return {
                "firmware": firmware,
                "build_log": build_log,
                "success": True,
            }

        except TimeoutError:
            build_log = "\n".join(build_log_lines) + "\n\nError: Build timeout"
            logger.error(f"Build timeout after {config.timeout_seconds} seconds")
            return {
                "firmware": None,
                "build_log": build_log,
                "success": False,
            }
        except Exception as e:
            build_log = "\n".join(build_log_lines) + f"\n\nError: {e}"
            logger.error(f"Build failed with exception: {e}")
            return {
                "firmware": None,
                "build_log": build_log,
                "success": False,
            }

    def _parse_size_esp_idf(self, build_log: str) -> dict[str, int]:
        """Parse section sizes from ESP-IDF build log.

        Args:
            build_log: Full build output

        Returns:
            Dictionary mapping section names to sizes in bytes
        """
        sections = {}

        # ESP-IDF outputs size info like:
        # Total sizes:
        # Used static DRAM:   12345 bytes (  67890 remain, 15.3% used)
        # Used static IRAM:   23456 bytes (  78901 remain, 22.9% used)
        # Flash code:        123456 bytes
        # Flash rodata:       34567 bytes

        patterns = {
            "dram": r"Used static DRAM:\s+(\d+)\s+bytes",
            "iram": r"Used static IRAM:\s+(\d+)\s+bytes",
            "flash_code": r"Flash code:\s+(\d+)\s+bytes",
            "flash_rodata": r"Flash rodata:\s+(\d+)\s+bytes",
        }

        for section, pattern in patterns.items():
            match = re.search(pattern, build_log)
            if match:
                sections[section] = int(match.group(1))

        return sections

    def _parse_size_platformio(self, build_log: str) -> dict[str, int]:
        """Parse section sizes from PlatformIO build log.

        Args:
            build_log: Full build output

        Returns:
            Dictionary mapping section names to sizes in bytes
        """
        sections = {}

        # PlatformIO outputs size info like:
        # RAM:   [====      ]  40.0% (used 12345 bytes from 65536 bytes)
        # Flash: [======    ]  60.0% (used 123456 bytes from 1048576 bytes)

        ram_pattern = r"RAM:.*?used (\d+) bytes"
        flash_pattern = r"Flash:.*?used (\d+) bytes"

        ram_match = re.search(ram_pattern, build_log)
        if ram_match:
            sections["ram"] = int(ram_match.group(1))

        flash_match = re.search(flash_pattern, build_log)
        if flash_match:
            sections["flash"] = int(flash_match.group(1))

        return sections


class FlashPrepareNode(BaseNode):
    """Prepares firmware for flashing to target device.

    Generates flash command with appropriate parameters, handles partition
    tables, and can optionally merge multiple binaries for single-file flashing.

    Input Ports:
        firmware (electronics.FirmwareBinary): Compiled firmware
        flash_config (optional<json>): Flash parameters (baud, port, partition table)

    Output Ports:
        flash_command (string): Ready-to-execute flash command
        merged_binary (optional<binary>): Merged binary for single-file flashing

    Configuration:
        None
    """

    node_type = "electronics.firmware.flash_prepare"
    description = "Prepares firmware for flashing to target device"

    def _default_config(self) -> FlashPrepareConfig:
        """Return default configuration for flash preparation."""
        return FlashPrepareConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for flash preparation."""
        return [
            PortType(
                name="firmware",
                direction=PortDirection.INPUT,
                port_type="electronics.FirmwareBinary",
                description="Compiled firmware",
                optional=False,
            ),
            PortType(
                name="flash_config",
                direction=PortDirection.INPUT,
                port_type="json",
                description="Flash parameters (baud, port, partition table)",
                optional=True,
                default_value=None,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for flash preparation."""
        return [
            PortType(
                name="flash_command",
                direction=PortDirection.OUTPUT,
                port_type="string",
                description="Ready-to-execute flash command",
            ),
            PortType(
                name="merged_binary",
                direction=PortDirection.OUTPUT,
                port_type="binary",
                description="Merged binary for single-file flashing",
                optional=True,
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute flash preparation.

        Args:
            inputs: Dictionary with firmware (required), flash_config (optional)

        Returns:
            Dictionary with flash_command (string), merged_binary (optional)

        Raises:
            ValueError: If firmware is missing or invalid
        """
        # Validate required inputs
        firmware = inputs.get("firmware")
        if not firmware:
            raise ValueError("firmware is required and cannot be empty")

        # Get optional inputs
        flash_config = inputs.get("flash_config", {})

        # Default flash configuration
        default_config = {
            "baud": 460800,
            "port": "/dev/ttyUSB0",
            "flash_mode": "dio",
            "flash_freq": "40m",
            "flash_size": "4MB",
        }

        # Merge with provided config
        config = {**default_config, **flash_config}

        # Extract firmware data
        target = firmware.get("target", "esp32")
        framework = firmware.get("framework", "esp-idf")

        logger.info(
            f"Preparing flash command: target={target}, framework={framework}, "
            f"port={config['port']}, baud={config['baud']}"
        )

        # Generate flash command based on framework
        if framework in ["esp-idf", "platformio"]:
            # ESP32 targets use esptool.py
            flash_command = self._generate_esptool_command(firmware, config)
        else:
            # Generic flash command
            flash_command = f"# Unsupported framework: {framework}\n"
            flash_command += "# Please use appropriate flashing tool for your target"

        # For now, we don't generate merged binary (would require esptool.py merge_bin)
        # This could be added in a future enhancement
        merged_binary = None

        return {
            "flash_command": flash_command,
            "merged_binary": merged_binary,
        }

    def _generate_esptool_command(
        self, firmware: dict[str, Any], config: dict[str, Any]
    ) -> str:
        """Generate esptool.py flash command.

        Args:
            firmware: Firmware binary structure
            config: Flash configuration

        Returns:
            Ready-to-execute flash command string
        """
        target = firmware.get("target", "esp32")

        # Build esptool.py command
        cmd_parts = [
            "esptool.py",
            f"--chip {target}",
            f"--port {config['port']}",
            f"--baud {config['baud']}",
            "write_flash",
            "-z",
            f"--flash_mode {config['flash_mode']}",
            f"--flash_freq {config['flash_freq']}",
            f"--flash_size {config['flash_size']}",
            "0x10000 firmware.bin",
        ]

        flash_command = " ".join(cmd_parts)

        # Add helpful comments
        flash_command = (
            f"# Flash command for {target}\n"
            f"# Save firmware binary to 'firmware.bin' before running\n"
            f"{flash_command}\n"
        )

        return flash_command


class SizeAnalysisNode(BaseNode):
    """Analyzes firmware binary size breakdown for optimization.

    Provides detailed section-by-section size analysis and warnings about
    potential size issues (approaching flash limits, large sections, etc.).

    Input Ports:
        firmware (electronics.FirmwareBinary): Compiled firmware

    Output Ports:
        size_report (json): Section-by-section size analysis
        warnings (array<string>): Size warnings (e.g., approaching flash limit)

    Configuration:
        None
    """

    node_type = "electronics.firmware.size_analysis"
    description = "Analyzes firmware binary size breakdown for optimization"

    def _default_config(self) -> SizeAnalysisConfig:
        """Return default configuration for size analysis."""
        return SizeAnalysisConfig()

    def _define_input_ports(self) -> list[PortType]:
        """Define input ports for size analysis."""
        return [
            PortType(
                name="firmware",
                direction=PortDirection.INPUT,
                port_type="electronics.FirmwareBinary",
                description="Compiled firmware",
                optional=False,
            ),
        ]

    def _define_output_ports(self) -> list[PortType]:
        """Define output ports for size analysis."""
        return [
            PortType(
                name="size_report",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Section-by-section size analysis",
            ),
            PortType(
                name="warnings",
                direction=PortDirection.OUTPUT,
                port_type="json",
                description="Size warnings (e.g., approaching flash limit)",
            ),
        ]

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute size analysis.

        Args:
            inputs: Dictionary with firmware (required)

        Returns:
            Dictionary with size_report (json), warnings (array<string>)

        Raises:
            ValueError: If firmware is missing or invalid
        """
        # Validate required inputs
        firmware = inputs.get("firmware")
        if not firmware:
            raise ValueError("firmware is required and cannot be empty")

        # Extract firmware data
        size_bytes = firmware.get("size_bytes", 0)
        sections = firmware.get("sections", {})
        target = firmware.get("target", "unknown")
        framework = firmware.get("framework", "unknown")

        logger.info(
            f"Analyzing firmware size: target={target}, framework={framework}, "
            f"size={size_bytes} bytes"
        )

        # Build size report
        size_report = {
            "total_size_bytes": size_bytes,
            "total_size_kb": round(size_bytes / 1024, 2),
            "target": target,
            "framework": framework,
            "sections": sections,
        }

        # Calculate percentages if we know flash size
        flash_sizes = {
            "esp32": 4 * 1024 * 1024,  # 4MB typical
            "esp32s2": 4 * 1024 * 1024,
            "esp32s3": 8 * 1024 * 1024,  # 8MB typical
            "esp32c3": 4 * 1024 * 1024,
            "esp32c6": 4 * 1024 * 1024,
        }

        flash_size = flash_sizes.get(target, 4 * 1024 * 1024)
        usage_percent = (size_bytes / flash_size) * 100

        size_report["flash_size_bytes"] = flash_size
        size_report["usage_percent"] = round(usage_percent, 2)

        # Generate warnings
        warnings = []

        if usage_percent > 90:
            warnings.append(
                f"Critical: Firmware uses {usage_percent:.1f}% of flash (>90%). "
                "Very limited space remaining."
            )
        elif usage_percent > 75:
            warnings.append(
                f"Warning: Firmware uses {usage_percent:.1f}% of flash (>75%). "
                "Consider optimizing size."
            )
        elif usage_percent > 50:
            warnings.append(
                f"Info: Firmware uses {usage_percent:.1f}% of flash (>50%). "
                "Size is reasonable but monitor growth."
            )

        # Check individual sections if available
        if "flash_code" in sections:
            flash_code = sections["flash_code"]
            if flash_code > 1 * 1024 * 1024:  # >1MB
                warnings.append(
                    f"Large code section: {flash_code / 1024:.1f} KB. "
                    "Consider enabling compiler optimizations (-Os)."
                )

        if "flash_rodata" in sections:
            flash_rodata = sections["flash_rodata"]
            if flash_rodata > 512 * 1024:  # >512KB
                warnings.append(
                    f"Large rodata section: {flash_rodata / 1024:.1f} KB. "
                    "Check for large constant arrays or strings."
                )

        # RAM usage warnings (if available)
        if "dram" in sections:
            # ESP32 has ~520KB total RAM, but varies by model
            ram_sizes = {
                "esp32": 520 * 1024,
                "esp32s2": 320 * 1024,
                "esp32s3": 512 * 1024,
                "esp32c3": 400 * 1024,
                "esp32c6": 512 * 1024,
            }
            ram_size = ram_sizes.get(target, 400 * 1024)
            dram = sections["dram"]
            ram_percent = (dram / ram_size) * 100

            if ram_percent > 50:
                warnings.append(
                    f"High static RAM usage: {dram / 1024:.1f} KB ({ram_percent:.1f}%). "
                    "May limit dynamic allocation."
                )

        logger.info(
            f"Size analysis complete: {size_bytes} bytes ({usage_percent:.1f}% of flash), "
            f"{len(warnings)} warnings"
        )

        return {
            "size_report": size_report,
            "warnings": warnings,
        }
