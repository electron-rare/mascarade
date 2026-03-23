#!/usr/bin/env python3
"""Train the ML domain classifier from prepared dataset.

This script trains a lightweight TF-IDF + Logistic Regression classifier
for domain routing. It loads the prepared training dataset and produces
a serialized model for production use.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from mascarade.router.classifier import DomainClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("train_classifier")


def load_dataset(dataset_path: Path) -> tuple[list[str], list[str]]:
    """
    Load training dataset from JSONL file.

    Args:
        dataset_path: Path to the dataset (.jsonl file)

    Returns:
        Tuple of (texts, labels)

    Raises:
        FileNotFoundError: If dataset file doesn't exist
        ValueError: If dataset is empty or malformed
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    texts: list[str] = []
    labels: list[str] = []

    logger.info("Loading dataset from %s", dataset_path)

    with dataset_path.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                text = sample.get("text", "").strip()
                domain = sample.get("domain", "").strip()

                if not text or not domain:
                    logger.warning(
                        "Line %d: missing text or domain, skipping", line_num
                    )
                    continue

                texts.append(text)
                labels.append(domain)

            except json.JSONDecodeError as exc:
                logger.warning("Line %d: invalid JSON, skipping: %s", line_num, exc)
                continue

    if not texts:
        raise ValueError("No valid samples found in dataset")

    logger.info("Loaded %d samples from dataset", len(texts))

    # Show domain distribution
    from collections import Counter

    domain_counts = Counter(labels)
    logger.info("Domain distribution:")
    for domain, count in domain_counts.most_common():
        logger.info(
            "  %s: %d samples (%.1f%%)", domain, count, 100 * count / len(labels)
        )

    return texts, labels


