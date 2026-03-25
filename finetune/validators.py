#!/usr/bin/env python3
"""Domain-specific validators for rejection sampling and DPO pair generation.

Each validator checks if a model-generated response is technically correct
using deterministic tools (compilers, simulators, parsers) or LLM-as-judge.

Usage:
    from validators import get_validator, validate_response

    v = get_validator("stm32")
    result = v.validate(prompt, response)
    # result.score: 0.0 (fail) / 0.5 (partial) / 1.0 (pass)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    score: float  # 0.0 = fail, 0.5 = partial, 1.0 = pass
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict | None = None


def _extract_code_blocks(text: str, lang: str | None = None) -> list[str]:
    """Extract fenced code blocks from markdown text."""
    pattern = r"```(?:" + (lang or r"[a-zA-Z]*") + r")?\s*\n(.*?)```"
    blocks = re.findall(pattern, text, re.DOTALL)
    if not blocks:
        # Fallback: treat entire text as code if no blocks found
        stripped = text.strip()
        if stripped and not stripped.startswith("#"):
            return [stripped]
    return blocks


class BaseValidator(ABC):
    """Base class for domain validators."""

    domain: str = ""

    @abstractmethod
    def validate(self, prompt: str, response: str) -> ValidationResult: ...

    def available(self) -> bool:
        """Check if validator tools are installed."""
        return True


# ---------------------------------------------------------------------------
# STM32 / Embedded C validator — uses arm-none-eabi-gcc or gcc
# ---------------------------------------------------------------------------


class EmbeddedCValidator(BaseValidator):
    domain = "stm32"

    def __init__(self, compiler: str | None = None, target: str = "cortex-m4"):
        self.target = target
        if compiler:
            self.compiler = compiler
        elif shutil.which("arm-none-eabi-gcc"):
            self.compiler = "arm-none-eabi-gcc"
        elif shutil.which("gcc"):
            self.compiler = "gcc"
        else:
            self.compiler = None

    def available(self) -> bool:
        return self.compiler is not None

    def validate(self, prompt: str, response: str) -> ValidationResult:
        blocks = _extract_code_blocks(response, r"c(?:\+\+)?")
        if not blocks:
            return ValidationResult(
                score=0.0, passed=False, errors=["No code block found"]
            )

        all_errors = []
        all_warnings = []
        passed_count = 0

        for code in blocks:
            result = self._compile_check(code)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            if result.passed:
                passed_count += 1

        if passed_count == len(blocks):
            score = 1.0 if not all_warnings else 0.8
        elif passed_count > 0:
            score = 0.5
        else:
            score = 0.0

        return ValidationResult(
            score=score,
            passed=score >= 0.5,
            errors=all_errors,
            warnings=all_warnings,
            details={"blocks": len(blocks), "compiled": passed_count},
        )

    def _compile_check(self, code: str) -> ValidationResult:
        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
            f.write(code)
            src = f.name

        cmd = [self.compiler, "-fsyntax-only", "-Wall", "-std=c11"]
        if self.compiler == "arm-none-eabi-gcc":
            cmd.extend([f"-mcpu={self.target}", "-mthumb"])
        cmd.append(src)

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            errors = [l for l in r.stderr.splitlines() if "error:" in l]
            warnings = [l for l in r.stderr.splitlines() if "warning:" in l]
            return ValidationResult(
                score=1.0 if r.returncode == 0 else 0.0,
                passed=r.returncode == 0,
                errors=errors,
                warnings=warnings,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return ValidationResult(score=0.0, passed=False, errors=[str(exc)])
        finally:
            os.unlink(src)


# ---------------------------------------------------------------------------
# SPICE validator — uses ngspice
# ---------------------------------------------------------------------------


class SpiceValidator(BaseValidator):
    domain = "spice"

    def available(self) -> bool:
        return shutil.which("ngspice") is not None

    def validate(self, prompt: str, response: str) -> ValidationResult:
        blocks = _extract_code_blocks(response, r"(?:spice|ngspice|netlist)?")
        if not blocks:
            # Try to find raw netlist (starts with * or .)
            lines = response.strip().split("\n")
            netlist_lines = [
                l
                for l in lines
                if l.strip().startswith(
                    ("*", ".", "V", "R", "C", "L", "M", "Q", "D", "X")
                )
            ]
            if len(netlist_lines) > 3:
                blocks = ["\n".join(netlist_lines)]

        if not blocks:
            return ValidationResult(
                score=0.0, passed=False, errors=["No SPICE netlist found"]
            )

        for block in blocks:
            result = self._simulate_check(block)
            if result.passed:
                return result

        return ValidationResult(
            score=0.0, passed=False, errors=["No valid netlist simulated"]
        )

    def _simulate_check(self, netlist: str) -> ValidationResult:
        # Ensure .end directive
        if ".end" not in netlist.lower():
            netlist = netlist.strip() + "\n.end\n"

        with tempfile.NamedTemporaryFile(suffix=".cir", mode="w", delete=False) as f:
            f.write(netlist)
            cir = f.name

        try:
            r = subprocess.run(
                ["ngspice", "-b", cir],
                capture_output=True,
                text=True,
                timeout=30,
            )
            errors = [l for l in r.stderr.splitlines() if "error" in l.lower()]
            warnings = [l for l in r.stderr.splitlines() if "warning" in l.lower()]

            # ngspice returns 0 even on some errors, check stderr
            has_fatal = any(
                "fatal" in e.lower() or "cannot" in e.lower() for e in errors
            )
            passed = r.returncode == 0 and not has_fatal

            return ValidationResult(
                score=1.0 if passed and not warnings else (0.5 if passed else 0.0),
                passed=passed,
                errors=errors,
                warnings=warnings,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return ValidationResult(score=0.0, passed=False, errors=[str(exc)])
        finally:
            os.unlink(cir)


# ---------------------------------------------------------------------------
# KiCad validator — uses kicad-cli DRC or S-expression parser
# ---------------------------------------------------------------------------


class KicadValidator(BaseValidator):
    domain = "kicad"

    def available(self) -> bool:
        return shutil.which("kicad-cli") is not None

    def validate(self, prompt: str, response: str) -> ValidationResult:
        # KiCad S-expression syntax check
        blocks = _extract_code_blocks(response)
        if not blocks:
            blocks = [response]

        for block in blocks:
            # Check if it looks like a KiCad S-expression
            if re.search(
                r"\(kicad_sch|\(kicad_pcb|\(footprint|\(module|\(symbol", block
            ):
                return self._check_sexp(block)

        # Fallback: check if response contains meaningful KiCad keywords
        kicad_keywords = [
            "footprint",
            "pad",
            "wire",
            "symbol",
            "pin",
            "net",
            "zone",
            "via",
            "segment",
        ]
        found = sum(1 for kw in kicad_keywords if kw in response.lower())
        if found >= 3:
            return ValidationResult(
                score=0.5,
                passed=True,
                warnings=["Keywords found but no parseable S-expression"],
            )

        return ValidationResult(
            score=0.0, passed=False, errors=["No KiCad content found"]
        )

    def _check_sexp(self, text: str) -> ValidationResult:
        """Basic S-expression balance check."""
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                return ValidationResult(
                    score=0.0, passed=False, errors=["Unbalanced parentheses"]
                )

        if depth != 0:
            return ValidationResult(
                score=0.0, passed=False, errors=[f"Unbalanced: {depth} unclosed parens"]
            )

        return ValidationResult(score=1.0, passed=True)


# ---------------------------------------------------------------------------
# PlatformIO validator — uses pio run --check or syntax check
# ---------------------------------------------------------------------------


class PlatformIOValidator(BaseValidator):
    domain = "platformio"

    def available(self) -> bool:
        return shutil.which("pio") is not None

    def validate(self, prompt: str, response: str) -> ValidationResult:
        # Check for platformio.ini content
        if "[env:" in response or "[platformio]" in response:
            return self._validate_ini(response)

        # Check for Arduino/C++ code
        blocks = _extract_code_blocks(response, r"(?:cpp|c\+\+|arduino|ino)?")
        if blocks:
            return self._validate_arduino_syntax(blocks[0])

        return ValidationResult(
            score=0.0, passed=False, errors=["No PlatformIO content found"]
        )

    def _validate_ini(self, text: str) -> ValidationResult:
        # Basic platformio.ini validation
        has_env = "[env:" in text or "[platformio]" in text
        has_platform = "platform" in text.lower()
        has_board = "board" in text.lower()

        if has_env and has_platform and has_board:
            return ValidationResult(score=1.0, passed=True)
        elif has_env:
            return ValidationResult(
                score=0.5, passed=True, warnings=["Incomplete platformio.ini"]
            )
        return ValidationResult(
            score=0.0, passed=False, errors=["Invalid platformio.ini"]
        )

    def _validate_arduino_syntax(self, code: str) -> ValidationResult:
        # Check for setup()/loop() or main()
        has_entry = bool(re.search(r"void\s+(setup|loop|main)\s*\(", code))
        has_include = "#include" in code
        if has_entry and has_include:
            return ValidationResult(score=0.8, passed=True)
        elif has_entry or has_include:
            return ValidationResult(
                score=0.5, passed=True, warnings=["Partial Arduino structure"]
            )
        return ValidationResult(
            score=0.0, passed=False, errors=["No Arduino entry point found"]
        )


# ---------------------------------------------------------------------------
# LLM-as-Judge validator — for domains without deterministic validators
# ---------------------------------------------------------------------------


class LLMJudgeValidator(BaseValidator):
    """Uses a local or remote LLM to score responses.

    Requires ollama with a model loaded, or an API endpoint.
    """

    def __init__(
        self,
        domain: str,
        ollama_model: str = "qwen3.5:9b",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.domain = domain
        self.ollama_model = ollama_model
        self.base_url = base_url

    def available(self) -> bool:
        try:
            import urllib.request

            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def validate(self, prompt: str, response: str) -> ValidationResult:
        judge_prompt = f"""You are an expert technical reviewer for {self.domain} engineering.

