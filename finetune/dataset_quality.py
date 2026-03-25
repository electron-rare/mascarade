#!/usr/bin/env python3
"""Dataset quality checks for ShareGPT-style fine-tuning corpora."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

try:
    from .sharegpt_utils import fingerprint_row, row_messages
except ImportError:  # pragma: no cover - script execution path
    from sharegpt_utils import fingerprint_row, row_messages

QUALITY_MODES = {"off", "warn", "fail"}


class DatasetQualityError(ValueError):
    """Raised when a dataset fails the configured quality gate."""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[index]


def resolve_quality_mode(mode: str | None = None) -> str:
    resolved = (
        (mode or os.environ.get("MASCARADE_DATASET_QUALITY_MODE", "fail"))
        .strip()
        .lower()
    )
    return resolved if resolved in QUALITY_MODES else "fail"


@dataclass
class DatasetQualityThresholds:
    min_rows_fail: int = 4
    recommended_rows_warn: int = 8
    min_unique_users_fail: int = 4
    max_duplicate_ratio_fail: float = 0.10
    max_repeated_pair_ratio_fail: float = 0.10
    max_assistant_p95_fail: int = 6000
    max_assistant_max_fail: int = 9000
    max_assistant_avg_warn: int = 3500
    short_assistant_threshold: int = 64
    max_short_assistant_ratio_warn: float = 0.25

    @classmethod
    def from_env(cls) -> "DatasetQualityThresholds":
        return cls(
            min_rows_fail=_env_int("MASCARADE_DATASET_QUALITY_MIN_ROWS", 4),
            recommended_rows_warn=_env_int(
                "MASCARADE_DATASET_QUALITY_RECOMMENDED_ROWS", 8
            ),
            min_unique_users_fail=_env_int(
                "MASCARADE_DATASET_QUALITY_MIN_UNIQUE_USERS", 4
            ),
            max_duplicate_ratio_fail=_env_float(
                "MASCARADE_DATASET_QUALITY_MAX_DUP_RATIO", 0.10
            ),
            max_repeated_pair_ratio_fail=_env_float(
                "MASCARADE_DATASET_QUALITY_MAX_REPEATED_PAIR_RATIO", 0.10
            ),
            max_assistant_p95_fail=_env_int(
                "MASCARADE_DATASET_QUALITY_MAX_ASSISTANT_P95", 6000
            ),
            max_assistant_max_fail=_env_int(
                "MASCARADE_DATASET_QUALITY_MAX_ASSISTANT_MAX", 9000
            ),
            max_assistant_avg_warn=_env_int(
                "MASCARADE_DATASET_QUALITY_MAX_ASSISTANT_AVG_WARN", 3500
            ),
            short_assistant_threshold=_env_int(
                "MASCARADE_DATASET_QUALITY_SHORT_ASSISTANT_THRESHOLD", 64
            ),
            max_short_assistant_ratio_warn=_env_float(
                "MASCARADE_DATASET_QUALITY_MAX_SHORT_ASSISTANT_RATIO", 0.25
            ),
        )


def analyze_dataset_quality(
    rows: list[dict],
    *,
    ids_fixed: int = 0,
    thresholds: DatasetQualityThresholds | None = None,
) -> dict:
    resolved_thresholds = thresholds or DatasetQualityThresholds.from_env()
    user_prompts: list[str] = []
    assistant_responses: list[str] = []
    system_prompts: list[str] = []
    assistant_lengths: list[int] = []
    duplicate_pairs: dict[tuple[str, str], int] = {}
    short_assistant_rows = 0
    fingerprints: list[str] = []

    for row in rows:
        messages = row_messages(row)
        system = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        ).strip()
        user = next((m["content"] for m in messages if m["role"] == "user"), "").strip()
        assistant = next(
            (m["content"] for m in reversed(messages) if m["role"] == "assistant"),
            "",
        ).strip()

        system_prompts.append(system)
        user_prompts.append(user)
        assistant_responses.append(assistant)
        assistant_lengths.append(len(assistant))
        if len(assistant) < resolved_thresholds.short_assistant_threshold:
            short_assistant_rows += 1
        duplicate_pairs[(user, assistant)] = (
            duplicate_pairs.get((user, assistant), 0) + 1
        )
        fingerprints.append(fingerprint_row(row))

    row_count = len(rows)
    duplicate_rows = len(fingerprints) - len(set(fingerprints))
    repeated_pairs = sum(1 for count in duplicate_pairs.values() if count > 1)

    return {
        "row_count": row_count,
        "ids_fixed": ids_fixed,
        "ids_fixed_ratio": (ids_fixed / row_count) if row_count else 0.0,
        "unique_system_prompts": len({item for item in system_prompts if item}),
        "unique_user_prompts": len({item for item in user_prompts if item}),
        "duplicate_rows": duplicate_rows,
        "duplicate_ratio": (duplicate_rows / row_count) if row_count else 0.0,
        "repeated_user_assistant_pairs": repeated_pairs,
        "repeated_pair_ratio": (repeated_pairs / row_count) if row_count else 0.0,
        "assistant_len_avg": (
            sum(assistant_lengths) / len(assistant_lengths)
            if assistant_lengths
            else 0.0
        ),
        "assistant_len_p95": _percentile(assistant_lengths, 0.95),
        "assistant_len_max": max(assistant_lengths) if assistant_lengths else 0,
        "short_assistant_rows": short_assistant_rows,
        "short_assistant_ratio": (
            short_assistant_rows / row_count if row_count else 0.0
        ),
    }


def evaluate_dataset_quality(
    rows: list[dict],
    *,
    label: str,
    ids_fixed: int = 0,
    mode: str | None = None,
    thresholds: DatasetQualityThresholds | None = None,
) -> dict:
    resolved_mode = resolve_quality_mode(mode)
    resolved_thresholds = thresholds or DatasetQualityThresholds.from_env()
    metrics = analyze_dataset_quality(
        rows,
        ids_fixed=ids_fixed,
        thresholds=resolved_thresholds,
    )
    errors: list[str] = []
    warnings: list[str] = []

    if metrics["row_count"] < resolved_thresholds.min_rows_fail:
        errors.append(
            f"dataset too small: {metrics['row_count']} rows < hard minimum "
            f"{resolved_thresholds.min_rows_fail}"
        )
    elif metrics["row_count"] < resolved_thresholds.recommended_rows_warn:
        warnings.append(
            f"dataset small for robust fine-tuning: {metrics['row_count']} rows < "
            f"recommended {resolved_thresholds.recommended_rows_warn}"
        )

    if metrics["unique_user_prompts"] < resolved_thresholds.min_unique_users_fail:
        errors.append(
            f"insufficient unique user prompts: {metrics['unique_user_prompts']} < "
            f"hard minimum {resolved_thresholds.min_unique_users_fail}"
        )

    if metrics["duplicate_ratio"] > resolved_thresholds.max_duplicate_ratio_fail:
        errors.append(
            f"too many duplicate rows: ratio={metrics['duplicate_ratio']:.2f} > "
            f"{resolved_thresholds.max_duplicate_ratio_fail:.2f}"
        )

    if (
        metrics["repeated_pair_ratio"]
        > resolved_thresholds.max_repeated_pair_ratio_fail
    ):
        errors.append(
            f"too many repeated prompt/answer pairs: ratio={metrics['repeated_pair_ratio']:.2f} > "
            f"{resolved_thresholds.max_repeated_pair_ratio_fail:.2f}"
        )

    if metrics["assistant_len_p95"] > resolved_thresholds.max_assistant_p95_fail:
        errors.append(
            f"assistant responses too verbose at p95: {metrics['assistant_len_p95']} > "
            f"{resolved_thresholds.max_assistant_p95_fail}"
        )

    if metrics["assistant_len_max"] > resolved_thresholds.max_assistant_max_fail:
        errors.append(
            f"assistant max length too high: {metrics['assistant_len_max']} > "
            f"{resolved_thresholds.max_assistant_max_fail}"
        )

    if metrics["assistant_len_avg"] > resolved_thresholds.max_assistant_avg_warn:
        warnings.append(
            f"assistant responses verbose on average: {metrics['assistant_len_avg']:.0f} > "
            f"{resolved_thresholds.max_assistant_avg_warn}"
        )

    if (
        metrics["short_assistant_ratio"]
        > resolved_thresholds.max_short_assistant_ratio_warn
    ):
        warnings.append(
            f"too many short assistant responses: ratio={metrics['short_assistant_ratio']:.2f} > "
            f"{resolved_thresholds.max_short_assistant_ratio_warn:.2f}"
        )

    if metrics["ids_fixed"] > 0:
        warnings.append(
            f"source ids are synthesized for {metrics['ids_fixed']}/{metrics['row_count']} rows; "
            "persist ids in source JSONL for traceability"
        )

    if (
        metrics["unique_system_prompts"] <= 1
        and metrics["row_count"] >= resolved_thresholds.min_rows_fail
    ):
        warnings.append(
            "single system prompt across the dataset; style diversity is low"
        )

    would_fail = bool(errors)
    if resolved_mode == "off":
        status = "disabled"
    elif would_fail and resolved_mode == "fail":
        status = "failed"
    elif errors or warnings:
        status = "warning"
    else:
        status = "passed"

    return {
        "label": label,
        "mode": resolved_mode,
        "status": status,
        "metrics": metrics,
        "thresholds": asdict(resolved_thresholds),
        "errors": errors,
        "warnings": warnings,
        "would_fail": would_fail,
    }


def summarize_quality_report(report: dict, *, limit: int = 4) -> str:
    messages = report.get("errors") or report.get("warnings") or []
    if not messages:
        return "dataset quality OK"
    return "; ".join(messages[:limit])


def enforce_dataset_quality(
    rows: list[dict],
    *,
    label: str,
    ids_fixed: int = 0,
    mode: str | None = None,
    thresholds: DatasetQualityThresholds | None = None,
) -> dict:
    report = evaluate_dataset_quality(
        rows,
        label=label,
        ids_fixed=ids_fixed,
        mode=mode,
        thresholds=thresholds,
    )
    if report["status"] == "failed":
        raise DatasetQualityError(f"{label}: {summarize_quality_report(report)}")
    return report
