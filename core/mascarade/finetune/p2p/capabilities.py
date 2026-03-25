"""P2P capabilities for fine-tuning agents."""

FT_CAPABILITIES = {
    "ft-research": "Search models and papers (HuggingFace + arXiv)",
    "ft-dataset": "Search and curate datasets",
    "ft-archive": "Version and publish to HuggingFace Hub",
    "ft-analysis": "Benchmarks and metrics evaluation",
    "ft-teacher": "Generate teacher data (requires LLM API keys)",
    "ft-student": "LoRA/QLoRA fine-tuning (requires GPU/Metal or CPU)",
    "ft-reinforcement": "DPO/RLHF improvement",
    "ft-validation": "End-to-end tests and red-teaming",
}

# Which machine should run which capability (based on actual hardware audit)
CAPABILITY_NODE_MAP = {
    "ft-research": ["GrosMac"],  # local, internet access
    "ft-dataset": ["GrosMac"],  # local, internet access
    "ft-archive": ["GrosMac"],  # HF token + internet
    "ft-analysis": ["KXKM-AI"],  # RTX 4090, fast inference
    "ft-teacher": ["GrosMac"],  # API keys (Claude/OpenAI)
    "ft-student": ["KXKM-AI"],  # RTX 4090 24GB — main training node
    "ft-reinforcement": ["KXKM-AI"],  # GPU for DPO training
    "ft-validation": ["CILS"],  # independent node, unbiased
}