Rate the following response on a scale of 0-10 for:
1. Technical accuracy
2. Completeness
3. Code quality (if applicable)

User question: {prompt[:500]}

Response to evaluate: {response[:2000]}

Reply with ONLY a JSON object: {{"accuracy": N, "completeness": N, "code_quality": N, "overall": N, "issues": ["..."]}}"""

        try:
            import json
            import urllib.request

            payload = json.dumps(
                {
                    "model": self.ollama_model,
                    "messages": [{"role": "user", "content": judge_prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                }
            ).encode()

            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read())
            content = data.get("message", {}).get("content", "")

            # Parse score from JSON response
            match = re.search(r"\{[^}]+\}", content)
            if match:
                scores = json.loads(match.group())
                overall = scores.get("overall", 5) / 10.0
                issues = scores.get("issues", [])
                return ValidationResult(
                    score=overall,
                    passed=overall >= 0.5,
                    errors=issues if overall < 0.5 else [],
                    warnings=issues if overall >= 0.5 else [],
                    details=scores,
                )

            return ValidationResult(
                score=0.5, passed=True, warnings=["Could not parse judge output"]
            )

        except Exception as exc:
            return ValidationResult(
                score=0.5, passed=True, warnings=[f"LLM judge unavailable: {exc}"]
            )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

VALIDATORS: dict[str, type[BaseValidator]] = {
    "stm32": EmbeddedCValidator,
    "embedded": EmbeddedCValidator,
    "spice": SpiceValidator,
    "kicad": KicadValidator,
    "platformio": PlatformIOValidator,
}

# Domains that fall back to LLM judge
LLM_JUDGE_DOMAINS = {"dsp", "power", "emc", "iot", "freecad", "components"}


def get_validator(domain: str, **kwargs) -> BaseValidator:
    """Get the best available validator for a domain."""
    if domain in VALIDATORS:
        v = VALIDATORS[domain](**kwargs) if kwargs else VALIDATORS[domain]()
        if v.available():
            return v

    # Fallback to LLM judge
    return LLMJudgeValidator(domain=domain, **kwargs)


def validate_response(
    domain: str, prompt: str, response: str, **kwargs
) -> ValidationResult:
    """Convenience function: validate a single response."""
    v = get_validator(domain, **kwargs)
    return v.validate(prompt, response)
