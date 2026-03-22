"""Xcode integration router — build, test, simulators, project analysis."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.xcode")

router = APIRouter(
    prefix="/v1/api/xcode",
    dependencies=[Depends(require_auth)],
    tags=["xcode"],
)


class XcodeBuildRequest(BaseModel):
    project_path: str = Field(min_length=1, max_length=500)
    scheme: str | None = Field(default=None, max_length=100)
    configuration: str = Field(default="Debug", max_length=50)
    destination: str = Field(default="generic/platform=iOS", max_length=200)
    sdk: str | None = Field(default=None, max_length=50)


class SwiftBuildRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    output: str | None = Field(default=None, max_length=500)
    flags: list[str] = Field(default_factory=list)


class SwiftPackageRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    name: str = Field(default="MyPackage", max_length=100)
    kind: str = Field(default="library", max_length=50)


@router.get("/version")
async def xcode_version():
    """Get Xcode and Swift version info."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    swift_ver = await xc.swift_version()
    xcode_ver = await xc.xcode_version()
    return {
        "swift": swift_ver,
        "xcode": xcode_ver,
    }


@router.get("/sdks")
async def list_sdks():
    """List available Apple SDKs."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    sdks = await xc.available_sdks()
    return {"sdks": sdks}


@router.get("/simulators")
async def list_simulators():
    """List available iOS/macOS simulators."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    devices = await xc.list_simulators()
    return {"devices": devices, "count": len(devices)}


@router.post("/discover")
async def discover_projects(path: str = "."):
    """Discover Xcode projects, workspaces, and Swift packages."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    projects = await xc.discover_projects(path)
    return {"projects": projects, "count": len(projects)}


@router.post("/project-info")
async def get_project_info(project_path: str):
    """Get detailed info about an Xcode project or Swift package."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    info = await xc.get_project_info(project_path)
    return info


@router.post("/build")
async def build_project(req: XcodeBuildRequest):
    """Build an Xcode project or Swift package."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    result = await xc.build(
        req.project_path,
        scheme=req.scheme,
        configuration=req.configuration,
        destination=req.destination,
        sdk=req.sdk,
    )
    return {
        "success": result.success,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "warnings": result.warnings,
        "errors": result.errors,
        "stdout": result.stdout[:5000] if not result.success else "",
        "stderr": result.stderr[:2000] if not result.success else "",
    }


@router.post("/build-swift")
async def build_swift(req: SwiftBuildRequest):
    """Compile a Swift source file."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    result = await xc.build_swift(req.source, output=req.output, flags=req.flags)
    return {
        "success": result.success,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "errors": result.errors,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:2000],
    }


@router.post("/test")
async def test_project(req: XcodeBuildRequest):
    """Run tests for an Xcode project or Swift package."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    result = await xc.test(
        req.project_path,
        scheme=req.scheme,
        destination=req.destination,
    )
    return {
        "success": result.success,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "warnings": result.warnings,
        "errors": result.errors,
    }


@router.post("/swift-package/init")
async def swift_package_init(req: SwiftPackageRequest):
    """Initialize a new Swift package."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    result = await xc.swift_package_init(req.path, name=req.name, kind=req.kind)
    return {
        "success": result.success,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:2000],
    }


@router.post("/swift-package/resolve")
async def swift_package_resolve(path: str):
    """Resolve Swift package dependencies."""
    from mascarade.integrations.xcode import XcodeProvider

    xc = XcodeProvider()
    result = await xc.swift_package_resolve(path)
    return {
        "success": result.success,
        "duration_ms": result.duration_ms,
        "stdout": result.stdout[:2000],
    }
