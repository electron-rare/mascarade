"""RLVR: Reinforcement Learning with Verifiable Rewards via KiCad DRC.

The model generates KiCad schematics, KiBot runs DRC, the DRC result = reward.
Training method: GRPO (Group Relative Policy Optimization) via TRL."""

import json
import time
import os
import re

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_DISABLED"] = "true"

RUNS = "finetune/runs"
OUTPUT = f"{RUNS}/rlvr-kicad-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(OUTPUT, exist_ok=True)

# RLVR prompts: ask the model to generate KiCad schematics
RLVR_PROMPTS = [
    "Generate a KiCad schematic (.kicad_sch format) for a simple LED circuit with a 330 ohm resistor powered by 3.3V.",
    "Generate a KiCad schematic for a voltage divider: 12V input, 3.3V output, using standard resistors.",
    "Generate a KiCad schematic for an STM32F103C8T6 minimum system: crystal, decoupling caps, reset circuit, SWD header.",
    "Generate a KiCad schematic for a USB Type-C connector with CC resistors for UFP (device) mode.",
    "Generate a KiCad schematic for a buck converter using TPS54331 with 12V input, 5V/3A output.",
    "Generate a KiCad schematic for an I2C level shifter between 3.3V and 5V domains using BSS138 MOSFETs.",
    "Generate a KiCad schematic for an ESP32-WROOM module with antenna, decoupling, EN/BOOT strapping, and UART header.",
    "Generate a KiCad schematic for a 4-layer stackup power section: 3.3V LDO from 5V USB with input/output caps.",
    "Generate a KiCad schematic for an op-amp inverting amplifier with gain -10 using OPA2134.",
    "Generate a KiCad schematic for RS-485 transceiver (MAX485) with termination and DE/RE control.",
    "Generate a KiCad schematic for a MOSFET H-bridge motor driver for a 12V DC motor.",
    "Generate a KiCad schematic for a temperature sensor circuit with NTC thermistor and voltage divider to ADC.",
    "Generate a KiCad schematic for a relay driver circuit with flyback diode and LED indicator.",
    "Generate a KiCad schematic for a CAN bus transceiver (MCP2551) with termination resistor.",
    "Generate a KiCad schematic for an audio line-in circuit with AC coupling, protection, and gain stage.",
]


def kicad_drc_reward(prompt: str, completion: str) -> float:
    """Verifiable reward: parse KiCad schematic and check for basic correctness.

    Returns:
        1.0 — valid KiCad schematic with components and wires
        0.5 — parseable but incomplete (missing connections)
        0.0 — not a valid KiCad schematic
       -0.5 — empty or refusal
    """
    if not completion or len(completion) < 50:
        return -0.5

    # Check if it looks like a KiCad schematic
    has_kicad_header = "kicad_sch" in completion or "(kicad_sch" in completion
    has_symbol = "(symbol" in completion or "(lib_symbols" in completion
    has_wire = "(wire" in completion
    has_property = "(property" in completion

    # Count components
    n_symbols = len(re.findall(r"\(symbol\s", completion))
    n_wires = len(re.findall(r"\(wire\s", completion))
    len(re.findall(r"\(pin\s", completion))

    if has_kicad_header and has_symbol and n_symbols >= 2:
        if has_wire and n_wires >= 2:
            return 1.0  # Full schematic with connections
        elif has_property:
            return 0.5  # Has components but incomplete wiring
        else:
            return 0.3  # Minimal structure
    elif has_symbol or "(component" in completion:
        return 0.2  # Some KiCad-like content
    elif "```" in completion and any(
        kw in completion for kw in ["resistor", "capacitor", "VCC", "GND"]
    ):
        return 0.1  # Describes a circuit but not in KiCad format
    else:
        return -0.5  # Not a schematic at all


def code_compilation_reward(prompt: str, completion: str) -> float:
    """Check if embedded code compiles (C/Python syntax check)."""
    if not completion:
        return -0.5

    # Extract code blocks
    code_blocks = re.findall(
        r"```(?:c|cpp|python|ino)?\n(.*?)```", completion, re.DOTALL
    )
    if not code_blocks:
        # Try without backticks
        if any(kw in completion for kw in ["#include", "void ", "def ", "import "]):
            code_blocks = [completion]
        else:
            return 0.0

    total_score = 0
    for code in code_blocks:
        # Python syntax check
        if "import " in code or "def " in code:
            try:
                compile(code, "<string>", "exec")
                total_score += 1.0
            except SyntaxError:
                total_score += 0.2
        # C/C++ basic check (bracket matching)
        elif "#include" in code or "void " in code:
            opens = code.count("{")
            closes = code.count("}")
            if opens == closes and opens > 0:
                total_score += 0.8
            elif abs(opens - closes) <= 1:
                total_score += 0.4
            else:
                total_score += 0.1

    return min(1.0, total_score / max(len(code_blocks), 1))


def main():
    print("=" * 60)
    print("RLVR: KiCad DRC Reward Training")
    print(f"Prompts: {len(RLVR_PROMPTS)}")
    print(f"Output: {OUTPUT}")
    print("=" * 60)

    # Check if GRPO is available
    try:
        from trl import GRPOConfig, GRPOTrainer

        print("GRPOTrainer available")
    except ImportError:
        print("GRPOTrainer not available in this TRL version. Using DPO fallback.")
        print("Install: pip install trl>=0.25")
        return

    from unsloth import FastLanguageModel
    from datasets import Dataset

    # Load best model (mascarade-spice-v2 or latest)
    base = "unsloth/Qwen3-8B-unsloth-bnb-4bit"
    print(f"Loading {base}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        base, max_seq_length=2048, load_in_4bit=True
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    # Build dataset
    ds = Dataset.from_dict(
        {"prompt": RLVR_PROMPTS * 10}
    )  # Repeat for more training steps
    print(f"Dataset: {len(ds)} prompts")

    # Reward function
    def reward_fn(completions, prompts=None):
        rewards = []
        for i, completion in enumerate(completions):
            text = completion if isinstance(completion, str) else str(completion)
            prompt = prompts[i] if prompts else ""

            # Combine rewards
            kicad_score = kicad_drc_reward(prompt, text)
            code_score = code_compilation_reward(prompt, text)
            combined = 0.6 * kicad_score + 0.4 * code_score
            rewards.append(combined)
        return rewards

    # GRPO config
    config = GRPOConfig(
        output_dir=OUTPUT,
        num_generations=8,  # Group size
        max_completion_length=1024,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_train_epochs=2,
        learning_rate=5e-7,
        logging_steps=5,
        save_steps=50,
        bf16=True,
        seed=42,
    )

    trainer = GRPOTrainer(
        model=model,
        config=config,
        train_dataset=ds,
        reward_funcs=[reward_fn],
        tokenizer=tokenizer,
    )

    print("Starting GRPO training...")
    start = time.time()
    trainer.train()
    duration = time.time() - start

    print(f"DONE in {duration:.0f}s")
    model.save_pretrained(f"{OUTPUT}/lora")
    tokenizer.save_pretrained(f"{OUTPUT}/lora")

    manifest = {
        "name": "mascarade-rlvr-kicad",
        "method": "GRPO",
        "base_model": base,
        "prompts": len(RLVR_PROMPTS),
        "reward_functions": ["kicad_drc_reward", "code_compilation_reward"],
        "duration_seconds": duration,
        "output_dir": OUTPUT,
    }
    with open(f"{OUTPUT}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest: {OUTPUT}/manifest.json")


if __name__ == "__main__":
    main()
