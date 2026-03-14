#!/usr/bin/env python3
"""Simple task handler for P2P workers — responds to pings and echoes payloads."""
import asyncio
import json
import os
import sys
import signal

_core_dir = os.environ.get('PYTHONPATH', os.path.expanduser('~/mascarade/core'))
if _core_dir not in sys.path:
    sys.path.append(_core_dir)  # append, not insert, to let venv packages take priority

from mascarade.p2p.asyncio_node import MascaradeP2PNode

LISTEN_HOST = os.environ.get('P2P_LISTEN_HOST', '0.0.0.0')
LISTEN_PORT = int(os.environ.get('P2P_LISTEN_PORT', '4001'))
KEY_DIR = os.path.expanduser(os.environ.get('P2P_KEY_DIR', '~/.mascarade/p2p'))
BOOTSTRAP_ID = os.environ.get('P2P_BOOTSTRAP_ID', 'QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S')
BOOTSTRAP_HOST = os.environ.get('P2P_BOOTSTRAP_HOST', '192.168.0.119')
BOOTSTRAP_PORT = int(os.environ.get('P2P_BOOTSTRAP_PORT', '4002'))
CAPABILITIES = os.environ.get('P2P_CAPABILITIES', 'compute').split(',')
ROLE = os.environ.get('P2P_ROLE', 'worker')
LABEL = os.environ.get('P2P_LABEL', 'Worker')
USE_RELAY = os.environ.get('P2P_USE_RELAY', 'false').lower() == 'true'


