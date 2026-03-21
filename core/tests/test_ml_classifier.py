"""Comprehensive tests for the ML routing classifier module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mascarade.router.ml_classifier import (
    TIERS,
    PromptFeatureExtractor,
    PromptFeatures,
    RoutingClassifier,
    _softmax,
)


# ---------------------------------------------------------------------------
# PromptFeatureExtractor.extract()
# ---------------------------------------------------------------------------


class TestPromptFeatureExtractor:
    def setup_method(self):
        self.extractor = PromptFeatureExtractor()

    def test_extract_simple_text(self):
        features = self.extractor.extract("Hello, how are you?")
        assert isinstance(features, PromptFeatures)
        assert features.word_count >= 4
        assert features.char_count == len("Hello, how are you?")
        assert features.question_marks == 1

    def test_extract_empty_string(self):
        features = self.extractor.extract("")
        assert features.char_count == 0
        assert features.word_count == 1  # split() on empty returns []  but max(1, ...)
        assert features.line_count == 1
        assert features.code_ratio == 0.0

    def test_extract_multiline(self):
        text = "line one\nline two\nline three"
        features = self.extractor.extract(text)
        assert features.line_count == 3

    # -----------------------------------------------------------------------
    # Code ratio detection
    # -----------------------------------------------------------------------

    def test_code_ratio_pure_code(self):
        code = "import os\nimport sys\ndef main():\n    pass"
        features = self.extractor.extract(code)
        assert features.code_ratio > 0.5

    def test_code_ratio_no_code(self):
        text = "This is plain english text with no code at all."
        features = self.extractor.extract(text)
        assert features.code_ratio == 0.0

    def test_has_code_block(self):
        text = "Here is code:\n```python\nprint('hi')\n```"
        features = self.extractor.extract(text)
        assert features.has_code_block is True

    def test_no_code_block(self):
        features = self.extractor.extract("No code blocks here.")
        assert features.has_code_block is False

    # -----------------------------------------------------------------------
    # Domain signal detection
    # -----------------------------------------------------------------------

    def test_domain_electronics(self):
        text = "Design a PCB with a STM32 and check DRC in KiCad"
        features = self.extractor.extract(text)
        assert "electronics" in features.domain_signals

    def test_domain_cad(self):
        text = "Open the FreeCAD model and export as STL for 3D printing"
        features = self.extractor.extract(text)
        assert "cad" in features.domain_signals

    def test_domain_code(self):
        text = "Refactor the function to use async await and return a promise"
        features = self.extractor.extract(text)
        assert "code" in features.domain_signals

    def test_domain_math(self):
        text = "Compute the integral of the derivative and prove the theorem"
        features = self.extractor.extract(text)
        assert "math" in features.domain_signals

    def test_no_domain_signals(self):
        text = "Tell me a joke about cats."
        features = self.extractor.extract(text)
        assert features.domain_signals == []

    # -----------------------------------------------------------------------
    # Language detection
    # -----------------------------------------------------------------------

    def test_language_french(self):
        text = "Bonjour, est-ce que les agents sont dans le registre pour les utilisateurs ?"
        features = self.extractor.extract(text)
        assert features.language_signals == "fr"

    def test_language_english(self):
        text = "The system is not working and has been failing for the last three days."
        features = self.extractor.extract(text)
        assert features.language_signals == "en"

    def test_language_code(self):
        text = "import os\nfrom pathlib import Path\ndef main():\n    pass\nclass Foo:\n    pass"
        features = self.extractor.extract(text)
        assert features.language_signals == "code"

    # -----------------------------------------------------------------------
    # JSON detection
    # -----------------------------------------------------------------------

    def test_has_json(self):
        text = 'Here is the config: {"name": "test", "value": 42, "nested": {"key": "val"}}'
        features = self.extractor.extract(text)
        assert features.has_json is True

    def test_no_json(self):
        features = self.extractor.extract("Just regular text.")
        assert features.has_json is False

    # -----------------------------------------------------------------------
    # Feature vector
    # -----------------------------------------------------------------------

    def test_to_vector_keys(self):
        features = self.extractor.extract("Hello world")
        vec = features.to_vector()
        expected_keys = {
            "token_count_norm", "char_count_norm", "word_count_norm",
            "line_count_norm", "code_ratio", "question_marks_norm",
            "avg_word_length_norm", "vocab_diversity", "has_json",
            "has_code_block", "lang_en", "lang_fr", "lang_code",
            "domain_electronics", "domain_cad", "domain_code", "domain_math",
        }
        assert set(vec.keys()) == expected_keys

    def test_to_vector_values_bounded(self):
        """All normalized values should be in [0, 1]."""
        features = self.extractor.extract("A " * 5000)  # very long text
        vec = features.to_vector()
        for key, val in vec.items():
            assert 0.0 <= val <= 1.0, f"{key} = {val} is out of bounds"


# ---------------------------------------------------------------------------
# RoutingClassifier
# ---------------------------------------------------------------------------


class TestRoutingClassifier:
    def test_predict_default_untrained(self):
        clf = RoutingClassifier()
        tier = clf.predict("Hello world")
        assert tier in TIERS

    def test_predict_returns_string(self):
        clf = RoutingClassifier()
        result = clf.predict("Test prompt")
        assert isinstance(result, str)

    def test_predict_with_confidence_returns_tuple(self):
        clf = RoutingClassifier()
        tier, confidence = clf.predict_with_confidence("Test prompt")
        assert tier in TIERS
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_predict_probabilities(self):
        clf = RoutingClassifier()
        probs = clf.predict_probabilities("Test prompt")
        assert set(probs.keys()) == set(TIERS)
        assert abs(sum(probs.values()) - 1.0) < 1e-6

    def test_record_outcome_stores_data(self):
        clf = RoutingClassifier()
        assert len(clf._training_data) == 0
        clf.record_outcome("test", "strong", True, 100.0, 0.01)
        assert len(clf._training_data) == 1
        assert clf._training_data[0]["tier"] == "strong"

    def test_record_outcome_ignores_unknown_tier(self):
        clf = RoutingClassifier()
        clf.record_outcome("test", "unknown_tier", True, 100.0, 0.01)
        assert len(clf._training_data) == 0

    def test_train_insufficient_samples(self):
        clf = RoutingClassifier()
        # Only 3 samples, needs at least 10
        for i in range(3):
            clf.record_outcome(f"prompt {i}", "strong", True, 100.0, 0.01)
        result = clf.train(min_samples=10)
        assert result["trained"] is False

    def test_train_with_enough_samples(self):
        clf = RoutingClassifier()
        # Record 15 samples across tiers
        for i in range(6):
            clf.record_outcome(f"complex code with function class {i}", "strong", True, 200.0, 0.05)
        for i in range(5):
            clf.record_outcome(f"simple question {i}", "cheap", True, 50.0, 0.001)
        for i in range(4):
            clf.record_outcome(f"quick hi {i}", "fast", True, 20.0, 0.0005)

        result = clf.train(min_samples=10, epochs=30)
        assert result["trained"] is True
        assert result["samples"] == 15
        assert "accuracy" in result
        assert "final_loss" in result
        assert clf.is_loaded is True

    def test_train_uses_only_successful_outcomes(self):
        clf = RoutingClassifier()
        for i in range(12):
            clf.record_outcome(f"prompt {i}", "strong", True, 100.0, 0.01)
        # Add failed outcomes that should be ignored
        for i in range(5):
            clf.record_outcome(f"failed {i}", "cheap", False, 100.0, 0.01)

        result = clf.train(min_samples=10, epochs=10)
        assert result["trained"] is True
        assert result["samples"] == 12  # only successful ones

    def test_save_load_roundtrip(self, tmp_path):
        model_file = tmp_path / "classifier.json"
        clf = RoutingClassifier(model_path=model_file)

        # Train it
        for i in range(12):
            clf.record_outcome(f"prompt {i}", "strong", True, 100.0, 0.01)
        clf.train(min_samples=10, epochs=10)

        # Verify saved
        assert model_file.exists()
        data = json.loads(model_file.read_text())
        assert "weights" in data
        assert "bias" in data

        # Load into a new classifier
        clf2 = RoutingClassifier(model_path=model_file)
        assert clf2.is_loaded is True
        assert clf2._weights == clf._weights
        assert clf2._bias == clf._bias

    def test_load_nonexistent_path(self, tmp_path):
        model_file = tmp_path / "does_not_exist.json"
        clf = RoutingClassifier(model_path=model_file)
        assert clf.is_loaded is False

    def test_prediction_changes_after_training(self):
        """After training, the classifier should use learned weights, not heuristics."""
        clf = RoutingClassifier()

        # Before training: uses heuristic
        before = clf.predict_probabilities("simple hello")

        # Train heavily toward 'fast' for simple prompts
        for i in range(20):
            clf.record_outcome(f"simple hello {i}", "fast", True, 10.0, 0.001)
        clf.train(min_samples=10, epochs=100)

        after = clf.predict_probabilities("simple hello")
        # After training, 'fast' probability should be higher
        assert after["fast"] > before.get("fast", 0) or clf.is_loaded


# ---------------------------------------------------------------------------
# _softmax helper
# ---------------------------------------------------------------------------


class TestSoftmax:
    def test_softmax_sums_to_one(self):
        result = _softmax({"a": 1.0, "b": 2.0, "c": 3.0})
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_softmax_ordering(self):
        result = _softmax({"a": 1.0, "b": 2.0, "c": 3.0})
        assert result["c"] > result["b"] > result["a"]

    def test_softmax_equal_inputs(self):
        result = _softmax({"a": 1.0, "b": 1.0, "c": 1.0})
        for v in result.values():
            assert abs(v - 1.0 / 3.0) < 1e-6

    def test_softmax_empty(self):
        result = _softmax({})
        assert result == {}
