"""Main Gradio application for fine-tuning workflows."""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

from mascarade.gradio_ui.components import (
    create_dataset_upload_form,
    create_hyperparameter_form,
    create_job_list_display,
    create_training_status_display,
    format_job_for_display,
)

logger = logging.getLogger("mascarade.gradio_ui.app")

# API base URL (assumes Gradio is mounted on same FastAPI server)
API_BASE = os.getenv("GRADIO_API_BASE", "http://localhost:8100/api")
DATASETS_DIR = Path.home() / ".mascarade" / "finetune" / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


async def upload_dataset_handler(
    file_path: str | None,
    dataset_id: str,
    domain: str,
    format: str,
) -> tuple[str, str]:
    """
    Handle dataset upload.

    Args:
        file_path: Path to uploaded file
        dataset_id: Dataset identifier
        domain: Training domain
        format: Dataset format (jsonl, parquet, csv)

    Returns:
        Tuple of (success/error message, dataset path)
    """
    if not file_path:
        return "❌ No file uploaded", ""

    if not dataset_id:
        return "❌ Dataset ID is required", ""

    try:
        # Copy file to datasets directory
        dest_path = DATASETS_DIR / f"{dataset_id}.{format}"
        shutil.copy(file_path, dest_path)

        logger.info("Dataset uploaded: %s -> %s", file_path, dest_path)
        return f"✅ Dataset uploaded successfully: {dest_path}", str(dest_path)

    except Exception as e:
        logger.exception("Failed to upload dataset")
        return f"❌ Upload failed: {e}", ""


async def submit_training_handler(
    dataset_path: str,
    base_model: str,
    method: str,
    learning_rate: float,
    batch_size: int,
    epochs: int,
    lora_r: int,
    lora_alpha: int,
) -> tuple[str, str, str, dict]:
    """
    Submit a fine-tuning job.

    Args:
        dataset_path: Path to training dataset
        base_model: Base model ID
        method: Training method (lora, qlora, full, dpo)
        learning_rate: Learning rate
        batch_size: Batch size
        epochs: Number of epochs
        lora_r: LoRA rank
        lora_alpha: LoRA alpha

    Returns:
        Tuple of (job_id, status message, status, metrics)
    """
    if not dataset_path:
        return "", "❌ Please upload a dataset first", "error", {}

    if not base_model:
        return "", "❌ Base model is required", "error", {}

    try:
        async with httpx.AsyncClient() as client:
            # Submit job to API
            response = await client.post(
                f"{API_BASE}/finetune/jobs",
                json={
                    "dataset": dataset_path,
                    "model": base_model,
                    "method": method,
                    "node": None,  # Auto-select
                },
                timeout=30.0,
            )
            response.raise_for_status()
            job_data = response.json()

            job_id = job_data.get("job_id", "")
            status = job_data.get("status", "pending")

            # Store hyperparameters in metrics for reference
            metrics = {
                "hyperparameters": {
                    "learning_rate": learning_rate,
                    "batch_size": batch_size,
                    "epochs": epochs,
                    "lora_r": lora_r,
                    "lora_alpha": lora_alpha,
                }
            }

            logger.info("Job submitted: %s (status: %s)", job_id, status)
            return (
                job_id,
                f"✅ Job submitted successfully: {job_id}",
                status,
                metrics,
            )

    except httpx.HTTPStatusError as e:
        logger.exception("Failed to submit job")
        return "", f"❌ API error: {e.response.status_code} - {e.response.text}", "error", {}
    except Exception as e:
        logger.exception("Failed to submit job")
        return "", f"❌ Submission failed: {e}", "error", {}


