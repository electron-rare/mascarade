"""Auto-registration of fine-tuned GGUF models into Ollama."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.publish")

DEFAULT_TEMPLATE = """\
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ end }}{{- if eq .Role "assistant" }}<|im_start|>assistant
{{ .Content }}<|im_end|>
{{ end }}{{- end }}<|im_start|>assistant
"""

DEFAULT_PARAMETERS = """\
PARAMETER stop <|im_end|>
PARAMETER stop <|im_start|>
PARAMETER temperature 0.7
PARAMETER top_p 0.9
"""


def build_modelfile(
    gguf_path: str,
    *,
    template: str | None = None,
    system: str | None = None,
    parameters: str | None = None,
) -> str:
    """Build an Ollama Modelfile for a GGUF model."""
    lines = [f'FROM "{gguf_path}"']
    lines.append(f'TEMPLATE """{template or DEFAULT_TEMPLATE}"""')
    if system:
        lines.append(f'SYSTEM """{system}"""')
    lines.append(parameters or DEFAULT_PARAMETERS)
    return "\n".join(lines)


async def register_ollama_model(
    gguf_path: str,
    model_name: str,
    *,
    ollama_binary: str = "ollama",
    template: str | None = None,
    system: str | None = None,
) -> dict:
    """Create an Ollama model from a GGUF file.

    Returns dict with status, model_name, and any error info.
    """
    gguf = Path(gguf_path)
    if not gguf.exists():
        return {"status": "error", "error": f"GGUF not found: {gguf_path}"}

    modelfile_content = build_modelfile(
        gguf_path,
        template=template,
        system=system,
    )

    # Write Modelfile to temp location
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".Modelfile",
        delete=False,
    ) as f:
        f.write(modelfile_content)
        modelfile_path = f.name

    try:
        # Check ollama is available
        if not shutil.which(ollama_binary):
            return {"status": "error", "error": f"'{ollama_binary}' not found in PATH"}

        proc = await asyncio.create_subprocess_exec(
            ollama_binary,
            "create",
            model_name,
            "-f",
            modelfile_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode().strip()[-500:]
            logger.error(
                "ollama create %s failed (rc=%d): %s",
                model_name,
                proc.returncode,
                err,
            )
            return {"status": "error", "error": err, "model_name": model_name}

        logger.info("Model %s registered in Ollama from %s", model_name, gguf_path)
        return {
            "status": "registered",
            "model_name": model_name,
            "gguf_path": gguf_path,
            "output": stdout.decode().strip()[-500:],
        }
    finally:
        Path(modelfile_path).unlink(missing_ok=True)
