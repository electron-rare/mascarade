"""RAGAS-inspired RAG evaluation pipeline.

Computes 5 standard metrics against a golden dataset (question + ground truth):
    - Faithfulness          claims in answer supported by retrieved context
    - Answer Relevance      does the answer actually address the question
    - Context Precision     relevant chunks are ranked at the top
    - Context Recall        all needed information was retrieved
    - Hallucination Rate    answers not grounded in context (1 - Faithfulness)

These metrics do NOT require ragas package — implemented via LLM judges so
mascarade's existing router is used directly. Compatible with RAGAS v0.4 semantics.

Usage::

    from mascarade.rag.eval import RAGEvaluator
    evaluator = RAGEvaluator(pipeline)
    report = await evaluator.evaluate(golden_dataset)

Golden dataset format (list of dicts)::

    [
      {
        "question": "What is the voltage of the ESP32-S3 GPIO?",
        "ground_truth": "3.3V",
        "answer": "...",          # optional — filled by pipeline if absent
        "contexts": ["..."],      # optional — filled by pipeline if absent
      },
      ...
    ]
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mascarade.rag.pipeline import RAGPipeline

logger = logging.getLogger("mascarade.rag.eval")

# Production thresholds (from RAGAS docs)
THRESHOLDS = {
    "faithfulness": 0.85,
    "answer_relevance": 0.75,
    "context_precision": 0.70,
    "context_recall": 0.75,
    "hallucination_rate": 0.05,  # max acceptable
}

# ------------------------------------------------------------------
# LLM judge prompts
# ------------------------------------------------------------------

_FAITHFULNESS_PROMPT = """\
Given the following context and answer, identify each claim in the answer
and determine if it is supported by the context.
Reply with ONLY a float between 0.0 and 1.0 representing the fraction of
claims supported by the context (1.0 = all claims supported).

Context:
{context}

Answer:
{answer}

Faithfulness score (0.0-1.0):"""

_RELEVANCE_PROMPT = """\
Given the following question and answer, rate how well the answer addresses
the question. Consider completeness and directness.
Reply with ONLY a float between 0.0 and 1.0 (1.0 = perfectly relevant).

Question: {question}
Answer: {answer}

Answer relevance score (0.0-1.0):"""

_CONTEXT_RECALL_PROMPT = """\
Given the following question, ground truth answer, and retrieved context,
determine what fraction of the information needed to answer the question
is present in the context.
Reply with ONLY a float between 0.0 and 1.0 (1.0 = all needed info present).

Question: {question}
Ground truth: {ground_truth}
Context:
{context}

Context recall score (0.0-1.0):"""

_CONTEXT_PRECISION_PROMPT = """\
Given the following question and retrieved contexts (numbered), rate
how many of the top contexts are actually relevant to answering the question.
Consider that relevant contexts should be ranked before irrelevant ones.
Reply with ONLY a float between 0.0 and 1.0 (1.0 = all top contexts relevant).

Question: {question}
Contexts:
{contexts_numbered}

