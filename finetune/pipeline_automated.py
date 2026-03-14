#!/usr/bin/env python3
"""
Automated Fine-Tuning Pipeline Runner
======================================
Orchestrates the full pipeline (train → merge → gguf → deploy) with
event emission, dry-run mode, and resume capability.

Usage:
    from finetune.pipeline_automated import PipelineRunner

    runner = PipelineRunner(domain="stm32", base_model="Qwen/Qwen2.5-Coder-7B-Instruct")
    runner.run()
"""

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Any, Callable

# Lazy imports for pipeline functions to avoid initialization side effects
_pipeline_module = None


def _get_pipeline_module():
    """Lazy-load pipeline module to avoid directory creation side effects during import"""
    global _pipeline_module
    if _pipeline_module is not None:
        return _pipeline_module

    # Set a temporary LLM dir to avoid permission issues during import
    if "MASCARADE_LLM_DIR" not in os.environ:
        os.environ["MASCARADE_LLM_DIR"] = str(Path.home() / ".cache" / "mascarade" / "llm")

    try:
        from . import pipeline as _pipeline_module
    except ImportError:  # pragma: no cover - script execution path
        # Add finetune directory to path if not already there
        finetune_dir = Path(__file__).parent
        if str(finetune_dir) not in sys.path:
            sys.path.insert(0, str(finetune_dir))
        import pipeline as _pipeline_module

    return _pipeline_module


# Default domains list (avoid importing pipeline at module level)
DOMAINS = [
    "stm32", "spice", "iot", "power", "dsp", "emc", "kicad",
    "embedded", "platformio", "freecad", "components"
]


StepName = Literal["train", "merge", "gguf", "deploy"]
EventType = Literal["pipeline_start", "step_start", "step_complete", "step_failed", "pipeline_complete", "pipeline_failed"]

# Default base model (matches pipeline.py)
DEFAULT_BASE = "Qwen/Qwen2.5-Coder-7B-Instruct"


@dataclass
class PipelineEvent:
    """Structured event for observability (Grafana/Langfuse)"""
    event_type: EventType
    timestamp: str
    domain: str
    step: str | None = None
    status: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def to_json(self) -> str:
        """Serialize event to JSON"""
        return json.dumps(asdict(self), default=str)


