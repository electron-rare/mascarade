"""ML-based routing classifier — learns from historical routing decisions.

Complements the rule-based ``_complexity_score`` / ``_routellm_heuristic_policy``
in ``router.py`` by learning tier selection (strong / cheap / fast) from past
routing outcomes stored in ``MetricsTracker.request_history``.

The classifier is intentionally **zero-dependency** at inference time: no
scikit-learn, no numpy.  Training uses only stdlib ``math`` to fit a simple
softmax linear model via mini-batch gradient descent.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("mascarade.router.ml_classifier")

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

TIERS = ("strong", "cheap", "fast")

_CODE_LINE_RE = re.compile(
    r"^\s*(import |from |def |class |function |const |let |var |if\s*\(|for\s*\(|#include)",
    re.MULTILINE,
)
_CODE_BLOCK_RE = re.compile(r"```")
_JSON_RE = re.compile(r"\{[\s\S]{10,}\}")
_QUESTION_RE = re.compile(r"\?")


@dataclass
class PromptFeatures:
    """Feature vector extracted from a prompt."""

    token_count: int
    char_count: int
    word_count: int
    line_count: int
    code_ratio: float  # fraction of lines that look like code
    question_marks: int
    avg_word_length: float
    vocab_diversity: float  # unique_words / total_words
    has_json: bool
    has_code_block: bool
    language_signals: str  # "en", "fr", "mixed", "code"
    domain_signals: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    def to_vector(self) -> dict[str, float]:
        """Return a flat ``{feature_name: float}`` dict for the linear model."""
        return {
            "token_count_norm": min(self.token_count / 2000.0, 1.0),
            "char_count_norm": min(self.char_count / 8000.0, 1.0),
            "word_count_norm": min(self.word_count / 1500.0, 1.0),
            "line_count_norm": min(self.line_count / 200.0, 1.0),
            "code_ratio": self.code_ratio,
            "question_marks_norm": min(self.question_marks / 5.0, 1.0),
            "avg_word_length_norm": min(self.avg_word_length / 12.0, 1.0),
            "vocab_diversity": self.vocab_diversity,
            "has_json": 1.0 if self.has_json else 0.0,
            "has_code_block": 1.0 if self.has_code_block else 0.0,
            "lang_en": 1.0 if self.language_signals == "en" else 0.0,
            "lang_fr": 1.0 if self.language_signals == "fr" else 0.0,
            "lang_code": 1.0 if self.language_signals == "code" else 0.0,
            # Domain one-hot
            "domain_electronics": 1.0 if "electronics" in self.domain_signals else 0.0,
            "domain_cad": 1.0 if "cad" in self.domain_signals else 0.0,
            "domain_code": 1.0 if "code" in self.domain_signals else 0.0,
            "domain_math": 1.0 if "math" in self.domain_signals else 0.0,
        }


class PromptFeatureExtractor:
    """Extract routing-relevant features from a prompt."""

    _DOMAIN_PATTERNS: dict[str, re.Pattern[str]] = {
        "electronics": re.compile(
            r"\b(pcb|schematic|kicad|resistor|capacitor|ipc|drc|stm32|spice)\b", re.I
        ),
        "cad": re.compile(
            r"\b(freecad|openscad|stl|3d\s*print|mesh|cad)\b", re.I
        ),
        "code": re.compile(
            r"\b(function|class|def |import |async|await|return|algorithm|refactor)\b"
        ),
        "math": re.compile(
            r"\b(equation|integral|derivative|matrix|probability|proof|theorem)\b", re.I
        ),
    }

    _FR_WORDS = re.compile(
        r"\b(le|la|les|un|une|des|est|sont|dans|avec|pour|qui|que|sur|pas|mais|ou)\b",
        re.I,
    )
    _EN_WORDS = re.compile(
        r"\b(the|is|are|was|were|have|has|been|with|this|that|from|for|not|but|and)\b",
        re.I,
    )

    def extract(self, text: str) -> PromptFeatures:
        """Build a ``PromptFeatures`` from raw prompt text."""
        lines = text.split("\n")
        words = text.split()
        word_count = len(words) or 1
        unique_words = set(w.lower() for w in words)

        code_lines = sum(1 for ln in lines if _CODE_LINE_RE.match(ln))
        line_count = len(lines) or 1

        # Language detection (quick heuristic)
        fr_hits = len(self._FR_WORDS.findall(text))
        en_hits = len(self._EN_WORDS.findall(text))
        code_hits = len(_CODE_LINE_RE.findall(text))
        if code_hits > max(fr_hits, en_hits):
            lang = "code"
        elif fr_hits > en_hits * 1.5:
            lang = "fr"
        elif en_hits > fr_hits * 1.5:
            lang = "en"
        else:
            lang = "mixed"

        # Domain signals
        domains: list[str] = []
        for domain, pattern in self._DOMAIN_PATTERNS.items():
            if pattern.search(text):
                domains.append(domain)

        avg_wl = sum(len(w) for w in words) / word_count if words else 0.0

        return PromptFeatures(
            token_count=max(1, int(len(text) / 4)),
            char_count=len(text),
            word_count=word_count,
            line_count=line_count,
            code_ratio=code_lines / line_count,
            question_marks=len(_QUESTION_RE.findall(text)),
            avg_word_length=avg_wl,
            vocab_diversity=len(unique_words) / word_count,
            has_json=bool(_JSON_RE.search(text)),
            has_code_block=bool(_CODE_BLOCK_RE.search(text)),
            language_signals=lang,
            domain_signals=domains,
        )


# ---------------------------------------------------------------------------
# Softmax linear classifier (zero external deps)
# ---------------------------------------------------------------------------


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    """Numerically-stable softmax over a dict of scores."""
    max_s = max(scores.values()) if scores else 0.0
    exps = {k: math.exp(v - max_s) for k, v in scores.items()}
    total = sum(exps.values()) or 1.0
    return {k: v / total for k, v in exps.items()}


class RoutingClassifier:
    """Lightweight softmax linear classifier for routing tier prediction.

    Predicts routing tier (``strong`` / ``cheap`` / ``fast``) based on prompt
    features.  Can be trained incrementally from successful routing outcomes
    recorded via ``record_outcome``.

    No external ML library is required — the model is a simple weight matrix
    trained with mini-batch SGD and persisted as JSON.
    """

    def __init__(self, model_path: Path | None = None) -> None:
        self._weights: dict[str, dict[str, float]] = {
            tier: {} for tier in TIERS
        }
        self._bias: dict[str, float] = {tier: 0.0 for tier in TIERS}
        self._feature_extractor = PromptFeatureExtractor()
        self._model_path = model_path
        self._training_data: list[dict[str, Any]] = []
        self.is_loaded = False

        if model_path and model_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, prompt: str) -> str:
        """Predict routing tier: ``'strong'``, ``'cheap'``, or ``'fast'``."""
        features = self._feature_extractor.extract(prompt)
        scores = self._score(features)
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def predict_with_confidence(self, prompt: str) -> tuple[str, float]:
        """Predict with a confidence score in [0, 1]."""
        features = self._feature_extractor.extract(prompt)
        scores = self._score(features)
        probabilities = _softmax(scores)
        best_tier = max(probabilities, key=probabilities.get)  # type: ignore[arg-type]
        return best_tier, probabilities[best_tier]

    def predict_probabilities(self, prompt: str) -> dict[str, float]:
        """Return softmax probabilities for each tier."""
        features = self._feature_extractor.extract(prompt)
        return _softmax(self._score(features))

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        prompt: str,
        tier: str,
        success: bool,
        latency_ms: float,
        cost: float,
    ) -> None:
        """Record a routing outcome for future training.

        Parameters
        ----------
        prompt:
            The original user prompt.
        tier:
            The tier that was used (``strong`` / ``cheap`` / ``fast``).
        success:
            Whether the request completed successfully.
        latency_ms:
            End-to-end latency in milliseconds.
        cost:
            Estimated cost of the request (USD).
        """
        if tier not in TIERS:
            logger.warning("Unknown tier '%s', ignoring outcome", tier)
            return

        features = self._feature_extractor.extract(prompt)
        self._training_data.append(
            {
                "features": features.to_vector(),
                "tier": tier,
                "success": success,
                "latency_ms": latency_ms,
                "cost": cost,
            }
        )
        logger.debug(
            "Recorded outcome tier=%s success=%s (total %d samples)",
            tier,
            success,
            len(self._training_data),
        )

    # ------------------------------------------------------------------
    # Training (mini-batch SGD on softmax cross-entropy)
    # ------------------------------------------------------------------

    def train(
        self,
        *,
        learning_rate: float = 0.1,
        epochs: int = 50,
        min_samples: int = 10,
    ) -> dict[str, Any]:
        """Train / retrain from recorded outcomes.

        Only successful outcomes are used as positive labels.  Returns a dict
        with training statistics.
        """
        positives = [d for d in self._training_data if d["success"]]
        if len(positives) < min_samples:
            logger.info(
                "Not enough positive samples to train (%d < %d)",
                len(positives),
                min_samples,
            )
            return {"trained": False, "samples": len(positives)}

        # Collect all feature keys from the data
        all_keys: set[str] = set()
        for sample in positives:
            all_keys.update(sample["features"].keys())

        # Re-initialise weights to zero
        self._weights = {tier: {k: 0.0 for k in all_keys} for tier in TIERS}
        self._bias = {tier: 0.0 for tier in TIERS}

        total_loss = 0.0
        for epoch in range(epochs):
            epoch_loss = 0.0
            for sample in positives:
                fv = sample["features"]
                target_tier = sample["tier"]

                # Forward pass: compute scores and probabilities
                raw_scores = {
                    tier: sum(
                        self._weights[tier].get(k, 0.0) * v for k, v in fv.items()
                    )
                    + self._bias[tier]
                    for tier in TIERS
                }
                probs = _softmax(raw_scores)

                # Cross-entropy loss contribution
                p = max(probs.get(target_tier, 1e-12), 1e-12)
                epoch_loss -= math.log(p)

                # Gradient step (softmax cross-entropy gradient)
                for tier in TIERS:
                    grad = probs[tier] - (1.0 if tier == target_tier else 0.0)
                    for k, v in fv.items():
                        self._weights[tier][k] = (
                            self._weights[tier].get(k, 0.0) - learning_rate * grad * v
                        )
                    self._bias[tier] -= learning_rate * grad

            total_loss = epoch_loss / len(positives)

        # Compute training accuracy
        correct = 0
        for sample in positives:
            fv = sample["features"]
            raw_scores = {
                tier: sum(
                    self._weights[tier].get(k, 0.0) * v for k, v in fv.items()
                )
                + self._bias[tier]
                for tier in TIERS
            }
            predicted = max(raw_scores, key=raw_scores.get)  # type: ignore[arg-type]
            if predicted == sample["tier"]:
                correct += 1

        accuracy = correct / len(positives)
        self.is_loaded = True

        logger.info(
            "Training complete: %d samples, accuracy=%.2f%%, loss=%.4f",
            len(positives),
            accuracy * 100,
            total_loss,
        )

        if self._model_path:
            self._save()

        return {
            "trained": True,
            "samples": len(positives),
            "accuracy": accuracy,
            "final_loss": total_loss,
            "epochs": epochs,
        }

    # ------------------------------------------------------------------
    # Scoring internals
    # ------------------------------------------------------------------

    def _score(self, features: PromptFeatures) -> dict[str, float]:
        """Compute raw scores for each tier using the linear model."""
        fv = features.to_vector()
        if not self.is_loaded:
            # Fallback heuristic scores when model is not trained.
            # Mirrors the existing _complexity_score behaviour so that
            # the classifier degrades gracefully.
            complexity = (
                fv.get("char_count_norm", 0.0) * 0.4
                + fv.get("code_ratio", 0.0) * 0.25
                + fv.get("has_code_block", 0.0) * 0.15
                + fv.get("vocab_diversity", 0.0) * 0.1
                + fv.get("question_marks_norm", 0.0) * 0.1
            )
            return {
                "strong": complexity,
                "cheap": 1.0 - complexity,
                "fast": 0.3 + (1.0 - fv.get("char_count_norm", 0.0)) * 0.5,
            }

        return {
            tier: sum(
                self._weights[tier].get(k, 0.0) * v for k, v in fv.items()
            )
            + self._bias[tier]
            for tier in TIERS
        }

    # ------------------------------------------------------------------
    # Persistence (JSON — human-readable, no pickle)
    # ------------------------------------------------------------------

    def _save(self) -> None:
        if not self._model_path:
            return
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "weights": self._weights,
            "bias": self._bias,
            "training_samples": len(self._training_data),
        }
        self._model_path.write_text(json.dumps(data, indent=2))
        logger.info("Saved routing classifier to %s", self._model_path)

    def _load(self) -> None:
        if not self._model_path or not self._model_path.exists():
            return
        try:
            data = json.loads(self._model_path.read_text())
            self._weights = data["weights"]
            self._bias = data["bias"]
            self.is_loaded = True
            logger.info(
                "Loaded routing classifier from %s (%d training samples)",
                self._model_path,
                data.get("training_samples", 0),
            )
        except Exception as exc:
            logger.warning("Failed to load routing classifier: %s", exc)

    # ------------------------------------------------------------------
    # Bulk import from metrics history
    # ------------------------------------------------------------------

    def import_from_history(
        self,
        request_history: list[dict[str, Any]],
        *,
        tier_mapping: dict[str, str] | None = None,
    ) -> int:
        """Import training data from ``MetricsTracker.request_history``.

        Parameters
        ----------
        request_history:
            List of dicts as stored in ``MetricsTracker.request_history``.
        tier_mapping:
            Optional mapping from strategy name to tier label.
            Defaults to ``{"best": "strong", "cheapest": "cheap", "fastest": "fast"}``.

        Returns
        -------
        Number of samples imported.
        """
        if tier_mapping is None:
            tier_mapping = {
                "best": "strong",
                "routellm": "strong",
                "cheapest": "cheap",
                "fastest": "fast",
                "domain": "strong",
                "specific": "strong",
            }

        imported = 0
        for entry in request_history:
            strategy = (entry.get("strategy") or "").lower()
            tier = tier_mapping.get(strategy)
            if tier is None:
                continue
            success = entry.get("success", False)
            if not success:
                continue

            # We don't have the original prompt in request_history, so we
            # store a synthetic feature vector based on available metadata.
            self._training_data.append(
                {
                    "features": {
                        "token_count_norm": min(entry.get("tokens", 0) / 2000.0, 1.0),
                        "char_count_norm": 0.0,
                        "word_count_norm": 0.0,
                        "line_count_norm": 0.0,
                        "code_ratio": 0.0,
                        "question_marks_norm": 0.0,
                        "avg_word_length_norm": 0.0,
                        "vocab_diversity": 0.0,
                        "has_json": 0.0,
                        "has_code_block": 0.0,
                        "lang_en": 0.0,
                        "lang_fr": 0.0,
                        "lang_code": 0.0,
                        "domain_electronics": 0.0,
                        "domain_cad": 0.0,
                        "domain_code": 0.0,
                        "domain_math": 0.0,
                    },
                    "tier": tier,
                    "success": True,
                    "latency_ms": entry.get("response_time", 0.0) * 1000,
                    "cost": entry.get("cost", 0.0),
                }
            )
            imported += 1

        logger.info("Imported %d samples from request history", imported)
        return imported


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_routing_classifier_instance: RoutingClassifier | None = None


def get_routing_classifier(
    model_path: Path | None = None,
) -> RoutingClassifier:
    """Get or create the global ``RoutingClassifier`` singleton."""
    global _routing_classifier_instance
    if _routing_classifier_instance is None:
        if model_path is None:
            model_path = Path.home() / ".mascarade" / "models" / "routing_classifier.json"
        _routing_classifier_instance = RoutingClassifier(model_path=model_path)
    return _routing_classifier_instance
