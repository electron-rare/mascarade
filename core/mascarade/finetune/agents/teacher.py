"""Teacher (Doctor) agent — generates high-quality training data via LLM."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.teacher")


@dataclass
class TeacherConfig:
    task_description: str
    output_format: str = "chatml"  # "chatml", "alpaca", "sharegpt"
    temperature: float = 0.7
    samples_per_input: int = 1
    max_tokens: int = 2048


class TeacherAgent:
    """Generates teacher data using Claude/GPT via the mascarade Router.

    Uses strategy=BEST to get highest quality responses.
    Outputs JSONL compatible with trl/axolotl.

    P2P capability: ft-teacher
    """

    def __init__(self, *, router=None):
        self.router = router

    async def generate_from_prompts(
        self,
        prompts: list[str],
        config: TeacherConfig,
        output_path: Path | str,
    ) -> dict:
        """Generate instruction/response pairs from a list of prompts."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.router is None:
            raise RuntimeError("TeacherAgent requires a mascarade Router instance")

        results = []
        errors = 0
        with open(output_path, "w") as f:
            for i, prompt in enumerate(prompts):
                try:
                    messages = [{"role": "user", "content": prompt}]
                    system = (
                        f"You are a teacher generating high-quality training data. "
                        f"Task: {config.task_description}. "
                        f"Respond clearly and accurately."
                    )
                    response = await self.router.send(
                        messages=messages,
                        system=system,
                        strategy="best",
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                    )
                    entry = self._format_entry(prompt, response.content, config.output_format)
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    results.append(entry)
                except Exception as e:
                    logger.warning("Failed to generate for prompt %d: %s", i, e)
                    errors += 1

        logger.info("Generated %d samples (%d errors) → %s", len(results), errors, output_path)
        return {
            "output_path": str(output_path),
            "total": len(results),
            "errors": errors,
            "format": config.output_format,
        }

    async def generate_corrections(
        self,
        errors: list[dict],
        config: TeacherConfig,
        output_path: Path | str,
    ) -> dict:
        """Generate corrected responses for detected errors (for DPO chosen data)."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.router is None:
            raise RuntimeError("TeacherAgent requires a mascarade Router instance")

        corrections = []
        with open(output_path, "w") as f:
            for err in errors:
                try:
                    original_prompt = err.get("prompt", "")
                    bad_response = err.get("bad_response", "")
                    error_desc = err.get("error_description", "incorrect")
                    if not original_prompt:
                        logger.warning("Skipping error with missing prompt field")
                        continue
                    prompt = (
                        f"The following response to the prompt was incorrect:\n\n"
                        f"Prompt: {original_prompt}\n"
                        f"Bad response: {bad_response}\n"
                        f"Error: {error_desc}\n\n"
                        f"Please provide the correct response."
                    )
                    response = await self.router.send(
                        messages=[{"role": "user", "content": prompt}],
                        strategy="best",
                        temperature=0.3,
                        max_tokens=config.max_tokens,
                    )
                    entry = {
                        "prompt": original_prompt,
                        "chosen": response.content,
                        "rejected": bad_response,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    corrections.append(entry)
                except Exception as e:
                    logger.warning("Failed correction: %s", e)

        return {"output_path": str(output_path), "total": len(corrections)}

    @staticmethod
    def _format_entry(prompt: str, response: str, fmt: str) -> dict:
        if fmt == "chatml":
            return {
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response},
                ]
            }
        elif fmt == "alpaca":
            return {
                "instruction": prompt,
                "input": "",
                "output": response,
            }
        elif fmt == "sharegpt":
            return {
                "conversations": [
                    {"from": "human", "value": prompt},
                    {"from": "gpt", "value": response},
                ]
            }
        return {"prompt": prompt, "response": response}
