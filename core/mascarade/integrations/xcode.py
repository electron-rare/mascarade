"""Xcode integration — build, test, Swift, simulators, provisioning."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("mascarade.integrations.xcode")


@dataclass
class XcodeBuildResult:
    """Result of an Xcode build or test operation."""

    success: bool
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


async def _run(
    cmd: list[str],
    *,
    cwd: str | None = None,
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> XcodeBuildResult:
    """Run an Xcode CLI command and return structured result."""
    import time

    run_env = {**os.environ, **(env or {})}
    start = time.monotonic()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=run_env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return XcodeBuildResult(
            success=False,
            command=" ".join(cmd),
            exit_code=-1,
            stdout="",
            stderr=f"Timeout after {timeout}s",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    duration = (time.monotonic() - start) * 1000
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")

    # Parse warnings and errors from output
    warnings = [l for l in out.splitlines() if "warning:" in l.lower()]
    errors = [l for l in out.splitlines() if "error:" in l.lower()]

    return XcodeBuildResult(
        success=proc.returncode == 0,
        command=" ".join(cmd),
        exit_code=proc.returncode or 0,
        stdout=out,
        stderr=err,
        duration_ms=duration,
        warnings=warnings[:50],
        errors=errors[:50],
    )


class XcodeProvider:
    """Xcode build system integration for mascarade.

    Provides programmatic access to:
    - xcodebuild (build, test, archive, export)
    - swift (compile, run, package manager)
    - xcrun (SDK tools, simctl, instruments)
    - Project/workspace discovery and analysis
    """

    def __init__(self, project_path: str | None = None):
        self._project_path = project_path

    # --- Discovery ---

    async def discover_projects(self, search_path: str = ".") -> list[dict[str, str]]:
        """Find Xcode projects and workspaces in a directory."""
        projects = []
        search = Path(search_path)

        for pattern, kind in [
            ("**/*.xcworkspace", "workspace"),
            ("**/*.xcodeproj", "project"),
        ]:
            for p in search.glob(pattern):
                if ".build" in str(p) or "DerivedData" in str(p):
                    continue
                projects.append(
                    {
                        "path": str(p),
                        "name": p.stem,
                        "type": kind,
                    }
                )

        # Also find Swift packages
        for p in search.glob("**/Package.swift"):
            if ".build" in str(p):
                continue
            projects.append(
                {
                    "path": str(p.parent),
                    "name": p.parent.name,
                    "type": "swift-package",
                }
            )

        return projects

    async def get_project_info(self, project_path: str) -> dict[str, Any]:
        """Get information about an Xcode project or workspace."""
        path = Path(project_path)

        if path.suffix == ".xcworkspace" or path.suffix == ".xcodeproj":
            result = await _run(
                [
                    "xcodebuild",
                    "-list",
                    "-json",
                    "-project" if path.suffix == ".xcodeproj" else "-workspace",
                    str(path),
                ],
                timeout=30.0,
            )
            if result.success:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

        # Swift package
        if (path / "Package.swift").exists() or path.name == "Package.swift":
            pkg_dir = str(path if path.is_dir() else path.parent)
            result = await _run(
                ["swift", "package", "describe", "--type", "json"],
                cwd=pkg_dir,
                timeout=30.0,
            )
            if result.success:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

        return {"error": "Could not parse project info", "path": str(path)}

    # --- Build ---

    async def build(
        self,
        project_path: str,
        *,
        scheme: str | None = None,
        configuration: str = "Debug",
        destination: str = "generic/platform=iOS",
        sdk: str | None = None,
        extra_args: list[str] | None = None,
        timeout: float = 600.0,
    ) -> XcodeBuildResult:
        """Build an Xcode project or Swift package."""
        path = Path(project_path)

        # Swift package
        if (path / "Package.swift").exists() or path.name == "Package.swift":
            pkg_dir = str(path if path.is_dir() else path.parent)
            cmd = ["swift", "build", "-c", configuration.lower()]
            if extra_args:
                cmd.extend(extra_args)
            return await _run(cmd, cwd=pkg_dir, timeout=timeout)

        # Xcode project/workspace
        cmd = ["xcodebuild", "build"]
        if path.suffix == ".xcworkspace":
            cmd.extend(["-workspace", str(path)])
        elif path.suffix == ".xcodeproj":
            cmd.extend(["-project", str(path)])

        if scheme:
            cmd.extend(["-scheme", scheme])
        cmd.extend(["-configuration", configuration])
        cmd.extend(["-destination", destination])
        if sdk:
            cmd.extend(["-sdk", sdk])
        if extra_args:
            cmd.extend(extra_args)

        return await _run(cmd, timeout=timeout)

    async def build_swift(
        self,
        source: str,
        *,
        output: str | None = None,
        flags: list[str] | None = None,
    ) -> XcodeBuildResult:
        """Compile a Swift source file directly."""
        cmd = ["swiftc", source]
        if output:
            cmd.extend(["-o", output])
        if flags:
            cmd.extend(flags)
        return await _run(cmd, timeout=120.0)

    # --- Test ---

    async def test(
        self,
        project_path: str,
        *,
        scheme: str | None = None,
        destination: str = "platform=iOS Simulator,name=iPhone 16",
        test_plan: str | None = None,
        filter_test: str | None = None,
        timeout: float = 900.0,
    ) -> XcodeBuildResult:
        """Run tests for an Xcode project or Swift package."""
        path = Path(project_path)

        # Swift package
        if (path / "Package.swift").exists():
            cmd = ["swift", "test"]
            if filter_test:
                cmd.extend(["--filter", filter_test])
            return await _run(cmd, cwd=str(path), timeout=timeout)

        # Xcode project
        cmd = ["xcodebuild", "test"]
        if path.suffix == ".xcworkspace":
            cmd.extend(["-workspace", str(path)])
        elif path.suffix == ".xcodeproj":
            cmd.extend(["-project", str(path)])

        if scheme:
            cmd.extend(["-scheme", scheme])
        cmd.extend(["-destination", destination])
        if test_plan:
            cmd.extend(["-testPlan", test_plan])
        if filter_test:
            cmd.extend(["-only-testing", filter_test])

        return await _run(cmd, timeout=timeout)

    # --- Archive & Export ---

    async def archive(
        self,
        project_path: str,
        *,
        scheme: str,
        archive_path: str,
        configuration: str = "Release",
        timeout: float = 1200.0,
    ) -> XcodeBuildResult:
        """Create an Xcode archive (.xcarchive)."""
        path = Path(project_path)
        cmd = ["xcodebuild", "archive"]

        if path.suffix == ".xcworkspace":
            cmd.extend(["-workspace", str(path)])
        else:
            cmd.extend(["-project", str(path)])

        cmd.extend(
            [
                "-scheme",
                scheme,
                "-configuration",
                configuration,
                "-archivePath",
                archive_path,
            ]
        )

        return await _run(cmd, timeout=timeout)

    async def export_ipa(
        self,
        archive_path: str,
        *,
        export_path: str,
        export_options_plist: str,
        timeout: float = 600.0,
    ) -> XcodeBuildResult:
        """Export an IPA from an archive."""
        cmd = [
            "xcodebuild",
            "-exportArchive",
            "-archivePath",
            archive_path,
            "-exportPath",
            export_path,
            "-exportOptionsPlist",
            export_options_plist,
        ]
        return await _run(cmd, timeout=timeout)

    # --- Simulators ---

    async def list_simulators(self) -> list[dict[str, Any]]:
        """List available iOS/macOS simulators."""
        result = await _run(
            ["xcrun", "simctl", "list", "devices", "-j"],
            timeout=15.0,
        )
        if result.success:
            try:
                data = json.loads(result.stdout)
                devices = []
                for runtime, devs in data.get("devices", {}).items():
                    for dev in devs:
                        dev["runtime"] = runtime
                        devices.append(dev)
                return devices
            except json.JSONDecodeError:
                pass
        return []

    async def boot_simulator(self, device_id: str) -> XcodeBuildResult:
        """Boot a simulator."""
        return await _run(["xcrun", "simctl", "boot", device_id], timeout=30.0)

    async def shutdown_simulator(self, device_id: str) -> XcodeBuildResult:
        """Shutdown a simulator."""
        return await _run(["xcrun", "simctl", "shutdown", device_id], timeout=15.0)

    async def install_app(self, device_id: str, app_path: str) -> XcodeBuildResult:
        """Install an app on a simulator."""
        return await _run(
            ["xcrun", "simctl", "install", device_id, app_path],
            timeout=60.0,
        )

    # --- Swift Package Manager ---

    async def swift_package_init(
        self, path: str, *, name: str, kind: str = "library"
    ) -> XcodeBuildResult:
        """Initialize a new Swift package."""
        return await _run(
            ["swift", "package", "init", "--name", name, "--type", kind],
            cwd=path,
            timeout=30.0,
        )

    async def swift_package_resolve(self, path: str) -> XcodeBuildResult:
        """Resolve Swift package dependencies."""
        return await _run(
            ["swift", "package", "resolve"],
            cwd=path,
            timeout=120.0,
        )

    async def swift_package_update(self, path: str) -> XcodeBuildResult:
        """Update Swift package dependencies."""
        return await _run(
            ["swift", "package", "update"],
            cwd=path,
            timeout=120.0,
        )

    # --- Code Analysis ---

    async def swift_lint(self, path: str, *, fix: bool = False) -> XcodeBuildResult:
        """Run SwiftLint on a directory (requires swiftlint installed)."""
        cmd = ["swiftlint"]
        if fix:
            cmd.append("--fix")
        cmd.extend(["--path", path])
        return await _run(cmd, timeout=120.0)

    async def swift_format(self, path: str, *, in_place: bool = False) -> XcodeBuildResult:
        """Run swift-format on a directory."""
        cmd = ["swift-format"]
        if in_place:
            cmd.append("--in-place")
        cmd.extend(["-r", path])
        return await _run(cmd, timeout=60.0)

    # --- Utilities ---

    async def available_sdks(self) -> list[dict[str, str]]:
        """List available SDKs."""
        result = await _run(
            ["xcodebuild", "-showsdks", "-json"],
            timeout=15.0,
        )
        if result.success:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        return []

    async def swift_version(self) -> str:
        """Get Swift compiler version."""
        result = await _run(["swift", "--version"], timeout=5.0)
        return result.stdout.strip().split("\n")[0] if result.success else ""

    async def xcode_version(self) -> str:
        """Get Xcode version."""
        result = await _run(["xcodebuild", "-version"], timeout=5.0)
        return result.stdout.strip() if result.success else "Xcode not installed"
