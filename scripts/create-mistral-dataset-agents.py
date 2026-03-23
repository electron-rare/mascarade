"""Create specialized Mistral agents for dataset generation, then use them."""

import json
import time
import os
import httpx
import random

MISTRAL_URL = "https://api.mistral.ai/v1"
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")

AGENTS_TO_CREATE = [
    {
        "name": "mascarade-kicad-teacher",
        "model": "mistral-medium-latest",
        "description": "Expert KiCad PCB designer for generating training data grounded in real schematics",
        "instructions": """You are an expert KiCad PCB designer with 20 years of experience.

RULES:
- Base ALL answers on the schematic data provided (components, description, project name)
- NEVER invent component values — say "check the datasheet for [component]" if unsure
- Include specific KiCad menu paths only if you are 100% certain they exist
- For DRC rules, reference IPC standards by number (IPC-2221, IPC-7351, etc.)
- For JLCPCB, only state capabilities you are certain about
- Write practical, actionable advice a real engineer would use
- Include calculations with formulas when relevant
- Recommend specific, real component part numbers when you know them""",
        "tools": [{"type": "web_search"}],
        "completion_args": {"temperature": 0.3},
    },
    {
        "name": "mascarade-embedded-teacher",
        "model": "mistral-medium-latest",
        "description": "Expert embedded systems engineer for generating firmware training data",
        "instructions": """You are an expert embedded systems engineer specializing in STM32, ESP32, nRF52, RP2040, and PlatformIO.

RULES:
- Write COMPILABLE code — every code snippet must be syntactically correct
- Include proper #include headers and function signatures
- Use real register names and peripheral addresses from datasheets
- For STM32 HAL: use actual HAL function names (HAL_GPIO_Init, HAL_SPI_Transmit, etc.)
- For ESP-IDF: use real API functions (esp_wifi_init, gpio_set_direction, etc.)
- For Arduino: use real library APIs
- Specify exact board/MCU when giving register-level code
- Include error handling in all code examples
- Reference real datasheets and application notes""",
        "tools": [{"type": "web_search"}],
        "completion_args": {"temperature": 0.2},
    },
    {
        "name": "mascarade-analog-teacher",
        "model": "mistral-medium-latest",
        "description": "Expert analog/audio electronics engineer for training data",
        "instructions": """You are an expert analog electronics and audio engineer.

RULES:
- Include SPICE netlists that actually simulate (correct syntax for ngspice/LTspice)
- Show calculations with real formulas (not approximations unless stated)
- Use real op-amp part numbers (TL072, NE5532, OPA2134, AD8620, etc.)
- For filters: show transfer function, component values, and Bode plot description
- For power supplies: include efficiency calculations and thermal analysis
- For audio: specify THD+N, SNR, frequency response when relevant
- Reference real datasheets for component specifications
- Say "consult the datasheet" rather than guessing a spec""",
        "tools": [{"type": "web_search"}],
        "completion_args": {"temperature": 0.3},
    },
    {
        "name": "mascarade-verilog-teacher",
        "model": "codestral-latest",
        "description": "Expert Verilog/SystemVerilog RTL designer for training data",
        "instructions": """You are an expert RTL designer specializing in Verilog and SystemVerilog.

RULES:
- Write synthesizable Verilog (no #delay in synthesizable code)
- Include testbenches with proper clock generation and reset
- Use proper coding style: always blocks, case statements, generate
- Specify timing constraints when relevant
- Include assertions (SVA) for verification
- Write both behavioral and structural descriptions
- Include proper module port declarations with correct widths
- Handle clock domain crossings correctly
- Include comments explaining the design intent""",
        "completion_args": {"temperature": 0.2},
    },
]


def create_agent(agent_def):
    """Create a Mistral agent via API."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{MISTRAL_URL}/agents", headers={
            "Authorization": f"Bearer {MISTRAL_KEY}",
            "Content-Type": "application/json",
        }, json={
            "model": agent_def["model"],
            "name": agent_def["name"],
            "description": agent_def["description"],
            "instructions": agent_def["instructions"],
            "tools": agent_def.get("tools", []),
            "completion_args": agent_def.get("completion_args", {}),
        })
        resp.raise_for_status()
        data = resp.json()
        return data["id"]


def run_agent(agent_id, prompt, max_retries=2):
    """Run a Mistral agent and return the response."""
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(f"{MISTRAL_URL}/agents/completions", headers={
                    "Authorization": f"Bearer {MISTRAL_KEY}",
                    "Content-Type": "application/json",
                }, json={
                    "agent_id": agent_id,
                    "messages": [{"role": "user", "content": prompt}],
                })
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    return None


def main():
    print("=== Create Mistral Dataset Agents ===\n")

    if not MISTRAL_KEY:
        print("ERROR: MISTRAL_API_KEY not set")
        return

    # Create agents
    agent_ids = {}
    for agent_def in AGENTS_TO_CREATE:
        print(f"Creating {agent_def['name']}...")
        try:
            aid = create_agent(agent_def)
            agent_ids[agent_def["name"]] = aid
            print(f"  Created: {aid}")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Save agent IDs
    ids_file = "finetune/datasets/mistral_agent_ids.json"
    os.makedirs(os.path.dirname(ids_file), exist_ok=True)
    with open(ids_file, "w") as f:
        json.dump(agent_ids, f, indent=2)
    print(f"\nAgent IDs saved: {ids_file}")

    # Test each agent
    print("\n=== Testing Agents ===")
    for name, aid in agent_ids.items():
        print(f"\n{name} ({aid}):")
        result = run_agent(aid, "Say OK if you are ready to generate training data.")
        print(f"  Response: {(result or 'FAILED')[:100]}")

    print(f"\n=== {len(agent_ids)} agents created and tested ===")
    print("Use these agents with: python3 scripts/generate-with-agents.py")


if __name__ == "__main__":
    main()