class PipelineRunner:
    """
    Automated pipeline runner for fine-tuning workflows.

    Orchestrates train → merge → gguf → deploy with structured event
    emission for observability.

    Example:
        runner = PipelineRunner(
            domain="stm32",
            base_model="Qwen/Qwen2.5-Coder-7B-Instruct",
            epochs=3,
            dry_run=False
        )
        success = runner.run()
    """

    def __init__(
        self,
        domain: str,
        base_model: str = DEFAULT_BASE,
        steps: list[StepName] | None = None,
        epochs: int = 3,
        max_seq_len: int = 512,
        max_samples: int | None = None,
        train_quant: str = "4bit",
        gguf_quant: str = "q4_k_m",
        deploy_alias: str | None = None,
        dry_run: bool = False,
        emit_events: bool = True,
    ):
        """
        Initialize pipeline runner.

        Args:
            domain: Domain to fine-tune (e.g., "stm32", "kicad")
            base_model: Base model identifier or path
            steps: Steps to run (default: all steps)
            epochs: Training epochs
            max_seq_len: Maximum sequence length
            max_samples: Maximum training samples (None = all)
            train_quant: Training quantization mode ("4bit" or "none")
            gguf_quant: GGUF quantization format
            deploy_alias: Custom Ollama model name
            dry_run: Preview mode (don't execute steps)
            emit_events: Enable structured event emission
        """
        if domain not in DOMAINS:
            raise ValueError(f"Unknown domain: {domain}. Valid: {DOMAINS}")

        self.domain = domain
        self.base_model = base_model
        self.steps = steps or ["train", "merge", "gguf", "deploy"]
        self.epochs = epochs
        self.max_seq_len = max_seq_len
        self.max_samples = max_samples
        self.train_quant = train_quant
        self.gguf_quant = gguf_quant
        self.deploy_alias = deploy_alias
        self.dry_run = dry_run
        self.emit_events = emit_events

        self._start_time: float | None = None
        self._step_start_time: float | None = None

    def _emit_event(self, event: PipelineEvent) -> None:
        """Emit structured JSON event to stdout"""
        if self.emit_events:
            print(event.to_json(), file=sys.stdout, flush=True)

    def _run_step(self, step: StepName) -> bool:
        """
        Execute a single pipeline step.

        Args:
            step: Step name to execute

        Returns:
            True if step succeeded, False otherwise
        """
        self._step_start_time = time.time()

        self._emit_event(PipelineEvent(
            event_type="step_start",
            timestamp=datetime.utcnow().isoformat(),
            domain=self.domain,
            step=step,
            status="running",
            metadata={
                "base_model": self.base_model,
                "dry_run": self.dry_run,
            }
        ))

        if self.dry_run:
            print(f"\n[DRY RUN] Would execute step: {step}")
            print(f"  Domain: {self.domain}")
            print(f"  Base model: {self.base_model}")
            if step == "train":
                print(f"  Epochs: {self.epochs}, Seq len: {self.max_seq_len}")
                print(f"  Train quant: {self.train_quant}")
            elif step == "gguf":
                print(f"  GGUF quant: {self.gguf_quant}")
            elif step == "deploy":
                print(f"  Deploy alias: {self.deploy_alias or f'mascarade-{self.domain}'}")

            success = True
        else:
            # Lazy load pipeline module
            pipeline = _get_pipeline_module()

            try:
                if step == "train":
                    success = pipeline.step_train(
                        self.domain,
                        self.base_model,
                        epochs=self.epochs,
                        max_seq_len=self.max_seq_len,
                        max_samples=self.max_samples,
                        train_quant=self.train_quant,
                    )
                elif step == "merge":
                    success = pipeline.step_merge(self.domain, self.base_model)
                elif step == "gguf":
                    success = pipeline.step_gguf(self.domain, self.gguf_quant)
                elif step == "deploy":
                    success = pipeline.step_deploy(self.domain, deploy_alias=self.deploy_alias)
                else:
                    raise ValueError(f"Unknown step: {step}")
            except Exception as exc:
                duration = time.time() - self._step_start_time
                self._emit_event(PipelineEvent(
                    event_type="step_failed",
                    timestamp=datetime.utcnow().isoformat(),
                    domain=self.domain,
                    step=step,
                    status="failed",
                    duration_seconds=duration,
                    error=str(exc),
                ))
                raise

        duration = time.time() - self._step_start_time

        if success:
            self._emit_event(PipelineEvent(
                event_type="step_complete",
                timestamp=datetime.utcnow().isoformat(),
                domain=self.domain,
                step=step,
                status="completed",
                duration_seconds=duration,
            ))
        else:
            self._emit_event(PipelineEvent(
                event_type="step_failed",
                timestamp=datetime.utcnow().isoformat(),
                domain=self.domain,
                step=step,
                status="failed",
                duration_seconds=duration,
                error="Step returned False",
            ))

        return success

    def run(self) -> bool:
        """
        Run the full pipeline.

        Returns:
            True if all steps succeeded, False otherwise
        """
        self._start_time = time.time()

        self._emit_event(PipelineEvent(
            event_type="pipeline_start",
            timestamp=datetime.utcnow().isoformat(),
            domain=self.domain,
            status="running",
            metadata={
                "steps": self.steps,
                "base_model": self.base_model,
                "dry_run": self.dry_run,
                "epochs": self.epochs,
                "train_quant": self.train_quant,
                "gguf_quant": self.gguf_quant,
            }
        ))

        print(f"\n{'='*60}")
        print(f"  AUTOMATED PIPELINE: {self.domain}")
        print(f"  Base model: {self.base_model}")
        print(f"  Steps: {' → '.join(self.steps)}")
        if self.dry_run:
            print(f"  Mode: DRY RUN (preview only)")
        print(f"{'='*60}\n")

        try:
            for step in self.steps:
                print(f"\n{'#'*60}")
                print(f"# STEP: {step.upper()}")
                print(f"{'#'*60}")

                success = self._run_step(step)
                if not success:
                    total_duration = time.time() - self._start_time
                    self._emit_event(PipelineEvent(
                        event_type="pipeline_failed",
                        timestamp=datetime.utcnow().isoformat(),
                        domain=self.domain,
                        status="failed",
                        duration_seconds=total_duration,
                        error=f"Step {step} failed",
                        metadata={"failed_step": step}
                    ))
                    return False

            total_duration = time.time() - self._start_time
            self._emit_event(PipelineEvent(
                event_type="pipeline_complete",
                timestamp=datetime.utcnow().isoformat(),
                domain=self.domain,
                status="completed",
                duration_seconds=total_duration,
                metadata={"steps_completed": len(self.steps)}
            ))

            print(f"\n{'='*60}")
            print(f"  Pipeline complete for {self.domain}!")
            print(f"  Total time: {total_duration:.1f}s")
            print(f"{'='*60}\n")

            return True

        except Exception as exc:
            total_duration = time.time() - self._start_time
            self._emit_event(PipelineEvent(
                event_type="pipeline_failed",
                timestamp=datetime.utcnow().isoformat(),
                domain=self.domain,
                status="failed",
                duration_seconds=total_duration,
                error=str(exc),
            ))
            raise


def main():
    """CLI entry point for automated pipeline"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated fine-tuning pipeline with event emission",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("domain", choices=DOMAINS, help="Domain to fine-tune")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base model")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode (don't execute)")
    parser.add_argument("--no-events", action="store_true", help="Disable event emission")

    args = parser.parse_args()

    runner = PipelineRunner(
        domain=args.domain,
        base_model=args.base,
        epochs=args.epochs,
        dry_run=args.dry_run,
        emit_events=not args.no_events,
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
