# 🎯 Fine-Tuning Guide for Mascarade

## 📋 Quick Start

### 1. Test Environment
```bash
source venv_tuning/bin/activate
python test_environment.py
```

### 2. Run Demo (No Downloads)
```bash
python fine_tuning_demo.py
```

### 3. Download Models (Recommended)
```bash
python download_models.py
# Follow interactive prompts
```

### 4. Fine-Tune
```bash
# For KiCad/EDA (1.1B model, 3-4GB VRAM)
python fine_tuning_base.py --domain kicad --train --small --short-seq

# For STM32/FPGA (1.1B model, 3-4GB VRAM)
python fine_tuning_base.py --domain stm32 --train --small --short-seq

# For Generic Code (125M model, 1-2GB VRAM)
python fine_tuning_base.py --domain generic --train --ultrasmall --short-seq
```

## 🛠️ Environment Setup

### Requirements
- **GPU**: NVIDIA Quadro P2000 (4.9GB VRAM)
- **CUDA**: 11.8
- **PyTorch**: 2.2.0+cu118
- **Python**: 3.12

### Install Dependencies
```bash
# Create virtual environment
python3 -m venv venv_tuning
source venv_tuning/bin/activate

# Install requirements
pip install torch==2.2.0+cu118 torchvision==0.17.0+cu118 torchaudio==2.2.0+cu118 --index-url https://download.pytorch.org/whl/cu118
pip install transformers==4.57.6 peft==0.18.1 accelerate==1.12.0 bitsandbytes==0.43.2
pip install datasets psutil GPUtil protobuf tiktoken huggingface_hub[cli]
```

## 📚 Available Models

### For Quadro P2000 (4.9GB VRAM)

| Model | Size | VRAM Req | Command Flag |
|-------|------|----------|---------------|
| TinyLlama-1.1B | 2.1GB | 3-4GB | `--small` |
| OPT-125M | 250MB | 1-2GB | `--ultrasmall` |
| Phi-2 | 2.7GB | 3-4GB | `--ultrasmall` |

### Larger Models (Requires >6GB VRAM)

| Model | Size | VRAM Req |
|-------|------|----------|
| Open-Llama-3B | 6.3GB | 5-6GB |
| CodeLlama-7B | 14GB | 7-8GB |

## 🎯 Domain-Specific Fine-Tuning

### KiCad/PCB/EDA
```bash
# Create sample dataset
python fine_tuning_base.py  # Generates sample_kicad_dataset.txt

# Fine-tune with 1.1B model
python fine_tuning_base.py --domain kicad --train --small --short-seq

# Evaluate
python fine_tuning_base.py --domain kicad --evaluate
```

### STM32/FPGA
```bash
# Create sample dataset
python fine_tuning_base.py  # Generates sample_stm32_dataset.txt

# Fine-tune with 1.1B model
python fine_tuning_base.py --domain stm32 --train --small --short-seq

# Evaluate
python fine_tuning_base.py --domain stm32 --evaluate
```

### Generic Code
```bash
# Create sample dataset
python fine_tuning_base.py  # Generates sample_generic_dataset.txt

# Fine-tune with 125M model (fits in 4.9GB)
python fine_tuning_base.py --domain generic --train --ultrasmall --short-seq

# Evaluate
python fine_tuning_base.py --domain generic --evaluate
```

## 🔧 Advanced Configuration

### Custom Dataset
```bash
# Format: One sample per line, blank line between samples
cat > my_dataset.txt << EOF
# KiCad Schematic
def generate_footprint():
    # Code here

# PCB Design Rules
(rule "Clearance" (min 0.2mm))
EOF

# Train with custom dataset
python fine_tuning_base.py --domain kicad --train --small --dataset my_dataset.txt
```

### Training Parameters
```bash
# Adjust epochs
python fine_tuning_base.py --domain kicad --train --small --epochs 5

# Disable quantization (not recommended for 4.9GB VRAM)
python fine_tuning_base.py --domain kicad --train --small --no-quant
```

