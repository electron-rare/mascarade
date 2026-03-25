"""P2P task handlers for fine-tuning agents."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("mascarade.finetune.p2p.handlers")


async def handle_ft_task(payload: dict[str, Any], capability: str) -> dict:
    """Route fine-tuning tasks to the appropriate agent."""
    payload.get("action", "")

    if capability == "ft-research":
        return await _handle_research(payload)
    elif capability == "ft-dataset":
        return await _handle_dataset(payload)
    elif capability == "ft-teacher":
        return await _handle_teacher(payload)
    elif capability == "ft-student":
        return await _handle_student(payload)
    elif capability == "ft-analysis":
        return await _handle_analysis(payload)
    elif capability == "ft-reinforcement":
        return await _handle_reinforcement(payload)
    elif capability == "ft-validation":
        return await _handle_validation(payload)
    elif capability == "ft-archive":
        return await _handle_archive(payload)

    return {"error": f"Unknown capability: {capability}"}


async def _handle_research(payload: dict) -> dict:
    from mascarade.finetune.agents.researcher import ResearcherAgent

    agent = ResearcherAgent(hf_token=payload.get("hf_token"))
    action = payload.get("action", "search_models")

    task = payload.get("task")
    if not task:
        return {"error": "Missing required field: task"}

    if action == "search_models":
        candidates = await agent.search_base_models(
            task,
            max_size_gb=payload.get("max_size_gb", 4.0),
        )
        return {"candidates": [c.__dict__ for c in candidates]}
    elif action == "search_papers":
        topic = payload.get("topic")
        if not topic:
            return {"error": "Missing required field: topic"}
        papers = await agent.search_papers(topic)
        return {"papers": [p.__dict__ for p in papers]}
    elif action == "recommend":
        return await agent.recommend(
            task,
            max_size_gb=payload.get("max_size_gb", 4.0),
        )
    return {"error": f"Unknown research action: {action}"}


async def _handle_dataset(payload: dict) -> dict:
    from mascarade.finetune.agents.documentalist import DocumentalistAgent

    agent = DocumentalistAgent(hf_token=payload.get("hf_token"))
    action = payload.get("action", "search")

    domain = payload.get("domain")
    if not domain and action in ("search", "recommend"):
        return {"error": "Missing required field: domain"}

    if action == "search":
        candidates = await agent.search_datasets(
            domain,
            languages=payload.get("languages"),
        )
        return {"candidates": [c.__dict__ for c in candidates]}
    elif action == "inspect":
        dataset_id = payload.get("dataset_id")
        if not dataset_id:
            return {"error": "Missing required field: dataset_id"}
        return await agent.inspect_dataset(dataset_id)
    elif action == "recommend":
        return await agent.recommend(
            domain,
            languages=payload.get("languages"),
        )
    return {"error": f"Unknown dataset action: {action}"}


async def _handle_teacher(payload: dict) -> dict:
    """Handle teacher data generation. Creates Router locally."""
    try:
        from mascarade.finetune.agents.teacher import TeacherAgent, TeacherConfig
        from mascarade.router import Router

        router = Router()
        if not router._providers:
            return {"error": "No LLM providers configured (check API keys)"}

        agent = TeacherAgent(router=router)
        action = payload.get("action", "generate")

        if action == "generate":
            prompts = payload.get("prompts")
            if not prompts:
                return {"error": "Missing required field: prompts"}
            config = TeacherConfig(
                task_description=payload.get(
                    "task_description", "Generate training data"
                ),
                output_format=payload.get("output_format", "chatml"),
                temperature=payload.get("temperature", 0.7),
            )
            output_path = payload.get(
                "output_path", "~/.mascarade/finetune/teacher/output.jsonl"
            )
            result = await agent.generate_from_prompts(prompts, config, output_path)
            return result
        elif action == "correct":
            errors = payload.get("errors")
            if not errors:
                return {"error": "Missing required field: errors"}
            config = TeacherConfig(
                task_description=payload.get(
                    "task_description", "Generate corrections"
                ),
            )
            output_path = payload.get(
                "output_path", "~/.mascarade/finetune/teacher/corrections.jsonl"
            )
            result = await agent.generate_corrections(errors, config, output_path)
            return result

        return {"error": f"Unknown teacher action: {action}"}
    except ImportError as e:
        return {"error": f"Teacher dependencies not available: {e}"}


async def _handle_student(payload: dict) -> dict:
    from mascarade.finetune.agents.student import LoRAConfig, StudentAgent

    agent = StudentAgent()
    action = payload.get("action", "train_lora")

    if action == "train_lora":
        base_model = payload.get("base_model")
        dataset_path = payload.get("dataset_path")
        if not base_model or not dataset_path:
            return {"error": "Missing required fields: base_model, dataset_path"}
        config = LoRAConfig(**payload.get("lora_config", {}))
        result = await agent.train_lora(
            base_model,
            dataset_path,
            config,
            run_id=payload.get("run_id"),
        )
        return result.__dict__
    elif action == "train_llamacpp":
        gguf_model = payload.get("gguf_model")
        dataset_path = payload.get("dataset_path")
        if not gguf_model or not dataset_path:
            return {"error": "Missing required fields: gguf_model, dataset_path"}
        result = await agent.train_llamacpp(
            gguf_model,
            dataset_path,
            run_id=payload.get("run_id"),
        )
        return result.__dict__
    return {"error": f"Unknown student action: {action}"}


async def _handle_analysis(payload: dict) -> dict:
    from mascarade.finetune.agents.analyst import AnalystAgent

    agent = AnalystAgent()

    model_id = payload.get("model_id")
    model_path = payload.get("model_path")
    test_data_path = payload.get("test_data_path")
    if not model_id or not model_path or not test_data_path:
        return {
            "error": "Missing required fields: model_id, model_path, test_data_path"
        }

    result = await agent.full_eval(model_id, model_path, test_data_path)
    return result.__dict__


async def _handle_reinforcement(payload: dict) -> dict:
    """Handle reinforcement (DPO) tasks. Creates Router + Teacher + Reinforcer locally."""
    try:
        from mascarade.finetune.agents.reinforcer import ReinforcerAgent
        from mascarade.finetune.agents.teacher import TeacherAgent
        from mascarade.router import Router

        action = payload.get("action", "collect_errors")

        if action == "collect_errors":
            router = Router()
            if not router._providers:
                return {"error": "No LLM providers configured (check API keys)"}

            teacher = TeacherAgent(router=router)
            agent = ReinforcerAgent(teacher=teacher)
            model_path = payload.get("model_path")
            test_prompts = payload.get("test_prompts")
            if not model_path or not test_prompts:
                return {"error": "Missing required fields: model_path, test_prompts"}
            errors = await agent.collect_errors(
                eval_report=payload.get("eval_report", {}),
                model_path=model_path,
                test_prompts=test_prompts,
            )
            return {"errors": errors, "total": len(errors)}
        elif action == "generate_dpo":
            errors = payload.get("errors") or []
            teacher = None
            if errors:
                router = Router()
                if not router._providers:
                    return {"error": "No LLM providers configured (check API keys)"}
                teacher = TeacherAgent(router=router)

            agent = ReinforcerAgent(teacher=teacher)
            result = await agent.generate_dpo_pairs(
                errors,
                run_id=payload.get("run_id"),
                persona=payload.get("persona"),
                project_id=payload.get("project_id"),
                federation_scope=payload.get("federation_scope"),
                knowledge_scope=payload.get("knowledge_scope", "project"),
                include_kxkm_feedback=payload.get("include_kxkm_feedback", True),
            )
            return result.__dict__

        return {"error": f"Unknown reinforcement action: {action}"}
    except ImportError as e:
        return {"error": f"Reinforcement dependencies not available: {e}"}


async def _handle_validation(payload: dict) -> dict:
    from mascarade.finetune.agents.validator import ValidatorAgent

    agent = ValidatorAgent()

    model_id = payload.get("model_id")
    model_path = payload.get("model_path")
    if not model_id or not model_path:
        return {"error": "Missing required fields: model_id, model_path"}

    result = await agent.validate(
        model_id,
        model_path,
        previous_model_path=payload.get("previous_model_path"),
        test_prompts=payload.get("test_prompts"),
    )
    return result.__dict__


async def _handle_archive(payload: dict) -> dict:
    from mascarade.finetune.agents.archivist import ArchivistAgent

    agent = ArchivistAgent(hf_token=payload.get("hf_token"))
    action = payload.get("action", "push_model")

    local_path = payload.get("local_path")
    if not local_path:
        return {"error": "Missing required field: local_path"}

    if action == "push_dataset":
        domain = payload.get("domain")
        if not domain:
            return {"error": "Missing required field: domain"}
        result = await agent.push_dataset(
            local_path,
            domain,
            version=payload.get("version"),
        )
        return result.__dict__
    elif action == "push_model":
        task = payload.get("task")
        size_label = payload.get("size_label")
        if not task or not size_label:
            return {"error": "Missing required fields: task, size_label"}
        result = await agent.push_model(
            local_path,
            task,
            size_label,
            version=payload.get("version"),
        )
        return result.__dict__
    return {"error": f"Unknown archive action: {action}"}
