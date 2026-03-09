#!/usr/bin/env python3
"""Probe domain research sources over HTTP and persist a machine-readable report."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCES_DIR = SCRIPT_DIR / "research_sources" / "domains"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "research_probes"
URL_KEYS = (
    "authoritative_urls",
    "github_repos",
    "software_sources",
    "forum_urls",
    "datasheet_roots",
)


def _http_probe(url: str, timeout: float) -> dict:
    headers = {"User-Agent": "mascarade-research-probe/1.0"}
    context = ssl.create_default_context()
    methods = ("HEAD", "GET")
    last_error = ""
    for method in methods:
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return {
                    "ok": True,
                    "status": getattr(response, "status", 200),
                    "final_url": response.geturl(),
                    "method": method,
                }
        except urllib.error.HTTPError as exc:
            if 200 <= exc.code < 400:
                return {
                    "ok": True,
                    "status": exc.code,
                    "final_url": url,
                    "method": method,
                }
            last_error = f"http:{exc.code}"
            if method == "HEAD" and exc.code in {403, 405}:
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if method == "HEAD":
                continue
            break
    return {"ok": False, "status": None, "final_url": url, "method": "GET", "error": last_error}


def _probe_entry(item: dict, group: str, timeout: float) -> dict | None:
    label = item.get("label")
    url = item.get("url")
    if not label or not url:
        return None
    result = _http_probe(str(url), timeout=timeout)
    return {
        "group": group,
        "label": str(label),
        "url": str(url),
        **result,
    }


def probe_domain(path: Path, output_dir: Path, timeout: float) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    domain = str(payload.get("domain") or path.stem)
    planned_entries: list[tuple[str, dict]] = []
    for key in URL_KEYS:
        for item in payload.get(key, []):
            planned_entries.append((key, item))

    max_workers = min(16, max(4, len(planned_entries) or 1))
    entries: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_probe_entry, item, key, timeout)
            for key, item in planned_entries
        ]
        for future in concurrent.futures.as_completed(futures):
            entry = future.result()
            if entry is not None:
                entries.append(entry)
    entries.sort(key=lambda item: (item["group"], item["label"], item["url"]))
    total = len(entries)
    ok_count = sum(1 for item in entries if item["ok"])
    probe = {
        "domain": domain,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_file": str(path),
        "status": "ok" if total > 0 and ok_count == total else ("partial" if ok_count else "failed"),
        "reachable_count": ok_count,
        "total_count": total,
        "reachable_ratio": (ok_count / total) if total else 0.0,
        "entries": entries,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{domain}.json").write_text(
        json.dumps(probe, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return probe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domains", nargs="*", help="Specific domains to probe")
    parser.add_argument("--sources-dir", default=str(DEFAULT_SOURCES_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--max-domain-workers", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sources_dir = Path(args.sources_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if args.domains:
        files = [sources_dir / f"{domain}.json" for domain in args.domains]
    else:
        files = sorted(sources_dir.glob("*.json"))
    reports = []
    errors = []
    existing_files = []
    for path in files:
        if not path.exists():
            errors.append(f"missing source file: {path}")
            continue
        existing_files.append(path)
    max_domain_workers = max(1, int(args.max_domain_workers))
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(max_domain_workers, max(1, len(existing_files)))
    ) as executor:
        future_map = {
            executor.submit(probe_domain, path, output_dir, args.timeout): path
            for path in existing_files
        }
        for future in concurrent.futures.as_completed(future_map):
            path = future_map[future]
            try:
                reports.append(future.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.stem}: {exc}")
    reports.sort(key=lambda item: item["domain"])
    payload = {"reports": reports, "errors": errors}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for report in reports:
            print(
                f"{report['domain']}: status={report['status']} "
                f"reachable={report['reachable_count']}/{report['total_count']}"
            )
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors or any(report["status"] == "failed" for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
