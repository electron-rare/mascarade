#!/usr/bin/env python3
"""
Script for fine-tuning BERT classifier on production data.

This script:
1. Loads production query data from ClickHouse
2. Preprocesses and balances the dataset
3. Fine-tunes the BERT model
4. Evaluates performance
5. Saves the optimized model
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bert_finetuning")

# Import after logging is configured
from mascarade.analytics.clickhouse_logger import get_clickhouse_client
from mascarade.router.bert_classifier import BertDomainClassifier


def load_production_data(days: int = 7) -> tuple[list[str], list[str]]:
    """
    Load production query data from ClickHouse.

    Args:
        days: Number of days of data to load

    Returns:
        Tuple of (texts, labels)
    """
    logger.info("Loading production data from last %d days", days)

    try:
        client = get_clickhouse_client()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Query to get successful routing decisions with their domains
        query = f"""
        SELECT
            query_text,
            detected_domain
        FROM routing_decisions
        WHERE
            success = 1
            AND detected_domain != ''
            AND created_at >= '{start_date.isoformat()}'
            AND created_at <= '{end_date.isoformat()}'
        ORDER BY created_at DESC
        LIMIT 10000
        """

        result = client.execute(query)

        texts = []
        labels = []

        for row in result:
            query_text, domain = row
            if query_text and domain:
                texts.append(query_text)
                labels.append(domain)

        logger.info("Loaded %d production samples", len(texts))
        return texts, labels

    except Exception as e:
        logger.error("Failed to load production data: %s", e)
        raise


def balance_dataset(
    texts: list[str], labels: list[str], min_samples: int = 50
) -> tuple[list[str], list[str]]:
    """
    Balance the dataset to ensure all domains have sufficient samples.

    Args:
        texts: List of query texts
        labels: List of corresponding domains
        min_samples: Minimum number of samples per domain

    Returns:
        Balanced (texts, labels) tuples
    """
    import random
    from collections import defaultdict

    logger.info("Balancing dataset...")

    # Group by domain
    domain_groups = defaultdict(list)
    for text, label in zip(texts, labels, strict=False):
        domain_groups[label].append(text)

    # Filter domains with enough samples
    balanced_texts = []
    balanced_labels = []

    for domain, domain_texts in domain_groups.items():
        if len(domain_texts) >= min_samples:
            # Take up to min_samples from each domain
            selected_texts = random.sample(domain_texts, min_samples)
            balanced_texts.extend(selected_texts)
            balanced_labels.extend([domain] * len(selected_texts))
            logger.debug("Domain %s: %d samples", domain, len(selected_texts))

    logger.info(
        "Balanced dataset: %d samples across %d domains",
        len(balanced_texts),
        len(set(balanced_labels)),
    )

    return balanced_texts, balanced_labels


def fine_tune_bert(texts: list[str], labels: list[str]) -> BertDomainClassifier:
    """
    Fine-tune BERT classifier on production data.

    Args:
        texts: List of query texts
        labels: List of corresponding domains

    Returns:
        Fine-tuned BERT classifier
    """
    logger.info("Starting BERT fine-tuning...")

    try:
        # Initialize classifier
        model_path = (
            Path.home() / ".mascarade" / "models" / "bert_domain_classifier_prod"
        )
        classifier = BertDomainClassifier(model_path=model_path)

        # Training parameters
        training_params = {
            "model_name": "bert-base-uncased",
            "num_train_epochs": 3,
            "per_device_train_batch_size": 8,
            "learning_rate": 2e-5,
            "output_dir": str(model_path),
            "logging_dir": str(model_path / "logs"),
            "logging_steps": 10,
            "save_strategy": "epoch",
            "evaluation_strategy": "epoch",
            "load_best_model_at_end": True,
        }

        # Train the model
        results = classifier.train(texts, labels, **training_params)

        logger.info("Fine-tuning completed successfully")
        logger.info("Training results: %s", results)

        return classifier

    except Exception as e:
        logger.error("Fine-tuning failed: %s", e)
        raise


def evaluate_classifier(
    classifier: BertDomainClassifier, test_texts: list[str], test_labels: list[str]
) -> dict:
    """
    Evaluate classifier performance on test data.

    Args:
        classifier: Trained BERT classifier
        test_texts: List of test query texts
        test_labels: List of corresponding domains

    Returns:
        Dictionary with evaluation metrics
    """
    logger.info("Evaluating classifier performance...")

    try:
        from sklearn.metrics import accuracy_score, classification_report

        # Predict on test data
        predictions = []
        for text in test_texts:
            pred = classifier.predict(text)
            predictions.append(pred if pred else "unknown")

        # Calculate metrics
        accuracy = accuracy_score(test_labels, predictions)
        report = classification_report(test_labels, predictions, output_dict=True)

        metrics = {
            "accuracy": accuracy,
            "classification_report": report,
            "num_samples": len(test_labels),
        }

        logger.info("Evaluation completed")
        logger.info("Accuracy: %.4f", accuracy)

        return metrics

    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        raise


def main():
    """
    Main fine-tuning pipeline.
    """
    logger.info("Starting BERT fine-tuning pipeline")

    try:
        # Step 1: Load production data
        texts, labels = load_production_data(days=14)

        if len(texts) < 100:
            logger.warning(
                "Insufficient data (%d samples). Need at least 100.", len(texts)
            )
            return

        # Step 2: Balance dataset
        balanced_texts, balanced_labels = balance_dataset(texts, labels, min_samples=20)

        # Step 3: Split into train/test
        from sklearn.model_selection import train_test_split

        train_texts, test_texts, train_labels, test_labels = train_test_split(
            balanced_texts, balanced_labels, test_size=0.2, random_state=42
        )

        logger.info(
            "Train set: %d samples, Test set: %d samples",
            len(train_texts),
            len(test_texts),
        )

        # Step 4: Fine-tune BERT
        classifier = fine_tune_bert(train_texts, train_labels)

        # Step 5: Evaluate
        metrics = evaluate_classifier(classifier, test_texts, test_labels)

        # Step 6: Save final model
        save_path = Path("/app/models/bert_domain_classifier_production")
        classifier.save(save_path)
        logger.info("Model saved to %s", save_path)

        # Step 7: Save metrics
        metrics_path = save_path / "evaluation_metrics.json"
        import json

        with metrics_path.open("w") as f:
            json.dump(metrics, f, indent=2)

        logger.info("Fine-tuning pipeline completed successfully")
        logger.info("Final metrics: %s", metrics)

        return True

    except Exception as e:
        logger.error("Fine-tuning pipeline failed: %s", e)
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
