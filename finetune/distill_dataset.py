#!/usr/bin/env python3
"""Generate distilled ShareGPT samples with a teacher model via Mascarade."""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import random
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from sharegpt_utils import (
    dedupe_rows,
    ensure_row_ids,
    load_jsonl,
    make_row,
    validate_rows,
    write_jsonl,
)
from tqdm.auto import tqdm

DEFAULT_API_URLS = ["http://127.0.0.1:3100", "http://127.0.0.1:8100"]
DEFAULT_DOMAINS = [
    "stm32",
    "spice",
    "iot",
    "power",
    "dsp",
    "emc",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
]
DEFAULT_TEACHER_SYSTEM = """You create supervised fine-tuning data for a smaller local model.
Return only valid JSON. Do not wrap the JSON in markdown fences.
Prioritize technical correctness, realistic code/configuration, and domain precision.
When the source is in French, keep the generated samples in French. Otherwise keep the source language."""

DOMAIN_BRIEFS = {
    "stm32": "Embedded firmware, STM32 HAL/LL, CMSIS, FreeRTOS, ARM Cortex-M, registers, DMA, UART, SPI, I2C.",
    "spice": "SPICE simulation, LTspice/ngspice, analog circuits, netlists, stability, convergence, op-amps, filters.",
    "iot": "ESP-IDF, MQTT, Wi-Fi, BLE, embedded networking, low power, telemetry, home automation.",
    "power": "Power electronics, converters, gate driving, thermal constraints, current sense, motor control.",
    "dsp": "DSP, filters, FFT, fixed-point, C implementations, signal conditioning, sampling constraints.",
    "emc": "EMC/EMI, ESD, grounding, shielding, return paths, layout, compliance troubleshooting.",
    "kicad": "KiCad, PCB stackups, routing, DRC, impedance control, footprints, BOM, Gerbers, manufacturing.",
    "embedded": "Bare-metal and RTOS embedded systems, debugging, interrupts, memory maps, toolchains, drivers.",
    "platformio": "PlatformIO, pio.ini, ESP32/ESP-IDF, Arduino, board definitions, build flags, libraries, flashing, debugging.",
    "freecad": "FreeCAD, parametric CAD, Python macros, workbenches, sketches, constraints, TechDraw, STEP export.",
}


@dataclass
class EndpointConfig:
    base_url: str
    providers_url: str
    send_url: str
    providers: list[str]


def shorten(text: str, limit: int = 800) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def clip_text(text: str, limit: int) -> str:
    value = text.strip()
    if len(value) <= limit:
        return value
    clipped = value[:limit].rstrip()
    return clipped + "\n...[truncated]"


def stringify_sample_field(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback.strip()
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2).strip()
    return str(value).strip()


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail = shorten(raw) if raw else str(exc)
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error while calling {url}: {exc.reason}") from exc


def candidate_endpoints(base_url: str) -> list[tuple[str, str]]:
    base = base_url.rstrip("/")
    if base.endswith("/api/agents"):
        return [(f"{base}/providers", f"{base}/send")]
    if base.endswith("/api"):
        return [(f"{base}/agents/providers", f"{base}/agents/send")]
    if ":3100" in base:
        return [
            (f"{base}/api/agents/providers", f"{base}/api/agents/send"),
            (f"{base}/providers", f"{base}/send"),
        ]
    return [
        (f"{base}/providers", f"{base}/send"),
        (f"{base}/api/agents/providers", f"{base}/api/agents/send"),
    ]