async def refresh_status_handler(job_id: str) -> tuple[str, dict]:
    """
    Refresh job status.

    Args:
        job_id: Job ID to query

    Returns:
        Tuple of (status, metrics)
    """
    if not job_id:
        return "No job running", {}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/finetune/jobs/{job_id}",
                timeout=10.0,
            )
            response.raise_for_status()
            job_data = response.json()

            status = job_data.get("status", "unknown")
            metrics = job_data.get("metrics", {})

            logger.debug("Job status refreshed: %s (status: %s)", job_id, status)
            return status, metrics

    except httpx.HTTPStatusError as e:
        logger.exception("Failed to refresh status")
        return f"error: {e.response.status_code}", {}
    except Exception as e:
        logger.exception("Failed to refresh status")
        return f"error: {e}", {}


async def refresh_jobs_handler() -> list[list[Any]]:
    """
    Refresh the list of all jobs.

    Returns:
        List of job rows for dataframe display
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/finetune/jobs",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            jobs = data.get("jobs", [])
            rows = [format_job_for_display(job) for job in jobs]

            logger.debug("Jobs list refreshed: %d jobs", len(rows))
            return rows

    except Exception as e:
        logger.exception("Failed to refresh jobs")
        return []


def create_gradio_app() -> gr.Blocks:
    """
    Create the main Gradio application for fine-tuning.

    Returns:
        Gradio Blocks application
    """
    with gr.Blocks(
        title="Mascarade Fine-Tuning",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown(
            """
            # 🎭 Mascarade Fine-Tuning WebUI

            Upload datasets, configure hyperparameters, and launch fine-tuning jobs
            using Unsloth-accelerated training on GPU.
            """
        )

        # State to hold current job ID
        current_job_id = gr.State("")
        current_dataset_path = gr.State("")

        with gr.Tabs():
            # Tab 1: Dataset Upload
            with gr.Tab("📁 Dataset Upload"):
                (
                    file_upload,
                    dataset_id,
                    dataset_domain,
                    dataset_format,
                    upload_button,
                ) = create_dataset_upload_form()

                upload_status = gr.Textbox(
                    label="Upload Status",
                    interactive=False,
                    placeholder="No upload yet",
                )

            # Tab 2: Training Configuration
            with gr.Tab("⚙️ Training Configuration"):
                (
                    base_model,
                    method,
                    learning_rate,
                    batch_size,
                    epochs,
                    lora_r,
                    lora_alpha,
                ) = create_hyperparameter_form()

                submit_button = gr.Button("🚀 Launch Training", variant="primary", size="lg")
                submit_status = gr.Textbox(
                    label="Submission Status",
                    interactive=False,
                    placeholder="Configure and submit",
                )

            # Tab 3: Job Status
            with gr.Tab("📊 Job Status"):
                (
                    job_id_display,
                    status_display,
                    metrics_display,
                    refresh_button,
                ) = create_training_status_display()

            # Tab 4: All Jobs
            with gr.Tab("📋 All Jobs"):
                (
                    jobs_dataframe,
                    refresh_jobs_button,
                    cancel_button,
                ) = create_job_list_display()

        # Event handlers
        upload_button.click(
            fn=upload_dataset_handler,
            inputs=[file_upload, dataset_id, dataset_domain, dataset_format],
            outputs=[upload_status, current_dataset_path],
        )

        submit_button.click(
            fn=submit_training_handler,
            inputs=[
                current_dataset_path,
                base_model,
                method,
                learning_rate,
                batch_size,
                epochs,
                lora_r,
                lora_alpha,
            ],
            outputs=[current_job_id, submit_status, status_display, metrics_display],
        ).then(
            # After submission, update job ID display
            fn=lambda jid: jid,
            inputs=[current_job_id],
            outputs=[job_id_display],
        )

        refresh_button.click(
            fn=refresh_status_handler,
            inputs=[current_job_id],
            outputs=[status_display, metrics_display],
        )

        refresh_jobs_button.click(
            fn=refresh_jobs_handler,
            inputs=[],
            outputs=[jobs_dataframe],
        )

        # Auto-refresh jobs list on tab open
        app.load(
            fn=refresh_jobs_handler,
            inputs=[],
            outputs=[jobs_dataframe],
        )

    return app
