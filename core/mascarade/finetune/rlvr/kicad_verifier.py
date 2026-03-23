"""KiCad DRC reward function — verifies generated schematics/PCBs."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from mascarade.finetune.rlvr.reward_functions import RewardFunction, RewardResult

logger = logging.getLogger("mascarade.finetune.rlvr.kicad")


class KiCadDRCReward(RewardFunction):
    """Run KiCad DRC on generated schematics and return graded reward.

    Rewards:
        1.0 — DRC passes with 0 errors, 0 warnings
        0.5 — DRC passes with only warnings
        0.0 — DRC fails with errors
       -0.5 — Output cannot be parsed as KiCad format
       -1.0 — Empty completion

    Requires ``kibot`` CLI to be installed and accessible.
    Install via: ``pip install kibot>=1.8``
    """

    def __init__(self, *, kibot_path: str = "kibot", timeout_seconds: int = 30):
        self._kibot = kibot_path
        self._timeout = timeout_seconds

    async def evaluate(self, prompt: str, completion: str) -> RewardResult:
        stripped = completion.strip()
        if not stripped:
            return RewardResult(
                score=-1.0,
                passed=False,
                details="Empty completion",
                errors=["Completion is empty or whitespace-only"],
            )

        # Detect file type from content heuristics
        if "(kicad_pcb" in stripped:
            suffix = ".kicad_pcb"
        elif "(kicad_sch" in stripped:
            suffix = ".kicad_sch"
        else:
            return RewardResult(
                score=-0.5,
                passed=False,
                details="Output does not look like KiCad format (missing kicad_pcb or kicad_sch header)",
                errors=["Unrecognized KiCad format"],
            )

        # Write to temp file and run DRC
        with tempfile.TemporaryDirectory(prefix="mascarade_drc_") as tmpdir:
            filepath = Path(tmpdir) / f"design{suffix}"
            filepath.write_text(stripped, encoding="utf-8")

            return await self._run_drc(filepath)

    async def _run_drc(self, filepath: Path) -> RewardResult:
        """Execute kibot DRC preflight and parse results."""
        report_path = filepath.parent / "drc_report.json"

        cmd = [
            self._kibot,
            "-e",
            str(filepath) if filepath.suffix == ".kicad_sch" else "",
            "-b",
            str(filepath) if filepath.suffix == ".kicad_pcb" else "",
            "-s",
            "all",  # skip all outputs
            "-d",
            str(filepath.parent),
            "--drc",
        ]
        # Remove empty args
        cmd = [c for c in cmd if c]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(filepath.parent),
            )
        except FileNotFoundError:
            return RewardResult(
                score=0.0,
                passed=False,
                details=f"kibot not found at '{self._kibot}' — install with: pip install kibot>=1.8",
                errors=["kibot CLI not available"],
            )
        except subprocess.TimeoutExpired:
            return RewardResult(
                score=0.0,
                passed=False,
                details=f"DRC timed out after {self._timeout}s",
                errors=["DRC timeout"],
            )

        # Parse kibot output for error/warning counts
        stdout = result.stdout
        stderr = result.stderr
        combined = stdout + "\n" + stderr

        error_count = combined.lower().count("error")
        warning_count = combined.lower().count("warning")

        # Also try to read JSON report if kibot produced one
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                error_count = report.get("errors", error_count)
                warning_count = report.get("warnings", warning_count)
            except (json.JSONDecodeError, OSError):
                pass

        if result.returncode != 0 and "error" in combined.lower():
            return RewardResult(
                score=0.0,
                passed=False,
                details=f"DRC failed: {error_count} errors, {warning_count} warnings",
                errors=self._extract_messages(combined, "error"),
                warnings=self._extract_messages(combined, "warning"),
            )

        if warning_count > 0:
            return RewardResult(
                score=0.5,
                passed=True,
                details=f"DRC passed with {warning_count} warnings",
                warnings=self._extract_messages(combined, "warning"),
            )

        return RewardResult(
            score=1.0,
            passed=True,
            details="DRC passed with 0 errors and 0 warnings",
        )

    @staticmethod
    def _extract_messages(output: str, level: str, max_messages: int = 10) -> list[str]:
        """Extract error/warning lines from kibot output."""
        messages: list[str] = []
        for line in output.splitlines():
            if level.lower() in line.lower():
                messages.append(line.strip())
                if len(messages) >= max_messages:
                    break
        return messages
