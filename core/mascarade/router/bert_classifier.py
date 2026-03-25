"""BERT-based domain classifier for enhanced routing accuracy.

This classifier uses a fine-tuned BERT model to detect domains from user queries
with higher accuracy than keyword-based or TF-IDF approaches. The model is designed
for production use with optimized inference speed and memory footprint.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
from transformers import BertForSequenceClassification, BertTokenizer

logger = logging.getLogger("mascarade.router.bert_classifier")


class BertDomainClassifier:
    """
    BERT-based domain classifier for routing.

    Uses a fine-tuned BERT model for high-accuracy domain detection.
    Supports GPU acceleration when available and falls back to CPU.

    Attributes:
        model: BERT sequence classification model
        tokenizer: BERT tokenizer
        device: Torch device (cuda/cpu)
        domains: List of domain labels
        is_loaded: Whether the model is loaded and ready
        max_length: Maximum sequence length for BERT
    """

    def __init__(
        self,
        model_path: Path | None = None,
        max_length: int = 128,
        use_gpu: bool = True,
    ) -> None:
        """
        Initialize the BERT classifier.

        Args:
            model_path: Path to saved BERT model directory
            max_length: Maximum sequence length for BERT tokenizer
            use_gpu: Whether to use GPU if available
        """
        self.model: BertForSequenceClassification | None = None
        self.tokenizer: BertTokenizer | None = None
        self.device = torch.device(
            "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        )
        self.domains: list[str] = []
        self.is_loaded = False
        self.max_length = max_length

        if model_path is None:
            # Default model location
            model_path = (
                Path.home() / ".mascarade" / "models" / "bert_domain_classifier"
            )

        self.model_path = model_path

        # Try to load model if it exists
        if self.model_path.exists():
            try:
                self.load(self.model_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load BERT classifier model from %s: %s",
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
            logger.debug("BERT classifier not loaded, cannot predict")
            return None

        if not text or not text.strip():
            return None

        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length,
                padding="max_length",
            ).to(self.device)

            # Predict domain
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                predicted_idx = torch.argmax(logits, dim=1).item()

            prediction = self.domains[predicted_idx]

            logger.debug("BERT classified '%s...' as domain: %s", text[:50], prediction)
            return prediction

        except Exception as exc:
            logger.warning("BERT prediction failed: %s", exc)
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
            logger.debug("BERT classifier not loaded, cannot predict")
            return None

        if not text or not text.strip():
            return None

        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length,
                padding="max_length",
            ).to(self.device)

            # Get probability distribution
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=1)[0]

            # Create domain -> probability mapping
            result = {
                domain: float(prob)
                for domain, prob in zip(self.domains, probs, strict=False)
            }

            logger.debug(
                "BERT domain probabilities for '%s...': %s",
                text[:50],
                {
                    k: f"{v:.3f}"
                    for k, v in sorted(result.items(), key=lambda x: -x[1])[:3]
                },
            )

            return result

        except Exception as exc:
            logger.warning("BERT probability prediction failed: %s", exc)
            return None

    def save(self, path: Path) -> None:
        """
        Save the trained model to disk.

        Args:
            path: Path to save the model
        """
        if not self.is_loaded:
            raise ValueError("Cannot save: model not loaded")

        # Create directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)

        # Save model and tokenizer
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)

        # Save domains list
        domains_file = path / "domains.txt"
        domains_file.write_text("\n".join(self.domains))

        logger.info("Saved BERT classifier model to %s", path)

    def load(self, path: Path) -> None:
        """
        Load a trained model from disk.

        Args:
            path: Path to the model directory

        Raises:
            FileNotFoundError: If model directory doesn't exist
            ValueError: If model files are corrupted
        """
        if not path.exists():
            raise FileNotFoundError(f"Model directory not found: {path}")

        try:
            # Load tokenizer and model
            self.tokenizer = BertTokenizer.from_pretrained(path)
            self.model = BertForSequenceClassification.from_pretrained(path)
            self.model.to(self.device)
            self.model.eval()

            # Load domains
            domains_file = path / "domains.txt"
            if domains_file.exists():
                self.domains = domains_file.read_text().strip().split("\n")
            else:
                # Try to infer domains from model config
                num_labels = self.model.config.num_labels
                self.domains = [f"domain_{i}" for i in range(num_labels)]

            self.is_loaded = True

            logger.info(
                "Loaded BERT classifier model from %s (%d domains: %s)",
                path,
                len(self.domains),
                ", ".join(self.domains),
            )

        except Exception as exc:
            logger.error("Failed to load BERT model from %s: %s", path, exc)
            raise ValueError(f"Corrupted model files: {exc}") from exc

    def train(
        self,
        texts: list[str],
        labels: list[str],
        model_name: str = "bert-base-uncased",
        num_train_epochs: int = 3,
        per_device_train_batch_size: int = 8,
        learning_rate: float = 2e-5,
        **trainer_kwargs,
    ) -> dict[str, Any]:
        """
        Train the BERT classifier on labeled data.

        Args:
            texts: List of training texts
            labels: List of corresponding domain labels
            model_name: Pretrained BERT model name
            num_train_epochs: Number of training epochs
            per_device_train_batch_size: Batch size for training
            learning_rate: Learning rate for optimizer
            **trainer_kwargs: Additional kwargs for Trainer

        Returns:
            Dictionary with training metrics

        Raises:
            ValueError: If training data is invalid
        """
        if len(texts) != len(labels):
            raise ValueError(
                f"Mismatched data: {len(texts)} texts, {len(labels)} labels"
            )

        if len(texts) == 0:
            raise ValueError("No training data provided")

        try:
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import LabelEncoder
            from transformers import Trainer, TrainingArguments
        except ImportError as exc:
            raise ImportError(
                "Required packages not installed. Install with: pip install transformers scikit-learn"
            ) from exc

        logger.info("Training BERT classifier on %d samples", len(texts))

        # Encode labels
        label_encoder = LabelEncoder()
        encoded_labels = label_encoder.fit_transform(labels)
        self.domains = label_encoder.classes_.tolist()

        logger.info(
            "Training for %d domains: %s", len(self.domains), ", ".join(self.domains)
        )

        # Split data
        train_texts, val_texts, train_labels, val_labels = train_test_split(
            texts, encoded_labels, test_size=0.1, random_state=42
        )

        # Load tokenizer and model
        self.tokenizer = BertTokenizer.from_pretrained(model_name)
        self.model = BertForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(self.domains),
        )
        self.model.to(self.device)

        # Tokenize datasets
        train_encodings = self.tokenizer(
            train_texts, truncation=True, padding=True, max_length=self.max_length
        )
        val_encodings = self.tokenizer(
            val_texts, truncation=True, padding=True, max_length=self.max_length
        )

        class Dataset(torch.utils.data.Dataset):
            def __init__(self, encodings, labels):
                self.encodings = encodings
                self.labels = labels

            def __getitem__(self, idx):
                item = {
                    key: torch.tensor(val[idx]) for key, val in self.encodings.items()
                }
                item["labels"] = torch.tensor(self.labels[idx])
                return item

            def __len__(self):
                return len(self.labels)

        train_dataset = Dataset(train_encodings, train_labels)
        val_dataset = Dataset(val_encodings, val_labels)

        # Training arguments
        training_args = TrainingArguments(
            output_dir=str(self.model_path),
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            learning_rate=learning_rate,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            logging_dir=str(self.model_path / "logs"),
            logging_steps=10,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            **trainer_kwargs,
        )

        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
        )

        # Train
        trainer.train()

        # Evaluate
        eval_results = trainer.evaluate()
        self.is_loaded = True

        logger.info(
            "BERT training complete. Eval loss: %.4f", eval_results["eval_loss"]
        )

        return {
            "eval_loss": eval_results["eval_loss"],
            "num_samples": len(texts),
            "num_domains": len(self.domains),
            "epochs": num_train_epochs,
        }


# Global singleton instance for router integration
_bert_classifier_instance: BertDomainClassifier | None = None


def get_bert_classifier() -> BertDomainClassifier:
    """
    Get the global BERT classifier instance.

    Returns:
        Shared BertDomainClassifier instance
    """
    global _bert_classifier_instance
    if _bert_classifier_instance is None:
        _bert_classifier_instance = BertDomainClassifier()
    return _bert_classifier_instance
