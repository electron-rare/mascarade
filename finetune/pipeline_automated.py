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
        state_file: str | None = None,
        resume: bool = True,
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
            state_file: Path to state file (default: .pipeline_state_{domain}.json)
            resume: Enable resume from saved state (default: True)
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
        self.state_file = state_file or "state.json"
        self.resume = resume

        self._start_time: float | None = None
        self._step_start_time: float | None = None
        self._completed_steps: list[str] = []

    def _emit_event(self, event: PipelineEvent) -> None:
        """Emit structured JSON event to stdout"""
        if self.emit_events:
            print(event.to_json(), file=sys.stdout, flush=True)

    def _get_state_path(self) -> Path:
        """Get path to state file"""
        return Path(self.state_file)

    def _load_state(self) -> dict[str, Any]:
        """
        Load pipeline state from JSON file.

        Returns:
            State dict with completed_steps, or empty dict if no state exists
        """
        state_path = self._get_state_path()
        if not state_path.exists():
            return {}

        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
            return state
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load state from {state_path}: {e}", file=sys.stderr)
            return {}

    def _save_state(self, completed_step: str) -> None:
        """
        Save pipeline state to JSON file after step completion.

        Args:
            completed_step: The step that just completed
        """
        self._completed_steps.append(completed_step)

        state = {
            "domain": self.domain,
            "base_model": self.base_model,
            "completed_steps": self._completed_steps,
            "last_updated": datetime.utcnow().isoformat(),
            "epochs": self.epochs,
            "train_quant": self.train_quant,
            "gguf_quant": self.gguf_quant,
            "deploy_alias": self.deploy_alias,
        }

        state_path = self._get_state_path()
        try:
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save state to {state_path}: {e}", file=sys.stderr)

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
            print(f"  Would save state to: {self.state_file}")

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

        # Load existing state for resume capability
        if self.resume:
            state = self._load_state()
            self._completed_steps = state.get("completed_steps", [])

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
                "resume": self.resume,
                "state_file": self.state_file,
                "completed_steps": self._completed_steps,
            }
        ))

        print(f"\n{'='*60}")
        print(f"  AUTOMATED PIPELINE: {self.domain}")
        print(f"  Base model: {self.base_model}")
        print(f"  Steps: {' → '.join(self.steps)}")
        if self.dry_run:
            print(f"  Mode: DRY RUN (preview only)")
        if self.resume:
            print(f"  State file: {self.state_file}")
            if self._completed_steps:
                print(f"  Resume: Skipping completed steps: {', '.join(self._completed_steps)}")
        print(f"{'='*60}\n")

        try:
            for step in self.steps:
                # Skip already-completed steps when resuming
                if step in self._completed_steps:
                    print(f"\n{'#'*60}")
                    print(f"# STEP: {step.upper()} [SKIPPED - already completed]")
                    print(f"{'#'*60}")
                    continue

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

                # Save state after successful step
                self._save_state(step)

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
    parser.add_argument("--no-resume", action="store_true", help="Disable resume from saved state")
    parser.add_argument("--state-file", help="Custom state file path")

    args = parser.parse_args()

    runner = PipelineRunner(
        domain=args.domain,
        base_model=args.base,
        epochs=args.epochs,
        dry_run=args.dry_run,
        emit_events=not args.no_events,
        resume=not args.no_resume,
        state_file=args.state_file,
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
