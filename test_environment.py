#!/usr/bin/env python3
"""
Test script for fine-tuning environment
"""

import torch
import transformers
import peft
import accelerate
import bitsandbytes
import numpy as np
import psutil
import GPUtil


def test_gpu():
    """Test GPU availability and capabilities"""
    print("=" * 60)
    print("GPU TEST")
    print("=" * 60)

    # GPU info
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU device count: {torch.cuda.device_count()}")

    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        print(f"GPU: {gpu}")
        print(f"Compute capability: {props.major}.{props.minor}")
        print(f"Total memory: {props.total_memory / 1024**3:.2f} GB")
        print(f"Multiprocessor count: {props.multi_processor_count}")

        # Test memory allocation
        try:
            test_tensor = torch.randn(1000, 1000, device="cuda")
            print("✓ Successfully allocated tensor on GPU")
            del test_tensor
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"✗ Failed to allocate tensor on GPU: {e}")
    else:
        print("✗ No GPU available")

    print()


def test_libraries():
    """Test all required libraries"""
    print("=" * 60)
    print("LIBRARY TEST")
    print("=" * 60)

    libraries = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "accelerate": accelerate.__version__,
        "bitsandbytes": getattr(bitsandbytes, "__version__", "unknown"),
        "numpy": np.__version__,
    }

    for lib, version in libraries.items():
        print(f"✓ {lib}: {version}")

    print()


def test_memory():
    """Test system memory"""
    print("=" * 60)
    print("MEMORY TEST")
    print("=" * 60)

    # System memory
    mem = psutil.virtual_memory()
    print(f"System RAM: {mem.total / 1024**3:.2f} GB")
    print(f"Available RAM: {mem.available / 1024**3:.2f} GB")
    print(f"Used RAM: {mem.used / 1024**3:.2f} GB")
    print(f"RAM usage: {mem.percent}%")

    # GPU memory
    if torch.cuda.is_available():
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            print(f"GPU memory total: {gpu.memoryTotal} MB")
            print(f"GPU memory used: {gpu.memoryUsed} MB")
            print(f"GPU memory free: {gpu.memoryFree} MB")
            print(f"GPU usage: {gpu.load * 100}%")

    print()


def test_transformers():
    """Test transformers functionality"""
    print("=" * 60)
    print("TRANSFORMERS TEST")
    print("=" * 60)

    try:
        # Test tokenizer
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        test_text = "Hello, this is a test for fine-tuning environment."
        encoded = tokenizer(test_text)
        print(f"✓ Tokenizer working: {len(encoded['input_ids'])} tokens")

        # Test model loading (small model)
        from transformers import AutoModelForCausalLM

        model = AutoModelForCausalLM.from_pretrained("gpt2", device_map="auto")
        print("✓ Model loading working")

        # Test inference
        inputs = tokenizer("Hello, my name is", return_tensors="pt").to(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        outputs = model.generate(**inputs, max_new_tokens=10)
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"✓ Inference working: {result}")

    except Exception as e:
        print(f"✗ Transformers test failed: {e}")

    print()


def test_peft():
    """Test PEFT functionality"""
    print("=" * 60)
    print("PEFT TEST")
    print("=" * 60)

    try:
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM

        # Load small model
        model = AutoModelForCausalLM.from_pretrained("gpt2")

        # Create LoRA config
        lora_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["c_attn"],
            lora_dropout=0.1,
            bias="none",
            task_type="CAUSAL_LM",
        )

        # Apply LoRA
        model = get_peft_model(model, lora_config)
        print(f"✓ PEFT LoRA working: {model.print_trainable_parameters()}")

    except Exception as e:
        print(f"✗ PEFT test failed: {e}")

    print()


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("FINE-TUNING ENVIRONMENT TEST")
    print("=" * 60 + "\n")

    test_gpu()
    test_libraries()
    test_memory()
    test_transformers()
    test_peft()

    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("✓ Environment is ready for fine-tuning!")


if __name__ == "__main__":
    main()
