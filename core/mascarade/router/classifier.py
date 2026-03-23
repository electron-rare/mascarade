"""ML classifier for domain-based routing.

Provides a lightweight machine learning classifier to improve domain detection
accuracy beyond simple keyword matching. Uses TF-IDF + Logistic Regression
for fast inference (<50ms p95) with minimal memory footprint.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

logger = logging.getLogger("mascarade.router.classifier")


class DomainClassifier:
    """
    Lightweight ML classifier for domain detection.

    Uses TF-IDF vectorization + Logistic Regression for fast, accurate
    domain classification. Trained on historical request logs.

    Attributes:
        vectorizer: TF-IDF vectorizer for text features
        model: Logistic Regression classifier
        domains: List of domain labels
        is_loaded: Whether the model is loaded and ready
    """

    def __init__(self, model_path: Path | None = None) -> None:
        """
        Initialize the classifier.

        Args:
            model_path: Path to saved model file (.pkl). If None, uses default location.
        """
        self.vectorizer: TfidfVectorizer | None = None
        self.model: LogisticRegression | None = None
        self.domains: list[str] = []
        self.is_loaded = False

        if model_path is None:
            # Default model location
            model_path = Path.home() / ".mascarade" / "models" / "domain_classifier.pkl"

        self.model_path = model_path

        # Try to load model if it exists
        if self.model_path.exists():
            try:
                self.load(self.model_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load classifier model from %s: %s",
                    self.model_path,
                    exc,
                )

    def predict(self, text: str) -> str | None:
        """
        Predict the domain for a given text.

        Args:
            text: Input text to classify

        Returns:
            Predicted domain label or None if model not loaded
        """
        if not self.is_loaded:
            logger.debug("Classifier not loaded, cannot predict")
            return None

        if not text or not text.strip():
            return None

        try:
            # Vectorize input text
            features = self.vectorizer.transform([text])

            # Predict domain
            prediction = self.model.predict(features)[0]

            logger.debug("Classified '%s...' as domain: %s", text[:50], prediction)
            return prediction

        except Exception as exc:
            logger.warning("Prediction failed: %s", exc)
            return None

    def predict_proba(self, text: str) -> dict[str, float] | None:
        """
        Predict domain probabilities for a given text.

        Args:
            text: Input text to classify

        Returns:
            Dictionary mapping domain labels to probabilities, or None if model not loaded
        """
        if not self.is_loaded:
            logger.debug("Classifier not loaded, cannot predict")
            return None

        if not text or not text.strip():
            return None

        try:
            # Vectorize input text
            features = self.vectorizer.transform([text])

            # Get probability distribution
            probas = self.model.predict_proba(features)[0]

            # Create domain -> probability mapping
            result = {domain: float(proba) for domain, proba in zip(self.domains, probas, strict=False)}

            logger.debug(
                "Domain probabilities for '%s...': %s",
                text[:50],
                {k: f"{v:.3f}" for k, v in sorted(result.items(), key=lambda x: -x[1])[:3]},
            )

            return result

        except Exception as exc:
            logger.warning("Probability prediction failed: %s", exc)
            return None

    def save(self, path: Path) -> None:
        """
        Save the trained model to disk.

        Args:
            path: Path to save the model (.pkl file)
        """
        if not self.is_loaded:
            raise ValueError("Cannot save: model not loaded")

        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save model components as pickle
        model_data = {
            "vectorizer": self.vectorizer,
            "model": self.model,
            "domains": self.domains,
        }

        with path.open("wb") as f:
            pickle.dump(model_data, f)

        logger.info("Saved classifier model to %s", path)

    def load(self, path: Path) -> None:
        """
        Load a trained model from disk.

        Args:
            path: Path to the model file (.pkl)

        Raises:
            FileNotFoundError: If model file doesn't exist
            ValueError: If model file is corrupted
        """
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        try:
            with path.open("rb") as f:
                model_data = pickle.load(f)

            self.vectorizer = model_data["vectorizer"]
            self.model = model_data["model"]
            self.domains = model_data["domains"]
            self.is_loaded = True

            logger.info(
                "Loaded classifier model from %s (%d domains: %s)",
                path,
                len(self.domains),
                ", ".join(self.domains),
            )

        except Exception as exc:
            logger.error("Failed to load model from %s: %s", path, exc)
            raise ValueError(f"Corrupted model file: {exc}") from exc

    def train(
        self,
        texts: list[str],
        labels: list[str],
        max_features: int = 5000,
        ngram_range: tuple[int, int] = (1, 2),
        **model_kwargs,
    ) -> dict[str, float]:
        """
        Train the classifier on labeled data.

        Args:
            texts: List of training texts
            labels: List of corresponding domain labels
            max_features: Maximum number of TF-IDF features
            ngram_range: N-gram range for TF-IDF (default: unigrams + bigrams)
            **model_kwargs: Additional kwargs for LogisticRegression

        Returns:
            Dictionary with training metrics

        Raises:
            ValueError: If training data is invalid
        """
        if len(texts) != len(labels):
            raise ValueError(f"Mismatched data: {len(texts)} texts, {len(labels)} labels")

        if len(texts) == 0:
            raise ValueError("No training data provided")

        try:
            # Import sklearn dependencies
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:
            raise ImportError(
                "scikit-learn is required for classifier training. "
                "Install with: pip install scikit-learn"
            ) from exc

        logger.info("Training classifier on %d samples", len(texts))

        # Get unique domains
        self.domains = sorted(set(labels))
        logger.info("Training for %d domains: %s", len(self.domains), ", ".join(self.domains))

        # Create TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            lowercase=True,
            strip_accents="unicode",
            stop_words="english",
        )

        # Vectorize training texts
        features = self.vectorizer.fit_transform(texts)
        logger.info("Extracted %d TF-IDF features", features.shape[1])

        # Train logistic regression classifier
        # Default parameters optimized for multi-class text classification
        default_kwargs = {
            "max_iter": 1000,
            "solver": "lbfgs",
            "class_weight": "balanced",  # Handle class imbalance
            "random_state": 42,
        }
        default_kwargs.update(model_kwargs)

        self.model = LogisticRegression(**default_kwargs)
        self.model.fit(features, labels)

        self.is_loaded = True

        # Calculate training accuracy
        train_accuracy = float(self.model.score(features, labels))

        logger.info("Training complete. Accuracy: %.2f%%", train_accuracy * 100)

        return {
            "accuracy": train_accuracy,
            "num_samples": len(texts),
            "num_domains": len(self.domains),
            "num_features": features.shape[1],
        }


# Global singleton instance for router integration
_classifier_instance: DomainClassifier | None = None


def get_classifier() -> DomainClassifier:
    """
    Get the global classifier instance.

    Returns:
        Shared DomainClassifier instance
    """
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = DomainClassifier()
    return _classifier_instance
