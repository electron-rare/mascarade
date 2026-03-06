#!/usr/bin/env python3
"""
Model Download Script for Fine-Tuning
Handles authentication and downloads models to local directory
"""

import os
import subprocess
from huggingface_hub import login, whoami


def check_huggingface_login():
    """Check if user is logged in to HuggingFace Hub"""
    try:
        user = whoami()
        print(f"✓ Logged in as: {user['name']} ({user['email']})")
        return True
    except Exception as e:
        print(f"✗ Not logged in: {e}")
        return False


def huggingface_login():
    """Prompt user to login to HuggingFace"""
    print("\n🔐 HuggingFace Login Required")
    print("Please enter your HuggingFace token from:")
    print("https://huggingface.co/settings/tokens")

    try:
        login()
        print("✓ Login successful!")
        return True
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return False


def download_model(model_name, local_dir="./models"):
    """Download model using huggingface-cli"""
    model_dir = os.path.join(local_dir, model_name.replace("/", "_"))

    print(f"\n📥 Downloading {model_name}...")
    print(f"   Target: {model_dir}")

    try:
        # Create directory
        os.makedirs(model_dir, exist_ok=True)

        # Download using huggingface-cli
        cmd = [
            "huggingface-cli",
            "download",
            model_name,
            "--local-dir",
            model_dir,
            "--local-dir-use-symlinks",
            "False",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✓ Download completed: {model_dir}")
            print(f"  Size: {get_dir_size(model_dir):.2f} MB")
            return model_dir
        else:
            print(f"✗ Download failed: {result.stderr}")
            return None

    except Exception as e:
        print(f"✗ Download error: {e}")
        return None


def get_dir_size(dir_path):
    """Get directory size in MB"""
    total = 0
    for entry in os.scandir(dir_path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_dir_size(entry.path)
    return total / (1024 * 1024)


def main():
    print("=" * 60)
    print("📥 MODEL DOWNLOAD SCRIPT")
    print("=" * 60)

    # Check/login
    if not check_huggingface_login():
        if not huggingface_login():
            print("\n⚠️  Cannot proceed without HuggingFace login")
            print("    Visit: https://huggingface.co/settings/tokens")
            return

    # Model selection
    models = {
        "1": {
            "name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            "size": "2.1GB",
            "vram": "3-4GB",
        },
        "2": {
            "name": "openlm-research/open_llama_3b_v2",
            "size": "6.3GB",
            "vram": "5-6GB",
        },
        "3": {"name": "codellama/CodeLlama-7b-hf", "size": "14GB", "vram": "7-8GB"},
        "4": {"name": "facebook/opt-125m", "size": "250MB", "vram": "1-2GB"},
        "5": {"name": "microsoft/phi-2", "size": "2.7GB", "vram": "3-4GB"},
    }

    print("\n📋 Available Models:")
    print("-" * 40)
    for key, info in models.items():
        print(f"{key}. {info['name']}")
        print(f"   Size: {info['size']}, VRAM: {info['vram']}")
    print("-" * 40)

    # Get user choice
    choice = input("\nEnter model number (1-5): ").strip()

    if choice not in models:
        print("✗ Invalid choice")
        return

    model_info = models[choice]

    # Check VRAM compatibility
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        required_vram = float(model_info["vram"].split("-")[0])

        if gpu_mem < required_vram:
            print(f"\n⚠️  WARNING: Your GPU has {gpu_mem:.1f}GB VRAM")
            print(f"   Model requires {model_info['vram']}")
            confirm = input("   Continue anyway? (y/n): ").lower()
            if confirm != "y":
                return

    # Download
    print(f"\n🚀 Starting download of {model_info['name']}...")
    local_path = download_model(model_info["name"])

    if local_path:
        print("\n✅ SUCCESS!")
        print(f"Model saved to: {local_path}")
        print("\nTo use this model:")
        print("  python fine_tuning_base.py --domain generic --train")
        print(f"  --model-path {local_path}")
    else:
        print("\n❌ Download failed")


def show_manual_download():
    """Show manual download instructions"""
    print("\n" + "=" * 60)
    print("📥 MANUAL DOWNLOAD INSTRUCTIONS")
    print("=" * 60)

    print("\n1. Get your HuggingFace token:")
    print("   https://huggingface.co/settings/tokens")

    print("\n2. Login via command line:")
    print("   huggingface-cli login")

    print("\n3. Download models manually:")
    print("   huggingface-cli download TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    print("   huggingface-cli download openlm-research/open_llama_3b_v2")

    print("\n4. Use in fine-tuning:")
    print("   python fine_tuning_base.py --domain kicad --train")
    print("   --model-path ./models/TinyLlama_TinyLlama-1.1B-Chat-v1.0")

    print("\n💡 Tip: Use --small flag for automatic model selection")
    print("=" * 60)


if __name__ == "__main__":
    try:
        import torch

        main()
    except ImportError:
        print("PyTorch not available, showing manual instructions...")
        show_manual_download()
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        show_manual_download()
