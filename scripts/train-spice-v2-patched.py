"""mascarade-spice-v2 finetune with LoraConfig monkey-patch."""
import os
import json
import time
os.environ["WANDB_DISABLED"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Monkey-patch: Unsloth 2026.3.8 passes unknown kwargs to peft LoraConfig
import peft
import inspect
_orig = peft.LoraConfig.__init__
_valid_params = set(inspect.signature(_orig).parameters.keys())
def _patched(self, *a, **kw):
    filtered = {k: v for k, v in kw.items() if k in _valid_params}
    return _orig(self, *a, **filtered)
peft.LoraConfig.__init__ = _patched
print(f"[patch] LoraConfig patched (accepts {len(_valid_params)} params, strips unknown)")

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

RUN = "finetune/runs/mascarade-spice-v2-" + time.strftime("%Y%m%d-%H%M%S")
os.makedirs(RUN, exist_ok=True)

model, tokenizer = FastLanguageModel.from_pretrained(
    "unsloth/Qwen3-8B-unsloth-bnb-4bit", max_seq_length=2048, load_in_4bit=True
)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0, bias="none",
    use_gradient_checkpointing="unsloth", random_state=42,
)

ds = load_dataset("json", data_files="finetune/datasets/spice_chat.jsonl", split="train")
print(f"Dataset: {len(ds)}")

def fmt(ex):
    t = ""
    for c in ex.get("conversations", []):
        r, v = c.get("from", ""), c.get("value", "")
        if r in ("system", "human", "user"):
            t += f"<s>[INST] {v} [/INST]"
        elif r in ("assistant", "gpt"):
            t += f" {v}</s>"
    return {"text": t}

ds = ds.map(fmt).filter(lambda x: len(x["text"]) > 50)
print(f"Formatted: {len(ds)}")

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(
        output_dir=RUN, num_train_epochs=3,
        per_device_train_batch_size=1, gradient_accumulation_steps=16,
        learning_rate=2e-4, warmup_steps=50, logging_steps=25, save_steps=500,
        max_seq_length=2048, dataset_text_field="text", bf16=True, seed=42,
    ),
    train_dataset=ds, tokenizer=tokenizer,
)

start = time.time()
trainer.train()
dur = time.time() - start
print(f"DONE in {dur:.0f}s")

model.save_pretrained(f"{RUN}/lora")
tokenizer.save_pretrained(f"{RUN}/lora")
json.dump({"name": "mascarade-spice-v2", "examples": len(ds), "duration": dur, "output": RUN},
          open(f"{RUN}/manifest.json", "w"), indent=2)
print(f"Saved: {RUN}")
