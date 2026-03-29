"""Fine-tuning orchestrator — coordinates the full pipeline across P2P mesh."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from mascarade.finetune.agents.teacher import TeacherAgent, TeacherConfig
from mascarade.finetune.registry import (
    DatasetEntry,
    FinetuneRegistry,
    ModelEntry,
    RunEntry,
)

logger = logging.getLogger("mascarade.finetune.orchestrator")


@dataclass
class PipelineConfig:
    task: str  # e.g. "text-generation", "code", "kicad"
    domain: str  # e.g. "electronics", "french-chat"
    max_model_size_gb: float = 4.0
    languages: list[str] = field(default_factory=lambda: ["en", "fr"])
    lora_config: dict = field(default_factory=dict)
    dpo_iterations: int = 1
    alignment_method: str = "simpo"  # "simpo", "dpo", "kto", or "rlvr"
    auto_publish: bool = False


@dataclass
class PipelineState:
    config: PipelineConfig
    phase: str = (
        "init"  # init, research, dataset, teacher, training, eval, dpo, validation, publish
    )
    model_candidates: list[dict] = field(default_factory=list)
    selected_model: str = ""
    dataset_candidates: list[dict] = field(default_factory=list)
    selected_dataset: str = ""
    teacher_data_path: str = ""
    training_result: dict = field(default_factory=dict)
    eval_report: dict = field(default_factory=dict)
    validation_result: dict = field(default_factory=dict)
    published_model: str = ""
    errors: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)


class FinetuneOrchestrator:
    """Orchestrates the full fine-tuning pipeline.

    Distributes tasks to P2P nodes based on capabilities:
    1. Research → find base model + papers (ft-research)
    2. Dataset → find/create dataset (ft-dataset)
    3. Teacher → generate training data (ft-teacher)
    4. Archive → version on HuggingFace (ft-archive)
    5. Student → fine-tune LoRA (ft-student)
    6. Analyst → benchmark + metrics (ft-analysis)
    7. Reinforcer → DPO on errors (ft-reinforcement)
    8. Validator → e2e + red-team (ft-validation)
    9. Archive → publish final model (ft-archive)
    """

    def __init__(self, *, node=None, router=None, registry: FinetuneRegistry | None = None):
        self.node = node  # MascaradeP2PNode
        self.router = router
        self.registry = registry or FinetuneRegistry()

    async def run_pipeline(self, config: PipelineConfig) -> PipelineState:
        """Execute the full pipeline end-to-end."""
        state = PipelineState(config=config)
        logger.info(
            "Starting fine-tuning pipeline: task=%s domain=%s",
            config.task,
            config.domain,
        )

        try:
            # Phase 1: Research
            state.phase = "research"
            state = await self._phase_research(state)

            # Phase 2: Dataset
            state.phase = "dataset"
            state = await self._phase_dataset(state)

            # Phase 3: Teacher data generation
            state.phase = "teacher"
            state = await self._phase_teacher(state)

            # Phase 4: Training
            state.phase = "training"
            state = await self._phase_training(state)

            # Phase 5: Evaluation
            state.phase = "eval"
            state = await self._phase_eval(state)

            # Phase 6: Alignment — DPO/SimPO/KTO (optional iterations)
            for i in range(config.dpo_iterations):
                state.phase = f"alignment-{config.alignment_method}-{i+1}"
                state = await self._phase_dpo(state)

            # Phase 7: Validation
            state.phase = "validation"
            state = await self._phase_validation(state)

            # Phase 8: Publish
            if config.auto_publish and state.validation_result.get("passed"):
                state.phase = "publish"
                state = await self._phase_publish(state)

            state.phase = "complete"
            logger.info(
                "Pipeline complete for %s/%s in %.0fs",
                config.task,
                config.domain,
                time.time() - state.started_at,
            )

        except Exception as e:
            state.errors.append(f"Pipeline failed at phase {state.phase}: {e}")
            logger.exception("Pipeline failed at phase %s", state.phase)

        return state

    async def _distribute(self, capability: str, payload: dict) -> dict:
        """Distribute a task to the appropriate P2P node."""
        if self.node is None:
            raise RuntimeError("Orchestrator requires a P2P node for task distribution")
        return await self.node.distribute_task(payload=payload, capability=capability, timeout=600)

    async def _phase_research(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Research — searching for base models")
        result = await self._distribute(
            "ft-research",
            {
                "action": "recommend",
                "task": state.config.task,
                "max_size_gb": state.config.max_model_size_gb,
            },
        )
        state.model_candidates = result.get("candidates", [])
        if state.model_candidates:
            state.selected_model = state.model_candidates[0]["model_id"]
            self.registry.add_model(
                ModelEntry(
                    model_id=state.selected_model,
                    source="huggingface",
                    task=state.config.task,
                    size_gb=state.model_candidates[0].get("size_gb", 0),
                    license=state.model_candidates[0].get("license", ""),
                    downloads=state.model_candidates[0].get("downloads", 0),
                )
            )
            logger.info("Selected model: %s", state.selected_model)
        else:
            raise RuntimeError("No model candidates found — cannot proceed")
        return state

    async def _phase_dataset(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Dataset — searching for training data")
        result = await self._distribute(
            "ft-dataset",
            {
                "action": "recommend",
                "domain": state.config.domain,
                "languages": state.config.languages,
            },
        )
        state.dataset_candidates = result.get("candidates", [])
        if state.dataset_candidates:
            state.selected_dataset = state.dataset_candidates[0]["dataset_id"]
            self.registry.add_dataset(
                DatasetEntry(
                    dataset_id=state.selected_dataset,
                    source="huggingface",
                    domain=state.config.domain,
                    license=state.dataset_candidates[0].get("license", ""),
                )
            )
            logger.info("Selected dataset: %s", state.selected_dataset)
        else:
            raise RuntimeError("No dataset candidates found — cannot proceed")
        return state

    async def _phase_teacher(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Teacher — generating training data")
        if self.router is None:
            logger.warning("No Router available, skipping teacher data generation")
            return state

        teacher = TeacherAgent(router=self.router)
        config = TeacherConfig(
            task_description=f"Generate high-quality {state.config.domain} training data",
        )

        # Generate prompts from dataset description
        prompts = [
            f"Write a {state.config.domain} example with clear instruction and response.",
            f"Create a challenging {state.config.domain} task with a detailed solution.",
            f"Generate a {state.config.domain} question that tests understanding.",
        ]

        output_path = Path(
            f"~/.mascarade/finetune/teacher/{state.config.domain}/train.jsonl"
        ).expanduser()
        try:
            result = await teacher.generate_from_prompts(prompts, config, output_path)
            state.teacher_data_path = result["output_path"]
            logger.info(
                "Teacher generated %d samples → %s",
                result["total"],
                state.teacher_data_path,
            )
        except Exception as e:
            state.errors.append(f"Teacher data generation failed: {e}")
            logger.warning("Teacher phase failed: %s", e)

        return state

    async def _phase_training(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Training — fine-tuning on %s", state.selected_model)
        result = await self._distribute(
            "ft-student",
            {
                "action": "train_lora",
                "base_model": state.selected_model,
                "dataset_path": state.selected_dataset,
                "lora_config": state.config.lora_config,
            },
        )
        state.training_result = result
        run_id = result.get("output_dir", "").split("/")[-1] or f"run-{int(time.time())}"
        failed = bool(result.get("error"))
        self.registry.add_run(
            RunEntry(
                run_id=run_id,
                base_model=state.selected_model,
                dataset=state.selected_dataset,
                method=result.get("method", "lora"),
                node="ft-student",
                status="failed" if failed else "completed",
                metrics=result.get("metrics", {}),
            )
        )
        if failed:
            raise RuntimeError(f"Training failed: {result.get('error')}")
        return state

    async def _phase_eval(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Evaluation")
        model_path = state.training_result.get("output_dir", "")
        if model_path:
            result = await self._distribute(
                "ft-analysis",
                {
                    "model_id": state.selected_model,
                    "model_path": model_path,
                    "test_data_path": state.selected_dataset,
                },
            )
            state.eval_report = result
        return state

    async def _phase_dpo(self, state: PipelineState) -> PipelineState:
        alignment_method = state.config.alignment_method
        logger.info("Phase: %s alignment (%s)", alignment_method.upper(), state.phase)

        # 1. Check prerequisites: eval_report must exist with data
        if not state.eval_report or not state.eval_report.get("metrics"):
            logger.warning("%s skipped — no eval report available", alignment_method.upper())
            state.errors.append(f"{alignment_method} phase {state.phase} skipped: no eval report")
            return state

        model_path = state.training_result.get("output_dir", "")
        if not model_path:
            logger.warning("%s skipped — no trained model path", alignment_method.upper())
            state.errors.append(f"{alignment_method} phase {state.phase} skipped: no model path")
            return state

        # Build test prompts from domain context
        test_prompts = [
            f"Write a {state.config.domain} example with clear instruction and response.",
            f"Create a challenging {state.config.domain} task with a detailed solution.",
            f"Generate a {state.config.domain} question that tests understanding.",
        ]

        try:
            # 2. Distribute collect_errors task to ft-reinforcement capability
            logger.info(
                "%s: collecting errors from model at %s",
                alignment_method.upper(),
                model_path,
            )
            error_result = await self._distribute(
                "ft-reinforcement",
                {
                    "action": "collect_errors",
                    "model_path": model_path,
                    "test_prompts": test_prompts,
                    "eval_report": state.eval_report,
                },
            )

            errors = error_result.get("errors", [])
            if not errors:
                logger.info(
                    "%s: no errors found, model looks good — skipping",
                    alignment_method.upper(),
                )
                return state

            # 3. Distribute alignment data generation task
            logger.info(
                "%s: generating training data from %d errors",
                alignment_method.upper(),
                len(errors),
            )
            alignment_result = await self._distribute(
                "ft-reinforcement",
                {
                    "action": "generate_dpo",
                    "errors": errors,
                    "run_id": f"{alignment_method}-{state.config.domain}-{state.phase}",
                    "alignment_method": alignment_method,
                },
            )

            alignment_dataset_path = alignment_result.get("dataset_path", "")
            total_pairs = alignment_result.get("total_pairs", 0)
            logger.info(
                "%s: generated %d examples → %s",
                alignment_method.upper(),
                total_pairs,
                alignment_dataset_path,
            )

            if not alignment_dataset_path or total_pairs <= 0:
                logger.warning(
                    "%s: no alignment dataset produced, skipping training",
                    alignment_method.upper(),
                )
                state.errors.append(
                    f"{alignment_method} phase {state.phase} skipped: no alignment dataset"
                )
                return state

            # 4. Run the actual alignment training on the reinforcement capability.
            logger.info(
                "%s: training aligned model from %s",
                alignment_method.upper(),
                alignment_dataset_path,
            )
            train_result = await self._distribute(
                "ft-reinforcement",
                {
                    "action": "train_alignment",
                    "model_path": model_path,
                    "dataset_path": alignment_dataset_path,
                    "method": alignment_method,
                    "run_id": f"{alignment_method}-{state.config.domain}-{state.phase}",
                },
            )

            if train_result.get("error"):
                raise RuntimeError(train_result["error"])

            # 5. Update state with alignment results and promote the aligned model path
            state.training_result["alignment_dataset"] = alignment_dataset_path
            state.training_result["alignment_pairs"] = total_pairs
            state.training_result["alignment_method"] = alignment_method
            state.training_result["alignment_training"] = train_result
            state.training_result["base_output_dir"] = model_path
            state.training_result["output_dir"] = train_result.get(
                "model_path",
                train_result.get("output_dir", model_path),
            )
            state.eval_report[f"alignment_{state.phase}"] = {
                "method": alignment_method,
                "errors_found": len(errors),
                "pairs_generated": total_pairs,
                "dataset_path": alignment_dataset_path,
                "training_output_dir": train_result.get("output_dir", ""),
                "aligned_model_path": train_result.get("model_path", ""),
            }

        except Exception as e:
            state.errors.append(f"{alignment_method} phase {state.phase} failed: {e}")
            logger.warning("%s phase %s failed: %s", alignment_method.upper(), state.phase, e)

        return state

    async def _phase_validation(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Validation")
        model_path = state.training_result.get("output_dir", "")
        if model_path:
            result = await self._distribute(
                "ft-validation",
                {
                    "model_id": state.selected_model,
                    "model_path": model_path,
                },
            )
            state.validation_result = result
        return state

    async def _phase_publish(self, state: PipelineState) -> PipelineState:
        logger.info("Phase: Publish to HuggingFace")
        model_path = state.training_result.get("output_dir", "")
        if model_path:
            actual_size = (
                state.model_candidates[0].get("size_gb", state.config.max_model_size_gb)
                if state.model_candidates
                else state.config.max_model_size_gb
            )
            result = await self._distribute(
                "ft-archive",
                {
                    "action": "push_model",
                    "local_path": model_path,
                    "task": state.config.task,
                    "size_label": f"{actual_size:.0f}B",
                },
            )
            state.published_model = result.get("repo_id", "")
            logger.info("Published: %s", state.published_model)
        return state