def split_dataset(
    texts: list[str],
    labels: list[str],
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Split dataset into train and test sets.

    Args:
        texts: List of text samples
        labels: List of corresponding labels
        test_size: Fraction of data to use for testing (default: 0.2)
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (X_train, X_test, y_train, y_test)
    """
    try:
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required for training. Install with: pip install scikit-learn"
        ) from exc

    return train_test_split(
        texts, labels, test_size=test_size, random_state=random_state
    )


def evaluate_classifier(
    classifier: DomainClassifier,
    texts: list[str],
    labels: list[str],
) -> dict[str, float]:
    """
    Evaluate classifier on test data.

    Args:
        classifier: Trained classifier
        texts: Test texts
        labels: Test labels

    Returns:
        Dictionary with evaluation metrics
    """
    try:
        from sklearn.metrics import accuracy_score, classification_report, f1_score
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required for evaluation. Install with: pip install scikit-learn"
        ) from exc

    logger.info("Evaluating classifier on %d test samples", len(texts))

    # Make predictions
    predictions = [classifier.predict(text) for text in texts]

    # Calculate metrics
    accuracy = accuracy_score(labels, predictions)
    f1 = f1_score(labels, predictions, average="weighted")

    logger.info("Test Accuracy: %.2f%%", accuracy * 100)
    logger.info("Weighted F1 Score: %.3f", f1)

    # Show detailed classification report
    logger.info(
        "\nClassification Report:\n%s", classification_report(labels, predictions)
    )

    return {
        "accuracy": accuracy,
        "f1_score": f1,
    }


def train_classifier(
    dataset_path: Path,
    output_path: Path,
    max_features: int = 5000,
    test_size: float = 0.2,
    epochs: int = 100,
    dry_run: bool = False,
) -> None:
    """
    Train the domain classifier.

    Args:
        dataset_path: Path to training dataset (.jsonl)
        output_path: Path to save trained model (.pkl)
        max_features: Maximum TF-IDF features
        test_size: Fraction of data for testing
        epochs: Training iterations (mapped to max_iter for LogisticRegression)
        dry_run: If True, train but don't save model
    """
    logger.info("Starting classifier training")
    logger.info("  Dataset: %s", dataset_path)
    logger.info("  Output: %s", output_path)
    logger.info("  Max features: %d", max_features)
    logger.info("  Test size: %.1f%%", test_size * 100)
    logger.info("  Epochs (max_iter): %d", epochs)

    # Load dataset
    texts, labels = load_dataset(dataset_path)

    # Split into train/test
    X_train, X_test, y_train, y_test = split_dataset(
        texts,
        labels,
        test_size=test_size,
    )

    logger.info("Split dataset: %d train, %d test", len(X_train), len(X_test))

    # Create and train classifier
    classifier = DomainClassifier()

    # Map epochs parameter to max_iter for LogisticRegression
    # Scale appropriately: epochs * 10 for convergence
    max_iter = epochs * 10

    train_metrics = classifier.train(
        X_train,
        y_train,
        max_features=max_features,
        ngram_range=(1, 2),  # Unigrams + bigrams
        max_iter=max_iter,
    )

    logger.info("Training metrics:")
    for key, value in train_metrics.items():
        logger.info("  %s: %s", key, value)

    # Evaluate on test set
    test_metrics = evaluate_classifier(classifier, X_test, y_test)

    # Calculate performance improvement over baseline (keyword matching)
    # Keyword matching baseline is typically 60-70% accurate
    baseline_accuracy = 0.65
    improvement = (
        (test_metrics["accuracy"] - baseline_accuracy) / baseline_accuracy * 100
    )

    logger.info("\nPerformance vs Baseline:")
    logger.info("  Baseline (keyword matching): %.1f%%", baseline_accuracy * 100)
    logger.info("  ML Classifier: %.1f%%", test_metrics["accuracy"] * 100)
    logger.info("  Improvement: %+.1f%%", improvement)

    if improvement >= 10:
        logger.info("  ✅ Meets ≥10%% improvement target")
    else:
        logger.warning("  ⚠️  Below 10%% improvement target")

    # Save model
    if dry_run:
        logger.info("\n[DRY RUN] Would save model to %s", output_path)
    else:
        classifier.save(output_path)
        logger.info("\n✅ Model saved to %s", output_path)

        # Save training metadata
        metadata_path = output_path.with_suffix(".meta.json")
        metadata = {
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "domains": classifier.domains,
            "max_features": max_features,
            "max_iter": max_iter,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "improvement_over_baseline": improvement,
        }

        with metadata_path.open("w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("✅ Metadata saved to %s", metadata_path)

    logger.info("\nTraining complete! 🎉")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train ML domain classifier for routing"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/classifier_training_dataset.jsonl"),
        help="Path to training dataset (JSONL format)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".mascarade" / "models" / "domain_classifier.pkl",
        help="Output path for trained model",
    )
    parser.add_argument(
        "--max-features",
        type=int,
        default=5000,
        help="Maximum TF-IDF features (default: 5000)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data for testing (default: 0.2)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Training epochs (mapped to max_iter, default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Train but don't save model",
    )

    args = parser.parse_args()

    try:
        # Generate dataset if it doesn't exist
        if not args.dataset.exists():
            logger.warning("Dataset not found at %s", args.dataset)
            logger.info("Generating dataset with prepare_classifier_dataset.py...")

            # Import and run dataset preparation
            prepare_script = Path(__file__).parent / "prepare_classifier_dataset.py"
            if prepare_script.exists():
                import subprocess

                result = subprocess.run(
                    [
                        sys.executable,
                        str(prepare_script),
                        "--output",
                        str(args.dataset),
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    logger.error("Dataset preparation failed: %s", result.stderr)
                    return 1

                logger.info("Dataset generated successfully")
            else:
                logger.error("Dataset preparation script not found: %s", prepare_script)
                return 1

        train_classifier(
            dataset_path=args.dataset,
            output_path=args.output,
            max_features=args.max_features,
            test_size=args.test_size,
            epochs=args.epochs,
            dry_run=args.dry_run,
        )

        return 0

    except Exception as exc:
        logger.error("Training failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