def resolve_endpoint(
    api_urls: list[str], headers: dict[str, str], timeout: int
) -> EndpointConfig:
    last_error: str | None = None
    for base_url in api_urls:
        for providers_url, send_url in candidate_endpoints(base_url):
            try:
                payload = request_json(
                    providers_url,
                    method="GET",
                    headers=headers,
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{providers_url}: {exc}"
                continue
            providers = payload.get("providers", [])
            if not isinstance(providers, list):
                providers = []
            return EndpointConfig(
                base_url=base_url.rstrip("/"),
                providers_url=providers_url,
                send_url=send_url,
                providers=[str(provider) for provider in providers],
            )
    raise RuntimeError(
        f"Unable to reach Mascarade API/providers endpoint ({last_error})"
    )


def extract_messages(row: dict) -> tuple[str, str, str]:
    system = ""
    user = ""
    assistant = ""
    for message in row.get("conversations", []):
        role = message.get("from")
        value = str(message.get("value", "")).strip()
        if role == "system" and not system:
            system = value
        elif role == "human" and not user:
            user = value
        elif role == "gpt":
            assistant = value
    return system, user, assistant


def build_teacher_prompt(row: dict, domain: str, samples_per_source: int) -> str:
    domain_brief = DOMAIN_BRIEFS.get(domain, "")
    source_system, source_user, source_assistant = extract_messages(row)
    source_system = clip_text(source_system or "(none)", 1200)
    source_user = clip_text(source_user, 4000)
    source_assistant = clip_text(source_assistant or "(none)", 2400)
    return f"""Create exactly {samples_per_source} distilled supervised training samples for the domain "{domain}".

Domain brief:
{domain_brief}

Rules:
- Return only valid JSON.
- Return a single JSON object with this schema exactly:
  {{"samples":[{{"system":"...","user":"...","assistant":"...","source_kind":"upgrade|variant"}}]}}
- Every field except source_kind must be a JSON string.
- "assistant" must be a single plain-text or markdown string, never an object, array, or nested JSON value.
- Sample 1 must be an upgraded version of the source task with a stronger answer.
- Remaining samples must be close domain variants that train adjacent sub-skills.
- Keep the same language as the source user message.
- Be precise, concrete, and production-ready.
- Compress oversized source material into a focused task; do not copy giant enumerations or long checklists verbatim.
- Keep each assistant compact enough to fit comfortably in the token budget.
- If code is useful, include at most one minimal code block.
- No placeholders, no TODOs, no markdown fences around the JSON.

Source system:
{source_system}

Source user:
{source_user}

Source assistant excerpt:
{source_assistant}
"""


def build_repair_prompt(
    *,
    row: dict,
    domain: str,
    samples_per_source: int,
    raw_response: str,
) -> str:
    source_system, source_user, source_assistant = extract_messages(row)
    snippet = raw_response.strip()
    if len(snippet) > 4000:
        snippet = snippet[:4000]
    return f"""Your previous answer was invalid for automated parsing.

Regenerate the answer from the source below.
Return only valid JSON. Do not add markdown fences. Do not add explanations.
Use this exact schema:
{{"samples":[{{"system":"...","user":"...","assistant":"...","source_kind":"upgrade|variant"}}]}}

You must return exactly {samples_per_source} samples for domain "{domain}".
- Every field except source_kind must be a JSON string.
- "assistant" must be a single plain-text or markdown string, never an object or array.
- Keep the answer compact enough to stay well within the token budget.

Source system:
{clip_text(source_system or "(none)", 1200)}

Source user:
{clip_text(source_user, 4000)}

Source assistant excerpt:
{clip_text(source_assistant or "(none)", 2400)}

Previous invalid answer:
{snippet}
"""


def parse_teacher_payload(raw_text: str) -> dict:
    candidates = [raw_text.strip()]

    fenced = re.findall(
        r"```(?:json)?\s*(.*?)```", raw_text, flags=re.DOTALL | re.IGNORECASE
    )
    candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(raw_text[first_brace : last_brace + 1].strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
            return payload

    raise ValueError("Teacher response is not valid JSON with a 'samples' array")


def build_distilled_rows(
    payload: dict,
    *,
    domain: str,
    source_row: dict,
    provider: str | None,
    model: str | None,
    max_rows: int,
) -> list[dict]:
    source_id = str(source_row.get("id") or "")
    source_system, source_user, _source_assistant = extract_messages(source_row)
    if not source_id:
        source_fingerprint = hashlib.sha1(
            json.dumps(
                source_row.get("conversations", []), ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()[:12]
        source_id = source_fingerprint
    rows: list[dict] = []

    for index, sample in enumerate(payload["samples"][:max_rows], start=1):
        if not isinstance(sample, dict):
            continue
        system = stringify_sample_field(sample.get("system"), source_system)
        user = stringify_sample_field(sample.get("user"), source_user)
        assistant = stringify_sample_field(sample.get("assistant"), "")
        source_kind = str(
            sample.get("source_kind") or ("upgrade" if index == 1 else "variant")
        ).strip()
        if not system or not user or not assistant:
            continue

        row_id = f"{domain}-distill-{source_id}-{index:02d}"
        rows.append(
            make_row(
                row_id=row_id,
                system=system,
                user=user,
                assistant=assistant,
                meta={
                    "domain": domain,
                    "source_id": source_id,
                    "source_kind": source_kind,
                    "teacher_provider": provider,
                    "teacher_model": model,
                    "generated_at": int(time.time()),
                },
            )
        )

    return rows


def sample_source_rows(
    rows: list[dict], max_samples: int | None, seed: int
) -> list[dict]:
    selected = list(rows)
    rng = random.Random(seed)
    rng.shuffle(selected)
    if max_samples is not None:
        selected = selected[:max_samples]
    return selected


def default_output_path(domain: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return (
        Path(__file__).resolve().parent
        / "datasets"
        / "distilled"
        / f"{domain}_teacher_{stamp}.jsonl"
    )


def resolve_concurrency(requested: int, sample_count: int) -> int:
    if sample_count <= 1:
        return 1
    if requested <= 0:
        cpu_count = os.cpu_count() or 1
        requested = min(4, max(1, cpu_count // 3))
    return max(1, min(requested, sample_count))


def distill_source_row(
    *,
    index: int,
    row: dict,
    domain: str,
    samples_per_source: int,
    dry_run: bool,
    teacher_provider: str | None,
    teacher_model: str | None,
    strategy: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    sleep_ms: int,
    teacher_system: str,
    endpoint: EndpointConfig | None,
    headers: dict[str, str],
    json_retries: int,
) -> dict:
    source_id = str(row.get("id", f"row-{index}"))
    prompt = build_teacher_prompt(row, domain, samples_per_source)

    if dry_run:
        system, user, assistant = extract_messages(row)
        payload = {
            "samples": [
                {
                    "system": system,
                    "user": user,
                    "assistant": f"{assistant}\n\n[distilled dry-run sample {sample_index}]",
                    "source_kind": "upgrade" if sample_index == 1 else "variant",
                }
                for sample_index in range(1, samples_per_source + 1)
            ]
        }
        provider_used = "dry-run"
        model_used = "dry-run"
        latency_ms = 0.0
    else:
        route_strategy = "specific" if teacher_provider else strategy
        provider_used = None
        model_used = None
        payload = None
        latency_ms = 0.0
        last_error: Exception | None = None
        repair_raw = ""
        attempts = max(1, json_retries + 1)
        for attempt in range(attempts):
            user_prompt = (
                prompt
                if attempt == 0
                else build_repair_prompt(
                    row=row,
                    domain=domain,
                    samples_per_source=samples_per_source,
                    raw_response=repair_raw,
                )
            )
            body = {
                "messages": [{"role": "user", "content": user_prompt}],
                "strategy": route_strategy,
                "provider": teacher_provider,
                "model": teacher_model,
                "system": teacher_system,
                "temperature": temperature if attempt == 0 else 0.0,
                "max_tokens": max_tokens,
            }
            if teacher_provider == "mistral":
                body["response_format"] = {"type": "json_object"}
            try:
                started_at = time.perf_counter()
                response = request_json(
                    endpoint.send_url,
                    method="POST",
                    body=body,
                    headers=headers,
                    timeout=timeout,
                )
                provider_used = response.get("provider")
                model_used = response.get("model")
                if teacher_provider and provider_used != teacher_provider:
                    raise RuntimeError(
                        f"Strict teacher provider mismatch: requested {teacher_provider}, got {provider_used}"
                    )
                repair_raw = str(response.get("content", ""))
                latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                payload = parse_teacher_payload(repair_raw)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if isinstance(
                    exc, RuntimeError
                ) and "Strict teacher provider mismatch" in str(exc):
                    raise
                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 8))
                    continue
                if attempt == attempts - 1:
                    raise ValueError(
                        f"{exc} | raw={shorten(repair_raw, 1200)}"
                    ) from exc
        if payload is None:
            raise RuntimeError(
                str(last_error) if last_error else "Teacher response parsing failed"
            )

    rows = build_distilled_rows(
        payload,
        domain=domain,
        source_row=row,
        provider=provider_used,
        model=model_used,
        max_rows=samples_per_source,
    )

    if sleep_ms:
        time.sleep(sleep_ms / 1000)

    return {
        "index": index,
        "source_id": source_id,
        "rows": rows,
        "provider": provider_used,
        "model": model_used,
        "latency_ms": latency_ms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate distilled ShareGPT samples with a teacher model"
    )
    parser.add_argument("domain", choices=DEFAULT_DOMAINS)
    parser.add_argument("--source-dataset", default=None, help="Input ShareGPT JSONL")
    parser.add_argument("--out", default=None, help="Output ShareGPT JSONL")
    parser.add_argument("--report-path", default=None, help="Optional JSON report path")
    parser.add_argument(
        "--failures-out",
        default=None,
        help="Optional JSONL of source rows that failed distillation",
    )
    parser.add_argument(
        "--api-url",
        action="append",
        dest="api_urls",
        help="Mascarade base URL, repeatable",
    )
    parser.add_argument("--api-key", default="", help="MASCARADE_API_KEY bearer token")
    parser.add_argument(
        "--teacher-provider", default=None, help="Provider name to force, e.g. mistral"
    )
    parser.add_argument(
        "--teacher-model", default=None, help="Specific teacher model override"
    )
    parser.add_argument(
        "--strategy",
        default="best",
        help="Routing strategy when provider is not forced",
    )
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-source-samples", type=int, default=32)
    parser.add_argument("--samples-per-source", type=int, default=2)
    parser.add_argument(
        "--concurrency", type=int, default=0, help="Teacher calls in parallel (0=auto)"
    )
    parser.add_argument(
        "--json-retries",
        type=int,
        default=1,
        help="Retry count when teacher returns invalid JSON",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument(
        "--teacher-system-path",
        default=None,
        help="Optional file to override teacher system prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No HTTP call, emit deterministic synthetic rows",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed progress information"
    )
    verbosity.add_argument(
        "--quiet", action="store_true", help="Only print important messages"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    source_dataset = (
        Path(args.source_dataset)
        if args.source_dataset
        else script_dir / "datasets" / f"{args.domain}_chat.jsonl"
    )
    output_path = Path(args.out) if args.out else default_output_path(args.domain)
    report_path = (
        Path(args.report_path)
        if args.report_path
        else output_path.with_suffix(".report.json")
    )

    if not source_dataset.exists():
        raise SystemExit(f"Source dataset not found: {source_dataset}")

    source_rows = load_jsonl(source_dataset)
    selected_rows = ensure_row_ids(
        sample_source_rows(source_rows, args.max_source_samples, args.seed),
        f"{args.domain}-source",
    )
    resolved_concurrency = resolve_concurrency(args.concurrency, len(selected_rows))

    progress: tqdm | None = None

    def emit(message: str, *, important: bool = False) -> None:
        if args.quiet and not important:
            return
        if progress is not None:
            progress.write(message)
        else:
            print(message)

    teacher_system = (
        Path(args.teacher_system_path).read_text(encoding="utf-8")
        if args.teacher_system_path
        else DEFAULT_TEACHER_SYSTEM
    )

    headers: dict[str, str] = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    endpoint = None
    if not args.dry_run:
        api_urls = args.api_urls or DEFAULT_API_URLS
        endpoint = resolve_endpoint(api_urls, headers, args.timeout)
        emit(f"[OK] API: {endpoint.send_url}", important=True)
        emit(
            f"[OK] Providers: {', '.join(endpoint.providers) if endpoint.providers else '(none)'}",
            important=True,
        )
        if args.teacher_provider and args.teacher_provider not in endpoint.providers:
            emit(
                f"[WARN] Teacher provider '{args.teacher_provider}' is not currently advertised by the API",
                important=True,
            )

    if args.verbose:
        emit(f"[INFO] Source dataset: {source_dataset}", important=True)
        emit(
            f"[INFO] Selected source rows: {len(selected_rows)} / {len(source_rows)}",
            important=True,
        )
        emit(f"[INFO] Output dataset: {output_path}", important=True)
        emit(f"[INFO] Concurrency: {resolved_concurrency}", important=True)

    completed: list[dict] = []
    failures: list[dict] = []
    failed_rows: list[dict] = []
    progress = tqdm(
        total=len(selected_rows),
        desc=f"Distill {args.domain}",
        unit="sample",
        disable=args.quiet,
        dynamic_ncols=True,
    )
    with ThreadPoolExecutor(max_workers=resolved_concurrency) as executor:
        futures = {
            executor.submit(
                distill_source_row,
                index=index,
                row=row,
                domain=args.domain,
                samples_per_source=args.samples_per_source,
                dry_run=args.dry_run,
                teacher_provider=args.teacher_provider,
                teacher_model=args.teacher_model,
                strategy=args.strategy,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                sleep_ms=args.sleep_ms,
                teacher_system=teacher_system,
                endpoint=endpoint,
                headers=headers,
                json_retries=args.json_retries,
            ): index
            for index, row in enumerate(selected_rows, start=1)
        }

        for future in as_completed(futures):
            index = futures[future]
            row = selected_rows[index - 1]
            source_id = str(row.get("id", f"row-{index}"))
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append({"source_id": source_id, "error": str(exc)})
                failed_rows.append(dict(row))
                emit(
                    f"[FAIL] {index}/{len(selected_rows)} source={source_id} error={exc}",
                    important=True,
                )
                progress.update(1)
                continue

            completed.append(result)
            if args.verbose:
                emit(
                    f"[OK] {index}/{len(selected_rows)} source={result['source_id']} provider={result['provider']} model={result['model']} latency={result['latency_ms']}ms"
                )
            else:
                progress.set_postfix_str(
                    f"{result['provider'] or '-'} {result['latency_ms']:.0f}ms"
                )
            progress.update(1)

    distilled_rows: list[dict] = []
    for result in sorted(completed, key=lambda item: item["index"]):
        distilled_rows.extend(result["rows"])

    distilled_rows = dedupe_rows(distilled_rows)
    validation_errors = validate_rows(distilled_rows)
    if validation_errors:
        for error in validation_errors[:20]:
            print(f"[ERROR] {error}")
        raise SystemExit(
            f"Generated dataset is invalid ({len(validation_errors)} errors)"
        )

    write_jsonl(output_path, distilled_rows)

    report = {
        "domain": args.domain,
        "source_dataset": str(source_dataset),
        "output_dataset": str(output_path),
        "selected_source_rows": len(selected_rows),
        "generated_rows": len(distilled_rows),
        "failed_source_rows": len(failed_rows),
        "teacher_provider": args.teacher_provider,
        "teacher_model": args.teacher_model,
        "strategy": "specific" if args.teacher_provider else args.strategy,
        "api_url": None if endpoint is None else endpoint.base_url,
        "failures_out": (
            None if args.failures_out is None else str(Path(args.failures_out))
        ),
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.failures_out is not None:
        write_jsonl(Path(args.failures_out), failed_rows)

    emit(f"[OK] wrote distilled dataset: {output_path}", important=True)
    emit(f"[OK] wrote report: {report_path}", important=True)
    if args.failures_out is not None:
        emit(f"[OK] wrote failures dataset: {args.failures_out}", important=True)
    emit(f"[OK] rows: {len(distilled_rows)}", important=True)
    if failures:
        emit(f"[WARN] failures: {len(failures)}", important=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
