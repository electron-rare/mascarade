"""Tests for the finetune module — imports, registry, and agent logic."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.config import settings
from mascarade.finetune.agents.analyst import AnalystAgent
from mascarade.finetune.agents.archivist import ArchivistAgent
from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.reinforcer import (
    DPOPair,
    ReinforcementResult,
    ReinforcerAgent,
)
from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.agents.student import LoRAConfig, StudentAgent
from mascarade.finetune.agents.teacher import TeacherAgent
from mascarade.finetune.agents.validator import ValidatorAgent
from mascarade.finetune.orchestrator import (
    FinetuneOrchestrator,
    PipelineConfig,
    PipelineState,
)
from mascarade.finetune.p2p.capabilities import CAPABILITY_NODE_MAP, FT_CAPABILITIES
from mascarade.finetune.p2p.task_handlers import handle_ft_task
from mascarade.finetune.registry import (
    DatasetEntry,
    FinetuneRegistry,
    ModelEntry,
    RunEntry,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class TestImports:
    def test_all_agents_importable(self):
        """All 8 agents import cleanly."""
        assert ResearcherAgent is not None
        assert DocumentalistAgent is not None
        assert TeacherAgent is not None
        assert ArchivistAgent is not None
        assert StudentAgent is not None
        assert AnalystAgent is not None
        assert ReinforcerAgent is not None
        assert ValidatorAgent is not None

    def test_orchestrator_importable(self):
        assert FinetuneOrchestrator is not None
        assert PipelineConfig is not None

    def test_capabilities_defined(self):
        assert len(FT_CAPABILITIES) == 8
        expected = {
            "ft-research",
            "ft-dataset",
            "ft-archive",
            "ft-analysis",
            "ft-teacher",
            "ft-student",
            "ft-reinforcement",
            "ft-validation",
        }
        assert set(FT_CAPABILITIES.keys()) == expected

    def test_capability_node_map_complete(self):
        for cap in FT_CAPABILITIES:
            assert cap in CAPABILITY_NODE_MAP, f"Missing node mapping for {cap}"
            assert len(CAPABILITY_NODE_MAP[cap]) > 0


class TestRegistry:
    def test_create_empty_registry(self, tmp_path):
        reg = FinetuneRegistry(tmp_path / "reg.json")
        assert len(reg.models) == 0
        assert len(reg.datasets) == 0
        assert len(reg.runs) == 0

    def test_add_model_persists(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = FinetuneRegistry(path)
        reg.add_model(
            ModelEntry(
                model_id="test/model-1",
                source="huggingface",
                task="code",
                size_gb=1.5,
                license="apache-2.0",
            )
        )
        assert "test/model-1" in reg.models
        assert path.exists()

        # Reload
        reg2 = FinetuneRegistry(path)
        assert "test/model-1" in reg2.models
        assert reg2.models["test/model-1"].license == "apache-2.0"

    def test_add_dataset_persists(self, tmp_path):
        reg = FinetuneRegistry(tmp_path / "reg.json")
        reg.add_dataset(
            DatasetEntry(
                dataset_id="test/ds-1",
                source="huggingface",
                domain="code",
                rows=5000,
                license="mit",
            )
        )
        assert "test/ds-1" in reg.datasets

    def test_add_run(self, tmp_path):
        reg = FinetuneRegistry(tmp_path / "reg.json")
        reg.add_run(
            RunEntry(
                run_id="run-001",
                base_model="test/m",
                dataset="test/d",
                method="qlora-4bit",
                node="KXKM",
                status="completed",
                metrics={"loss": 1.5},
            )
        )
        assert "run-001" in reg.runs
        assert reg.runs["run-001"].status == "completed"

    def test_best_model_for_task(self, tmp_path):
        reg = FinetuneRegistry(tmp_path / "reg.json")
        reg.add_model(
            ModelEntry(
                model_id="big/model",
                source="hf",
                task="code",
                size_gb=10.0,
                downloads=1000,
            )
        )
        reg.add_model(
            ModelEntry(
                model_id="small/model",
                source="hf",
                task="code",
                size_gb=1.0,
                downloads=500,
            )
        )
        best = reg.best_model_for_task("code", max_size_gb=4.0)
        assert best is not None
        assert best.model_id == "small/model"

    def test_best_model_none_when_no_match(self, tmp_path):
        reg = FinetuneRegistry(tmp_path / "reg.json")
        assert reg.best_model_for_task("nonexistent") is None


class TestAgentLogic:
    def test_researcher_init(self):
        agent = ResearcherAgent(hf_token="test")
        assert agent.hf_token == "test"

    def test_documentalist_init(self):
        agent = DocumentalistAgent()
        assert agent.hf_token is None

    def test_teacher_requires_router(self):
        agent = TeacherAgent()
        assert agent.router is None

    def test_student_output_dir(self, tmp_path):
        agent = StudentAgent(output_base=tmp_path)
        assert agent.output_base == tmp_path

    def test_lora_config_defaults(self):
        config = LoRAConfig()
        assert config.r == 16
        assert config.lora_alpha == 32
        assert config.quantization == "4bit"

    def test_validator_red_team_prompts(self):
        from mascarade.finetune.agents.validator import RED_TEAM_PROMPTS

        assert len(RED_TEAM_PROMPTS) >= 5

    def test_reinforcer_repetition_check(self):
        assert ReinforcerAgent._is_repetitive(
            "the the the the the the the the the the the the"
        )
        assert not ReinforcerAgent._is_repetitive(
            "This is a normal sentence with varied words and good content."
        )

    def test_teacher_format_chatml(self):
        entry = TeacherAgent._format_entry("prompt", "response", "chatml")
        assert "messages" in entry
        assert len(entry["messages"]) == 2
        assert entry["messages"][0]["role"] == "user"

    def test_teacher_format_alpaca(self):
        entry = TeacherAgent._format_entry("prompt", "response", "alpaca")
        assert "instruction" in entry
        assert entry["output"] == "response"

    def test_teacher_format_sharegpt(self):
        entry = TeacherAgent._format_entry("prompt", "response", "sharegpt")
        assert "conversations" in entry


class TestOrchestrator:
    def test_pipeline_config(self):
        config = PipelineConfig(task="code", domain="code-gen")
        assert config.max_model_size_gb == 4.0
        assert config.dpo_iterations == 1

    def test_pipeline_state_init(self):
        config = PipelineConfig(task="test", domain="test")
        state = PipelineState(config=config)
        assert state.phase == "init"
        assert state.errors == []

    def test_orchestrator_no_node(self):
        orch = FinetuneOrchestrator()
        assert orch.node is None

    def test_orchestrator_accepts_router(self):
        orch = FinetuneOrchestrator(router="fake_router")
        assert orch.router == "fake_router"

    def test_orchestrator_default_router_none(self):
        orch = FinetuneOrchestrator()
        assert orch.router is None


class TestTaskHandlers:
    @pytest.mark.asyncio
    async def test_unknown_capability(self):
        result = await handle_ft_task({"action": "test"}, "ft-unknown")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_teacher_no_prompts(self):
        result = await handle_ft_task({"action": "generate"}, "ft-teacher")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_reinforcement_needs_injection(self):
        result = await handle_ft_task({"action": "generate"}, "ft-reinforcement")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_missing_task(self):
        result = await handle_ft_task({"action": "search_models"}, "ft-research")
        assert "error" in result
        assert "task" in result["error"]

    @pytest.mark.asyncio
    async def test_dataset_missing_domain(self):
        result = await handle_ft_task({"action": "search"}, "ft-dataset")
        assert "error" in result
        assert "domain" in result["error"]

    @pytest.mark.asyncio
    async def test_student_missing_fields(self):
        result = await handle_ft_task({"action": "train_lora"}, "ft-student")
        assert "error" in result
        assert "base_model" in result["error"]

    @pytest.mark.asyncio
    async def test_analysis_missing_fields(self):
        result = await handle_ft_task({"action": "eval"}, "ft-analysis")
        assert "error" in result
        assert "model_id" in result["error"]

    @pytest.mark.asyncio
    async def test_validation_missing_fields(self):
        result = await handle_ft_task({"action": "validate"}, "ft-validation")
        assert "error" in result
        assert "model_id" in result["error"]

    @pytest.mark.asyncio
    async def test_archive_missing_local_path(self):
        result = await handle_ft_task({"action": "push_model"}, "ft-archive")
        assert "error" in result
        assert "local_path" in result["error"]

    @pytest.mark.asyncio
    async def test_reinforcement_collect_no_model(self):
        result = await handle_ft_task({"action": "collect_errors"}, "ft-reinforcement")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_reinforcement_dpo_no_errors_uses_kxkm_feedback(self, monkeypatch):
        expected = ReinforcementResult("/tmp/dpo.jsonl", total_pairs=2)

        async def fake_generate(self, errors, **kwargs):
            assert errors == []
            assert kwargs["include_kxkm_feedback"] is True
            return expected

        monkeypatch.setattr(
            "mascarade.finetune.agents.reinforcer.ReinforcerAgent.generate_dpo_pairs",
            fake_generate,
        )

        result = await handle_ft_task(
            {
                "action": "generate_dpo",
                "run_id": "run-kxkm-dpo",
                "persona": "pharmacius",
                "project_id": "project-alpha",
            },
            "ft-reinforcement",
        )
        assert result["dataset_path"] == "/tmp/dpo.jsonl"
        assert result["total_pairs"] == 2


class TestRegistryAtomicSave:
    def test_atomic_save_creates_file(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = FinetuneRegistry(path)
        reg.add_model(
            ModelEntry(
                model_id="test/m",
                source="hf",
                task="code",
                size_gb=1.0,
            )
        )
        assert path.exists()
        # Ensure no .tmp file lingers
        assert not path.with_suffix(".tmp").exists()

    def test_save_reload_consistency(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = FinetuneRegistry(path)
        reg.add_model(ModelEntry(model_id="m1", source="hf", task="code", size_gb=1.0))
        reg.add_dataset(DatasetEntry(dataset_id="d1", source="hf", domain="code"))
        reg.add_run(
            RunEntry(
                run_id="r1", base_model="m1", dataset="d1", method="lora", node="test"
            )
        )

        reg2 = FinetuneRegistry(path)
        assert "m1" in reg2.models
        assert "d1" in reg2.datasets
        assert "r1" in reg2.runs
        assert reg2.runs["r1"].method == "lora"

    def test_malformed_json_recovery(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text("not valid json {{{")
        reg = FinetuneRegistry(path)
        assert len(reg.models) == 0  # Silently recovers


class TestStudentBackend:
    def test_backend_auto_default(self):
        config = LoRAConfig()
        assert config.backend == "auto"

    def test_backend_field_exists(self):
        config = LoRAConfig(backend="trl")
        assert config.backend == "trl"

    def test_backend_unsloth_explicit(self):
        config = LoRAConfig(backend="unsloth")
        assert config.backend == "unsloth"

    def test_resolve_backend_trl_explicit(self):
        student = StudentAgent()
        config = LoRAConfig(backend="trl")
        assert student._resolve_backend(config) == "trl"

    def test_resolve_backend_unsloth_missing(self):
        student = StudentAgent()
        config = LoRAConfig(backend="unsloth")
        # Unsloth not installed locally → should raise
        with pytest.raises(RuntimeError, match="not installed"):
            student._resolve_backend(config)

    def test_load_dataset_method_exists(self):
        assert hasattr(StudentAgent, "_load_dataset")

    def test_merge_and_quantize_method_exists(self):
        student = StudentAgent()
        assert hasattr(student, "merge_and_quantize")


class TestReinforcerSimPO:
    def test_reinforcement_result_method_field(self):
        from mascarade.finetune.agents.reinforcer import ReinforcementResult

        r = ReinforcementResult(
            dataset_path="/tmp/test.jsonl", total_pairs=10, method="simpo"
        )
        assert r.method == "simpo"
        assert r.ready_for_training

    def test_train_alignment_method_exists(self):
        agent = ReinforcerAgent()
        assert hasattr(agent, "train_alignment")

    def test_is_repetitive_false_for_unique(self):
        text = " ".join(f"word{i}" for i in range(20))
        assert not ReinforcerAgent._is_repetitive(text)

    def test_is_repetitive_true_for_repeated(self):
        text = "hello world again " * 20
        assert ReinforcerAgent._is_repetitive(text)


class TestReinforcerGRPO:
    def test_train_grpo_method_exists(self):
        agent = ReinforcerAgent()
        assert hasattr(agent, "train_grpo")

    def test_default_code_reward(self):
        completions = [[{"content": "def hello():\n    return 'world'"}]]
        prompts = ["Write a hello function"]
        rewards = ReinforcerAgent._default_code_reward(completions, prompts)
        assert len(rewards) == 1
        assert rewards[0] > 0.5  # Should get points for def, return, length

    def test_default_code_reward_empty(self):
        completions = [[{"content": ""}]]
        prompts = ["test"]
        rewards = ReinforcerAgent._default_code_reward(completions, prompts)
        assert rewards[0] < 0.5


class TestReinforcerKxkm:
    @pytest.fixture(autouse=True)
    def _restore_settings(self):
        snapshot = {
            "mascarade_project_id": settings.mascarade_project_id,
            "kxkm_rag_url": settings.kxkm_rag_url,
            "kxkm_timeout_seconds": settings.kxkm_timeout_seconds,
            "kxkm_dpo_persona": settings.kxkm_dpo_persona,
        }
        yield
        for name, value in snapshot.items():
            setattr(settings, name, value)

    @pytest.mark.asyncio
    async def test_collect_kxkm_feedback_normalizes_pairs(self):
        settings.mascarade_project_id = "project-alpha"
        settings.kxkm_rag_url = "http://localhost:3333"
        settings.kxkm_dpo_persona = "pharmacius"

        with patch(
            "mascarade.finetune.agents.reinforcer.httpx.AsyncClient"
        ) as async_client_cls:
            ctx = AsyncMock()
            ctx.get = AsyncMock(
                return_value=_FakeResponse(
                    {
                        "ok": True,
                        "data": {
                            "pairs": [
                                {
                                    "prompt": "Question",
                                    "chosen": "Bonne reponse",
                                    "rejected": "Mauvaise reponse",
                                    "persona": "pharmacius",
                                }
                            ],
                            "total": 1,
                        },
                    }
                )
            )
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            async_client_cls.return_value = ctx

            agent = ReinforcerAgent()
            pairs = await agent.collect_kxkm_feedback(project_id="project-alpha")

        assert pairs == [
            DPOPair(
                prompt="Question",
                chosen="Bonne reponse",
                rejected="Mauvaise reponse",
                persona="pharmacius",
                project_id="project-alpha",
                source="kxkm",
            )
        ]
        _, kwargs = ctx.get.await_args
        assert kwargs["params"]["project_id"] == "project-alpha"
        assert kwargs["headers"]["x-mascarade-project-id"] == "project-alpha"
        assert kwargs["headers"]["x-mascarade-federation-scope"] == "project-alpha"

    @pytest.mark.asyncio
    async def test_generate_dpo_pairs_dedupes_kxkm_feedback(
        self, tmp_path, monkeypatch
    ):
        settings.mascarade_project_id = "project-alpha"
        agent = ReinforcerAgent(output_dir=tmp_path)
        duplicate = DPOPair(
            prompt="Question",
            chosen="Bonne reponse",
            rejected="Mauvaise reponse",
            persona="pharmacius",
            project_id="project-alpha",
            source="kxkm",
        )
        monkeypatch.setattr(
            agent,
            "collect_kxkm_feedback",
            AsyncMock(return_value=[duplicate, duplicate]),
        )

        result = await agent.generate_dpo_pairs(
            [],
            run_id="run-kxkm-1",
            project_id="project-alpha",
        )

        assert result.total_pairs == 1
        dataset_path = Path(result.dataset_path)
        assert dataset_path.exists()
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["source"] == "kxkm"
        assert payload["project_id"] == "project-alpha"


class TestPubSubThreadSafety:
    def test_pubsub_has_seen_lock(self):
        from unittest.mock import MagicMock

        from mascarade.p2p.pubsub import P2PPubSub

        transport = MagicMock()
        transport.on_message = MagicMock()
        ps = P2PPubSub(local_peer_id="test", transport=transport)
        assert hasattr(ps, "_seen_lock")
        import asyncio

        assert isinstance(ps._seen_lock, asyncio.Lock)
