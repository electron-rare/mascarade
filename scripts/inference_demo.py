#!/usr/bin/env python3
"""
Script de démonstration d'inférence avec modèles locaux et datasets.
Utilise les datasets téléchargés et les modèles Mistral/CodeLlama.
"""

import json
import random
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Configuration
MODEL_PATH = "fine_tuned_models/mistral-7b-base"  # ou "codellama-7b-base"
# MODEL_PATH = "mistralai/Mistral-7B-Instruct-v0.1"  # Modèle léger (nécessite internet)
FORCE_CPU = True  # Désactiver CUDA pour compatibilité
DEVICE = "cpu" if FORCE_CPU else ("cuda" if torch.cuda.is_available() else "cpu")
USE_8BIT = True  # Quantification 8-bit pour réduire la mémoire
MAX_NEW_TOKENS = 100

# Charger le dataset STM32
STM32_DATASET = "datasets/stm32_dataset.jsonl"
GENERIC_DATASET = "datasets/generic_dataset.jsonl"


def load_dataset(filepath: str, limit: int = 100) -> list:
    """Charger un dataset depuis un fichier JSONL."""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            data.append(json.loads(line))
    return data


def load_model(model_path: str):
    """Charger le modèle et le tokenizer."""
    print(f"Chargement du modèle depuis {model_path}...")
    print(f"Utilisation de {DEVICE.upper()} avec quantification 8-bit: {USE_8BIT}")

    tokenizer = AutoTokenizer.from_pretrained(model_path)

    # Configuration pour CPU et mémoire réduite
    try:
        import bitsandbytes  # noqa: F401

        quantization_config = {
            "load_in_8bit": USE_8BIT,
            "device_map": "auto" if DEVICE == "cuda" else None,
        }
    except ImportError:
        print("bitsandbytes non disponible, désactivation de la quantification 8-bit")
        quantization_config = {
            "device_map": "auto" if DEVICE == "cuda" else None,
        }

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        **quantization_config,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    ).to(DEVICE)

    return tokenizer, model


def generate_response(
    tokenizer, model, prompt: str, max_new_tokens: int = MAX_NEW_TOKENS
):
    """Générer une réponse à partir du modèle."""
    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )

    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def demo_stm32_inference():
    """Démonstration avec le dataset STM32."""
    print("\n=== Démonstration STM32 ===")
    stm32_data = load_dataset(STM32_DATASET)

    # Sélectionner un exemple aléatoire
    example = random.choice(stm32_data)
    print(f"Catégorie: {example['category']}")
    print(f"Instruction: {example['instruction']}")
    print(f"Input: {example['input']}")

    # Générer une réponse
    prompt = f"STM32 HAL code example for: {example['instruction']}\n\n{example['input']}\n\nCode:"
    response = generate_response(tokenizer, model, prompt)

    print("\nRéponse générée:")
    print(response[:500] + "..." if len(response) > 500 else response)


def demo_generic_inference():
    """Démonstration avec le dataset générique."""
    print("\n=== Démonstration Générique ===")
    generic_data = load_dataset(GENERIC_DATASET)

    # Sélectionner un exemple aléatoire
    example = random.choice(generic_data)
    print(f"Texte source: {example['text'][:200]}...")

    # Générer un résumé
    prompt = f"Summarize the following text in 3 sentences:\n\n{example['text'][:500]}\n\nSummary:"
    response = generate_response(tokenizer, model, prompt)

    print("\nRésumé généré:")
    print(response)


def interactive_inference():
    """Mode interactif pour tester ses propres prompts."""
    print("\n=== Mode Interactif ===")
    print("Entrez votre prompt (ou 'quit' pour quitter):")

    while True:
        try:
            user_input = input(">>> ")
            if user_input.lower() in ["quit", "exit", "q"]:
                break

            response = generate_response(tokenizer, model, user_input)
            print("\nRéponse:")
            print(response)
            print("\n---\n")
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    # Vérifier que les fichiers existent
    if not Path(MODEL_PATH).exists():
        print(f"Erreur: Le modèle {MODEL_PATH} n'existe pas.")
        print("Téléchargement du modèle léger Mistral-7B-Instruct-v0.1...")
        MODEL_PATH = "mistralai/Mistral-7B-Instruct-v0.1"

    if not Path(STM32_DATASET).exists():
        print(
            f"Avertissement: {STM32_DATASET} non trouvé. Seule la démo générique sera disponible."
        )

    # Charger le modèle
    try:
        tokenizer, model = load_model(MODEL_PATH)
        print(f"Modèle chargé sur {DEVICE}")
    except Exception as e:
        print(f"Erreur lors du chargement du modèle: {e}")
        print("\nOptions:")
        print("1. Télécharger les poids complets du modèle local")
        print("2. Utiliser un modèle plus petit (nécessite internet)")
        print("3. Quitter")
        exit(1)

    # Lancer les démonstrations
    if Path(STM32_DATASET).exists():
        demo_stm32_inference()

    if Path(GENERIC_DATASET).exists():
        demo_generic_inference()

    # Mode interactif
    interactive_inference()

    print("\nFin de la démonstration.")