## 💡 Memory Optimization Tips

### For Quadro P2000 (4.9GB VRAM)

1. **Use smaller models**: `--small` or `--ultrasmall`
2. **Shorter sequences**: `--short-seq` (256 instead of 512)
3. **Batch size**: Automatically set to 1
4. **Gradient accumulation**: Compensates for small batches
5. **Mixed precision**: FP16 enabled by default
6. **Gradient checkpointing**: Reduces memory usage

### Environment Variables
```bash
# Reduce memory fragmentation
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Enable TF32 for faster training
export NVIDIA_TF32_OVERRIDE=1
```

## 🐛 Troubleshooting

### CUDA Out of Memory
**Error**: `CUDA out of memory`

**Solutions**:
1. Use `--ultrasmall` instead of `--small`
2. Add `--short-seq` flag
3. Reduce dataset sample length
4. Check for memory leaks with `nvidia-smi`

### Model Access Denied
**Error**: `403 Client Error` or `GatedRepoError`

**Solutions**:
1. Login to HuggingFace: `huggingface-cli login`
2. Request model access on HuggingFace website
3. Use open-source alternatives
4. Download models manually and use `--model-path`

### PyTorch Version Issues
**Error**: `requires PyTorch >= 2.4`

**Solutions**:
1. Use compatible models (TinyLlama, OPT, etc.)
2. Upgrade PyTorch if possible
3. Use the demo script for testing

## 📊 Performance Expectations

### Quadro P2000 (4.9GB VRAM)

| Model Size | Batch Size | Seq Length | Speed (tok/s) | VRAM Usage |
|------------|------------|------------|---------------|-------------|
| 125M | 1 | 256 | 50-100 | ~2GB |
| 1.1B | 1 | 256 | 20-50 | ~3.5GB |
| 3B | 1 | 256 | 10-20 | ~5GB (OOM likely) |

### Training Time Estimates

| Dataset Size | Epochs | 1.1B Model | 125M Model |
|--------------|--------|------------|-------------|
| 100 samples | 3 | ~10 min | ~2 min |
| 1,000 samples | 3 | ~60 min | ~15 min |
| 10,000 samples | 3 | ~10 hours | ~2 hours |

## 🎓 Learning Resources

### LoRA (Low-Rank Adaptation)
- Paper: https://arxiv.org/abs/2106.09685
- HuggingFace Docs: https://huggingface.co/docs/peft/conceptual_guides/lora

### Fine-Tuning Best Practices
- HuggingFace Guide: https://huggingface.co/docs/transformers/training
- PEFT Documentation: https://huggingface.co/docs/peft/index

### Memory Optimization
- PyTorch Docs: https://pytorch.org/docs/stable/notes/cuda.html
- NVIDIA Guide: https://developer.nvidia.com/blog/optimizing-pytorch-for-gpu/

## 📝 Changelog

### v1.0 (2026-03-04)
- Initial release
- Quadro P2000 optimization
- 3 domain configurations (KiCad, STM32, Generic)
- Memory-efficient training pipeline
- Demo mode for testing

### v1.1 (Planned)
- Automatic model selection based on VRAM
- Multi-GPU support
- Quantization-aware training
- Better evaluation metrics

## 🔗 Useful Links

- HuggingFace Hub: https://huggingface.co/models
- PyTorch: https://pytorch.org/
- PEFT: https://github.com/huggingface/peft
- Transformers: https://github.com/huggingface/transformers

## 📋 TODO List

See `TODO_TUNNING_PARTY.md` for complete task list and progress tracking.

## 📄 License

This guide and accompanying scripts are provided as-is for educational and research purposes. Check individual model licenses before commercial use.

---
*Last updated: 2026-03-04*
*Maintainer: Mistral Vibe 🤖*