Context precision score (0.0-1.0):"""


class RAGEvaluator:
    """Evaluate a RAGPipeline against a golden dataset using LLM judges."""

    def __init__(
        self,
        pipeline: RAGPipeline,
        *,
        judge_provider: str | None = None,
        judge_model: str | None = None,
        concurrency: int = 4,
    ) -> None:
        self.pipeline = pipeline
        self.judge_provider = judge_provider
        self.judge_model = judge_model
        self.concurrency = concurrency

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        golden_dataset: list[dict[str, Any]],
        *,
        run_pipeline: bool = True,
    ) -> dict[str, Any]:
        """Evaluate against golden dataset.

        Args:
            golden_dataset: list of {question, ground_truth, answer?, contexts?}
            run_pipeline: if True, run the RAG pipeline for items missing answer/contexts

        Returns:
            {metrics: {faithfulness, answer_relevance, ...}, per_item: [...], summary: str}
        """
        t0 = time.monotonic()
        logger.info("RAG eval: %d items, concurrency=%d", len(golden_dataset), self.concurrency)

        # Optionally run pipeline to fill missing answers/contexts
        if run_pipeline:
            golden_dataset = await self._fill_pipeline_outputs(golden_dataset)

        # Evaluate with concurrency limit
        sem = asyncio.Semaphore(self.concurrency)
        tasks = [self._eval_item(item, sem) for item in golden_dataset]
        per_item = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter exceptions
        results = []
        errors = 0
        for r in per_item:
            if isinstance(r, Exception):
                logger.warning("Eval item failed: %s", r)
                errors += 1
            else:
                results.append(r)

        if not results:
            return {"error": "All eval items failed", "errors": errors}

        # Aggregate metrics
        metrics = self._aggregate(results)
        elapsed = time.monotonic() - t0

        # Status: pass/fail per threshold
        status = {
            k: (
                "PASS"
                if (v >= THRESHOLDS[k] if k != "hallucination_rate" else v <= THRESHOLDS[k])
                else "FAIL"
            )
            for k, v in metrics.items()
            if k in THRESHOLDS
        }
        overall = "PASS" if all(s == "PASS" for s in status.values()) else "FAIL"

        return {
            "metrics": metrics,
            "thresholds": THRESHOLDS,
            "status": status,
            "overall": overall,
            "per_item": results,
            "n_items": len(results),
            "n_errors": errors,
            "elapsed_seconds": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # Per-item eval
    # ------------------------------------------------------------------

    async def _eval_item(self, item: dict[str, Any], sem: asyncio.Semaphore) -> dict[str, Any]:
        async with sem:
            question = item.get("question", "")
            ground_truth = item.get("ground_truth", "")
            answer = item.get("answer", "")
            contexts: list[str] = item.get("contexts", [])

            if not answer or not contexts:
                return {"question": question, "error": "missing answer or contexts"}

            context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
            contexts_numbered = "\n".join(f"[{i+1}] {c[:200]}" for i, c in enumerate(contexts))

            # Run 4 LLM judge calls concurrently
            faithfulness, relevance, recall, precision = await asyncio.gather(
                self._score(_FAITHFULNESS_PROMPT.format(context=context_str, answer=answer)),
                self._score(_RELEVANCE_PROMPT.format(question=question, answer=answer)),
                self._score(
                    _CONTEXT_RECALL_PROMPT.format(
                        question=question, ground_truth=ground_truth, context=context_str
                    )
                ),
                self._score(
                    _CONTEXT_PRECISION_PROMPT.format(
                        question=question, contexts_numbered=contexts_numbered
                    )
                ),
                return_exceptions=True,
            )

            def _safe(v: float | Exception, default: float = 0.0) -> float:
                return float(v) if not isinstance(v, Exception) else default

            faith = _safe(faithfulness)
            rel = _safe(relevance)
            rec = _safe(recall)
            prec = _safe(precision)

            return {
                "question": question,
                "faithfulness": faith,
                "answer_relevance": rel,
                "context_recall": rec,
                "context_precision": prec,
                "hallucination_rate": 1.0 - faith,
            }

    async def _score(self, prompt: str) -> float:
        """Ask LLM judge to score, return float 0.0-1.0."""
        resp = await self.pipeline.router.send(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=16,
            provider=self.judge_provider,
            model=self.judge_model,
        )
        raw = resp.text.strip()
        # Parse first float found
        for token in raw.replace(",", ".").split():
            try:
                v = float(token)
                return max(0.0, min(1.0, v))
            except ValueError:
                continue
        logger.debug("Could not parse score from %r", raw)
        return 0.0

    # ------------------------------------------------------------------
    # Pipeline run
    # ------------------------------------------------------------------

    async def _fill_pipeline_outputs(self, dataset: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run RAG pipeline for items missing answer or contexts."""
        sem = asyncio.Semaphore(self.concurrency)

        async def _run(item: dict[str, Any]) -> dict[str, Any]:
            if item.get("answer") and item.get("contexts"):
                return item
            async with sem:
                try:
                    result = await self.pipeline.query(
                        item["question"],
                        skip_classification=True,
                    )
                    return {
                        **item,
                        "answer": result.get("answer", ""),
                        "contexts": [s.get("text", "") for s in result.get("sources", [])],
                    }
                except Exception as exc:
                    logger.warning("Pipeline run failed for eval item: %s", exc)
                    return {**item, "answer": "", "contexts": []}

        return await asyncio.gather(*[_run(item) for item in dataset])  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(self, results: list[dict[str, Any]]) -> dict[str, float]:
        keys = [
            "faithfulness",
            "answer_relevance",
            "context_recall",
            "context_precision",
            "hallucination_rate",
        ]
        totals: dict[str, float] = dict.fromkeys(keys, 0.0)
        for r in results:
            for k in keys:
                totals[k] += r.get(k, 0.0)
        n = len(results)
        return {k: round(v / n, 4) for k, v in totals.items()}