async def _run_finetune(payload: dict) -> dict:
    """Run a fine-tuning job using Unsloth on this node."""
    import subprocess
    model = payload.get('model', 'Qwen/Qwen2.5-Coder-1.5B-Instruct')
    dataset = payload.get('dataset', 'ise-uiuc/Magicoder-OSS-Instruct-75K')
    max_examples = payload.get('max_examples', 5000)
    epochs = payload.get('epochs', 1)
    run_name = payload.get('run_name', 'p2p-finetune')
    output_dir = os.path.expanduser(f'~/.mascarade/finetune/runs/{run_name}')

    script = f'''
import os, json, time
os.makedirs("{output_dir}/adapter", exist_ok=True)
from unsloth import FastLanguageModel
from trl import SFTConfig, SFTTrainer
from datasets import load_dataset

t0 = time.time()
model, tokenizer = FastLanguageModel.from_pretrained("{model}", max_seq_length=2048, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=32,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth")

ds = load_dataset("{dataset}", split="train")
if len(ds) > {max_examples}: ds = ds.select(range({max_examples}))

def fmt(ex):
    parts = []
    if "problem" in ex: parts.append({{"role":"user","content":ex["problem"]}})
    elif "instruction" in ex: parts.append({{"role":"user","content":ex["instruction"]}})
    if "solution" in ex: parts.append({{"role":"assistant","content":ex["solution"]}})
    elif "output" in ex: parts.append({{"role":"assistant","content":ex["output"]}})
    return {{"text": tokenizer.apply_chat_template(parts, tokenize=False)}}

ds = ds.map(fmt)
config = SFTConfig(output_dir="{output_dir}/adapter", per_device_train_batch_size=4,
    gradient_accumulation_steps=4, num_train_epochs={epochs}, learning_rate=2e-4,
    warmup_ratio=0.03, optim="adamw_8bit", bf16=True, max_seq_length=2048, logging_steps=10,
    save_strategy="no", dataset_text_field="text")
trainer = SFTTrainer(model=model, train_dataset=ds, processing_class=tokenizer, args=config)
result = trainer.train()
model.save_pretrained("{output_dir}/adapter")
tokenizer.save_pretrained("{output_dir}/adapter")
elapsed = time.time() - t0
loss = result.training_loss
info = {{"loss": loss, "elapsed_s": round(elapsed), "model": "{model}", "dataset": "{dataset}",
    "examples": len(ds), "epochs": {epochs}, "adapter": "{output_dir}/adapter"}}
with open("{output_dir}/result.json", "w") as f: json.dump(info, f)
print(json.dumps(info))
'''
    # Write and run the script
    script_path = f'/tmp/p2p_finetune_{run_name}.py'
    with open(script_path, 'w') as f:
        f.write(script)

    venv_python = os.path.expanduser('~/mascarade/core/.venv/bin/python')
    if not os.path.isfile(venv_python):
        venv_python = 'python3'

    proc = await asyncio.create_subprocess_exec(
        venv_python, script_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {'status': 'error', 'from': LABEL, 'error': stderr.decode()[-500:]}

    # Parse the last JSON line from stdout
    result = None
    for line in reversed(stdout.decode().strip().split('\n')):
        try:
            result = {'status': 'completed', 'from': LABEL, **json.loads(line)}
            break
        except json.JSONDecodeError:
            continue
    if result is None:
        result = {'status': 'completed', 'from': LABEL, 'output': stdout.decode()[-500:]}

    # Auto-register into Ollama if a GGUF file is available
    adapter_dir = result.get('adapter', '')
    if adapter_dir and result.get('status') == 'completed':
        await _try_register_ollama(adapter_dir, payload.get('run_name', 'p2p-finetune'))

    return result


async def _try_register_ollama(adapter_dir: str, run_name: str) -> None:
    """Best-effort auto-registration of a GGUF into Ollama after fine-tune."""
    import glob as _glob
    # Look for GGUF files in the adapter dir and parent
    search_dirs = [adapter_dir, os.path.dirname(adapter_dir)]
    gguf_path = None
    for d in search_dirs:
        matches = _glob.glob(os.path.join(d, '*.gguf'))
        if matches:
            gguf_path = matches[0]
            break
    if not gguf_path:
        print(f'[publish] No GGUF found near {adapter_dir}, skipping Ollama registration', flush=True)
        return
    try:
        from mascarade.finetune.publish import register_ollama_model
        model_name = f'mascarade-{run_name}'
        result = await register_ollama_model(gguf_path, model_name)
        print(f'[publish] Ollama registration: {result}', flush=True)
    except Exception as exc:
        print(f'[publish] Ollama registration failed (best-effort): {exc}', flush=True)


async def handle_task(payload: dict, capability: str) -> dict:
    """Task handler — supports ping, echo, finetune, and generic actions."""
    action = payload.get('action', 'unknown')
    if action == 'ping':
        return {'status': 'pong', 'from': LABEL, 'capability': capability}
    elif action == 'echo':
        return {'status': 'echoed', 'from': LABEL, 'message': payload.get('message', '')}
    elif action == 'finetune':
        return await _run_finetune(payload)
    elif capability.startswith('ft-'):
        from mascarade.finetune.p2p.task_handlers import handle_ft_task

        result = await handle_ft_task(payload, capability)
        if isinstance(result, dict) and 'from' not in result:
            result = {'from': LABEL, **result}
        return result
    else:
        return {'status': 'handled', 'from': LABEL, 'action': action, 'capability': capability}


async def main():
    os.makedirs(KEY_DIR, exist_ok=True)
    node = MascaradeP2PNode(
        listen_host=LISTEN_HOST, listen_port=LISTEN_PORT, key_dir=KEY_DIR,
        bootstrap_peers=[(BOOTSTRAP_ID, BOOTSTRAP_HOST, BOOTSTRAP_PORT)],
    )
    await node.start()
    print(json.dumps({'peer_id': node.peer_id}), flush=True)

    if USE_RELAY:
        from mascarade.p2p.relay import RelayClient
        rc = RelayClient(local_peer_id=node.peer_id, transport=node.transport, dht=node.dht)
        rc.add_known_relay(BOOTSTRAP_ID)
        node.transport.set_relay_client(rc)

    node.set_task_handler(handle_task)

    await asyncio.sleep(1)
    await node.advertise_capabilities(
        capabilities=CAPABILITIES, role=ROLE, label=LABEL, http_base_url='',
    )
    print(f'READY (task handler active, caps={CAPABILITIES})', flush=True)

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    await stop.wait()
    await node.stop()

asyncio.run(main())
