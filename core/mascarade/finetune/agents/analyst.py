"""Analyst agent — evaluates fine-tuned models with benchmarks and metrics."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.analyst")


@dataclass
class BenchmarkResult:
    model_id: str
    benchmark: str
    score: float
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class EvalReport:
    model_id: str
    perplexity: float = 0.0
    accuracy: float = 0.0
    tokens_per_second: float = 0.0
    memory_mb: float = 0.0
    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    comparison: dict = field(default_factory=dict)  # vs baseline/teacher


class AnalystAgent:
    """Evaluates fine-tuned models against benchmarks.

    Compares student output vs teacher vs baseline on:
    - Perplexity on test set
    - Task-specific accuracy
    - Inference speed (tokens/s)
    - Memory footprint

    P2P capability: ft-analysis
    """

    def __init__(self, *, output_dir: Path | str = "~/.mascarade/finetune/evals"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def evaluate_perplexity(
        self,
        model_path: str,
        test_data_path: str,
    ) -> float:
        """Calculate perplexity on a test set using llama.cpp perplexity tool."""
        import subprocess
        if not shutil.which("llama-perplexity"):
            logger.warning("llama-perplexity not found in PATH")
            return 0.0
        try:
            result = subprocess.run(
                ["llama-perplexity", "--model", model_path, "--file", test_data_path,
                 "--ctx-size", "2048", "--threads", "4"],
                capture_output=True, text=True, timeout=3600,
            )
            # Parse perplexity from output
            for line in result.stdout.split("\n"):
                if "perplexity" in line.lower() and "=" in line:
                    try:
                        return float(line.split("=")[-1].strip())
                    except ValueError:
                        pass
            return 0.0
        except Exception as e:
            logger.warning("Perplexity eval failed: %s", e)
            return 0.0

    async def evaluate_inference_speed(
        self,
        model_path: str,
        prompt: str = "Explain quantum computing in simple terms.",
        n_tokens: int = 256,
    ) -> dict:
        """Measure inference speed using llama.cpp."""
        import subprocess
        if not shutil.which("llama-cli"):
            return {"error": "llama-cli not found in PATH"}
        start = time.time()
        try:
            result = subprocess.run(
                ["llama-cli", "--model", model_path, "--prompt", prompt,
                 "--n-predict", str(n_tokens), "--threads", "4", "--no-display-prompt"],
                capture_output=True, text=True, timeout=120,
            )
            elapsed = time.time() - start
            output_tokens = len(result.stdout.split())
            return {
                "tokens_generated": output_tokens,
                "time_seconds": round(elapsed, 2),
                "tokens_per_second": round(output_tokens / elapsed, 1) if elapsed > 0 else 0,
            }
        except Exception as e:
            return {"error": str(e)}

    async def compare_models(
        self,
        models: dict[str, str],  # {"student": path, "baseline": path}
        test_prompts: list[str],
    ) -> dict:
        """Compare multiple models on the same prompts."""
        results = {}
        for name, path in models.items():
            speeds = []
            for prompt in test_prompts[:5]:
                speed = await self.evaluate_inference_speed(path, prompt=prompt)
                speeds.append(speed)
            avg_tps = sum(s.get("tokens_per_second", 0) for s in speeds) / max(len(speeds), 1)
            results[name] = {
                "avg_tokens_per_second": round(avg_tps, 1),
                "samples": speeds,
            }
        return results

    async def full_eval(
        self,
        model_id: str,
        model_path: str,
        test_data_path: str,
    ) -> EvalReport:
        """Run full evaluation suite."""
        logger.info("Starting full eval for %s", model_id)

        ppl = await self.evaluate_perplexity(model_path, test_data_path)
        speed = await self.evaluate_inference_speed(model_path)

        report = EvalReport(
            model_id=model_id,
            perplexity=ppl,
            tokens_per_second=speed.get("tokens_per_second", 0),
        )

        # Save report
        report_path = self.output_dir / f"{model_id.replace('/', '_')}_eval.json"
        report_path.write_text(json.dumps(asdict(report), indent=2, default=str))
        logger.info("Eval complete for %s: ppl=%.2f tps=%.1f", model_id, ppl, report.tokens_per_second)
        return report
