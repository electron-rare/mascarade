"""Reusable Gradio UI components for fine-tuning workflows."""

from __future__ import annotations

import logging
from typing import Any

import gradio as gr

logger = logging.getLogger("mascarade.gradio_ui.components")


def create_dataset_upload_form() -> tuple[gr.components.Component, ...]:
    """
    Create dataset upload form components.

    Returns:
        Tuple of Gradio components for dataset upload:
        (file_upload, dataset_id, dataset_domain, dataset_format, upload_button)
    """
    with gr.Group():
        gr.Markdown("### Dataset Upload")
        gr.Markdown("Upload your training dataset in JSONL, Parquet, or CSV format.")

        file_upload = gr.File(
            label="Training Dataset",
            file_types=[".jsonl", ".parquet", ".csv", ".json"],
            type="filepath",
        )
        dataset_id = gr.Textbox(
            label="Dataset ID",
            placeholder="e.g., my-custom-dataset-v1",
            info="Unique identifier for this dataset",
        )
        dataset_domain = gr.Textbox(
            label="Domain",
            placeholder="e.g., code, chat, summarization",
            info="Training domain or task type",
        )
        dataset_format = gr.Dropdown(
            label="Format",
            choices=["jsonl", "parquet", "csv"],
            value="jsonl",
            info="Dataset file format",
        )
        upload_button = gr.Button("Upload Dataset", variant="primary")

    return file_upload, dataset_id, dataset_domain, dataset_format, upload_button


def create_hyperparameter_form() -> tuple[gr.components.Component, ...]:
    """
    Create hyperparameter configuration form.

    Returns:
        Tuple of Gradio components for hyperparameters:
        (base_model, method, learning_rate, batch_size, epochs, lora_r, lora_alpha)
    """
    with gr.Group():
        gr.Markdown("### Training Configuration")
        gr.Markdown("Configure hyperparameters for your fine-tuning job.")

        base_model = gr.Textbox(
            label="Base Model",
            placeholder="e.g., unsloth/llama-3-8b, meta-llama/Llama-2-7b-hf",
            value="unsloth/llama-3-8b",
            info="HuggingFace model ID to fine-tune",
        )
        method = gr.Dropdown(
            label="Training Method",
            choices=["lora", "qlora", "full", "dpo"],
            value="lora",
            info="Fine-tuning method (LoRA recommended for efficiency)",
        )
        learning_rate = gr.Slider(
            label="Learning Rate",
            minimum=1e-6,
            maximum=1e-3,
            value=2e-5,
            step=1e-6,
            info="Learning rate for optimizer",
        )
        batch_size = gr.Slider(
            label="Batch Size",
            minimum=1,
            maximum=32,
            value=2,
            step=1,
            info="Training batch size (lower for GPU memory constraints)",
        )
        epochs = gr.Slider(
            label="Epochs",
            minimum=1,
            maximum=10,
            value=3,
            step=1,
            info="Number of training epochs",
        )

        # LoRA-specific parameters
        with gr.Accordion("LoRA Parameters (optional)", open=False):
            lora_r = gr.Slider(
                label="LoRA Rank (r)",
                minimum=4,
                maximum=128,
                value=16,
                step=4,
                info="LoRA rank (higher = more parameters, better quality, slower)",
            )
            lora_alpha = gr.Slider(
                label="LoRA Alpha",
                minimum=4,
                maximum=128,
                value=16,
                step=4,
                info="LoRA scaling parameter (typically same as rank)",
            )

    return base_model, method, learning_rate, batch_size, epochs, lora_r, lora_alpha


def create_training_status_display() -> tuple[gr.components.Component, ...]:
    """
    Create training status display components.

    Returns:
        Tuple of Gradio components for status display:
        (job_id_display, status_display, metrics_display, refresh_button)
    """
    with gr.Group():
        gr.Markdown("### Training Status")

        job_id_display = gr.Textbox(
            label="Job ID",
            interactive=False,
            placeholder="No job running",
        )
        status_display = gr.Textbox(
            label="Status",
            interactive=False,
            placeholder="Idle",
        )
        metrics_display = gr.JSON(
            label="Training Metrics",
            value=None,
        )
        refresh_button = gr.Button("Refresh Status", size="sm")

    return job_id_display, status_display, metrics_display, refresh_button


def create_job_list_display() -> tuple[gr.components.Component, ...]:
    """
    Create job list display components.

    Returns:
        Tuple of Gradio components for job list:
        (jobs_dataframe, refresh_jobs_button, cancel_button)
    """
    with gr.Group():
        gr.Markdown("### Training Jobs")
        gr.Markdown("View and manage all fine-tuning jobs.")

        jobs_dataframe = gr.Dataframe(
            headers=["Job ID", "Base Model", "Dataset", "Method", "Status", "Started At"],
            datatype=["str", "str", "str", "str", "str", "str"],
            interactive=False,
            wrap=True,
        )
        with gr.Row():
            refresh_jobs_button = gr.Button("Refresh Jobs", size="sm")
            cancel_button = gr.Button("Cancel Selected", size="sm", variant="stop")

    return jobs_dataframe, refresh_jobs_button, cancel_button


def format_job_for_display(job: dict[str, Any]) -> list[Any]:
    """
    Format a job entry for display in the jobs dataframe.

    Args:
        job: Job dictionary from API

    Returns:
        List of values for dataframe row
    """
    import datetime

    started_at = job.get("started_at", 0)
    started_str = (
        datetime.datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M:%S")
        if started_at
        else "N/A"
    )

    return [
        job.get("job_id", ""),
        job.get("base_model", ""),
        job.get("dataset", ""),
        job.get("method", ""),
        job.get("status", ""),
        started_str,
    ]
