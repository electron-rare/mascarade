"""Provider spécialisé pour le routing PCB via KiCadRouterAI (GNN+PPO).

Ce provider ne gère pas du texte comme les LLM classiques.
Il prend un fichier .kicad_pcb + des tags de contraintes et produit
un board routé via un modèle GNN entraîné par renforcement.

Intégration: vendors/kicadrouterai/
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path

from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.providers.kicad_router")

# Add vendor path for kicadrouterai imports
VENDOR_DIR = Path(__file__).resolve().parents[4] / "vendors" / "kicadrouterai"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


def _check_deps() -> bool:
    """Check if kicadrouterai dependencies are available."""
    try:
        import numpy
        import torch

        return True
    except ImportError:
        return False


class KiCadRouterProvider(LLMProvider):
    """Provider pour le routing automatique de PCB via GNN+PPO.

    Modes d'utilisation:
    1. route  - Route un board avec un modèle entraîné
    2. train  - Entraîne le modèle sur un board
    3. tags   - Génère des tags de contraintes

    Exemple:
        provider = KiCadRouterProvider(model_path="models/router.pt")
        response = await provider.send([{
            "role": "user",
            "content": json.dumps({
                "action": "route",
                "board_path": "/path/to/board.kicad_pcb",
                "tags": [...],
                "max_steps": 10000,
            })
        }])
    """

    name = "kicad_router"
    default_model = "gnn-ppo-fp8"
    cost_per_million = (0.0, 0.0)  # Local model
    speed_rank = 5
    quality_rank = 7  # Specialized, high quality for routing

    def __init__(
        self,
        model_path: str | None = None,
        device: str | None = None,
        use_fp8: bool = True,
    ):
        self.model_path = model_path
        self.device = device
        self.use_fp8 = use_fp8
        self._router = None
        self._deps_available = _check_deps()

    @property
    def is_configured(self) -> bool:
        return self._deps_available

    def _get_router(self):
        """Lazy-load the FP8Router."""
        if self._router is None:
            if not self._deps_available:
                raise ImportError(
                    "KiCadRouterAI dependencies missing. "
                    "Install: pip install torch torch-geometric stable-baselines3 gymnasium"
                )
            if self.model_path is None:
                raise ValueError("model_path required for inference")

            from src.router.inference import FP8Router

            self._router = FP8Router(
                model_path=self.model_path,
                device=self.device,
                use_fp8=self.use_fp8,
            )
        return self._router

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Dispatch routing commands.

        Expected message content is JSON with an "action" field:
        - route: Route a .kicad_pcb board
        - train: Train model on a board
        - analyze: Analyze board and suggest tags
        """
        last_msg = messages[-1]["content"] if messages else ""

        try:
            request = json.loads(last_msg)
        except (json.JSONDecodeError, TypeError):
            return LLMResponse(
                content=json.dumps(
                    {
                        "error": "Expected JSON with 'action' field",
                        "supported_actions": ["route", "train", "analyze"],
                    }
                ),
                model=self.default_model,
                provider=self.name,
            )

        action = request.get("action", "route")

        if action == "route":
            result = await self._handle_route(request)
        elif action == "train":
            result = await self._handle_train(request)
        elif action == "analyze":
            result = await self._handle_analyze(request)
        else:
            result = {"error": f"Unknown action: {action}"}

        return LLMResponse(
            content=json.dumps(result, default=str),
            model=model or self.default_model,
            provider=self.name,
            usage=result.get("usage", {}),
        )

    async def _handle_route(self, request: dict) -> dict:
        """Route a PCB board using trained model."""
        board_path = request.get("board_path")
        if not board_path:
            return {"error": "board_path required"}

        tags_data = request.get("tags", [])
        max_steps = request.get("max_steps", 10000)
        deterministic = request.get("deterministic", True)
        output_path = request.get("output_path")

        try:
            router = self._get_router()

            # Load tags if provided
            tags = []
            if tags_data:
                from src.tags import load_tags_from_list

                tags = load_tags_from_list(tags_data)

            # Route
            board, metrics = router.route_board(
                board_path=board_path,
                tags=tags,
                max_steps=max_steps,
                deterministic=deterministic,
            )

            # Save if requested
            if output_path and board is not None:
                router.save_board(board, output_path)

            return {
                "status": "success",
                "metrics": {
                    "total_steps": metrics["total_steps"],
                    "nets_completed": metrics["nets_completed"],
                    "nets_total": metrics["nets_total"],
                    "drc_errors": metrics["drc_errors"],
                    "tag_compliance": metrics.get("tag_compliance", {}),
                },
                "output_path": output_path,
            }

        except Exception as e:
            logger.exception("Routing failed")
            return {"error": str(e), "status": "failed"}

    async def _handle_train(self, request: dict) -> dict:
        """Train model on a board."""
        board_path = request.get("board_path")
        timesteps = request.get("timesteps", 100000)
        save_dir = request.get("save_dir", "checkpoints")
        tags_data = request.get("tags", [])

        try:
            from src.router.environment import KiCadRoutingEnv
            from src.router.model import GNNRouter
            from src.router.trainer import FP8Trainer, TrainingConfig

            # Load tags
            tags = []
            if tags_data:
                from src.tags import load_tags_from_list

                tags = load_tags_from_list(tags_data)

            # Create environment
            env = KiCadRoutingEnv(
                board_path=board_path,
                tags=tags,
            )

            # Create model
            model = GNNRouter(
                node_features=64,
                edge_features=16,
                hidden_dim=request.get("hidden_dim", 256),
                num_layers=request.get("num_layers", 6),
                action_dim=env.action_space.n,
            )

            # Config
            config = TrainingConfig(
                learning_rate=request.get("lr", 3e-4),
                batch_size=request.get("batch_size", 64),
                use_fp8=self.use_fp8,
                save_dir=save_dir,
            )

            # Train
            trainer = FP8Trainer(model, env, config)

            resume_path = request.get("resume")
            if resume_path:
                trainer.load(resume_path)

            trainer.train(total_timesteps=timesteps)

            # Save final
            final_path = str(Path(save_dir) / "final_model.pt")
            trainer.save(final_path)

            return {
                "status": "success",
                "model_path": final_path,
                "total_timesteps": trainer.total_timesteps,
                "episodes": len(trainer.episode_rewards),
                "avg_reward": float(
                    sum(trainer.episode_rewards[-100:])
                    / max(len(trainer.episode_rewards[-100:]), 1)
                ),
            }

        except Exception as e:
            logger.exception("Training failed")
            return {"error": str(e), "status": "failed"}

    async def _handle_analyze(self, request: dict) -> dict:
        """Analyze a board and suggest routing tags."""
        board_path = request.get("board_path")
        if not board_path:
            return {"error": "board_path required"}

        try:
            from src.core.board_graph import BoardGraph

            try:
                import pcbnew

                board = pcbnew.LoadBoard(board_path)
                graph = BoardGraph.from_kicad_board(board)
            except ImportError:
                return {
                    "error": "KiCad (pcbnew) required for board analysis",
                    "hint": "Run from KiCad scripting console or install kicad",
                }

            nets = graph.get_unrouted_nets()
            suggestions = []

            # Suggest impedance tags for high-speed nets
            for net in nets:
                if any(
                    kw in net.lower()
                    for kw in ["clk", "clock", "usb", "eth", "spi", "i2c"]
                ):
                    suggestions.append(
                        {
                            "tag_type": "IMPEDANCE_SINGLE",
                            "net": net,
                            "target_ohm": 50,
                            "reason": "High-speed signal detected",
                        }
                    )
                if any(kw in net.lower() for kw in ["dp", "dn", "usb_p", "usb_n"]):
                    suggestions.append(
                        {
                            "tag_type": "IMPEDANCE_DIFF",
                            "net": net,
                            "diff_ohm": 90,
                            "reason": "Differential pair detected",
                        }
                    )

            return {
                "status": "success",
                "board_info": {
                    "num_nets": graph.num_nets,
                    "unrouted": len(nets),
                    "num_layers": graph.num_layers,
                },
                "suggested_tags": suggestions,
            }

        except Exception as e:
            logger.exception("Analysis failed")
            return {"error": str(e), "status": "failed"}

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream routing progress updates."""
        response = await self.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield response.content

    def available_models(self) -> list[str]:
        """Available routing models."""
        models = ["gnn-ppo-fp8"]

        # Check for saved checkpoints
        checkpoints_dir = VENDOR_DIR / "checkpoints"
        if checkpoints_dir.exists():
            for pt_file in checkpoints_dir.glob("*.pt"):
                models.append(f"checkpoint:{pt_file.stem}")

        # Check for project-level models
        project_models = Path(__file__).resolve().parents[4] / "fine_tuned_models"
        if project_models.exists():
            for kicad_dir in project_models.glob("kicad_*"):
                if (kicad_dir / "final").exists() or (
                    kicad_dir / "final_model.pt"
                ).exists():
                    models.append(f"finetuned:{kicad_dir.name}")

        return models
