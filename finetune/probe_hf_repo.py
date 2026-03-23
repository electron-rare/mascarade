#!/usr/bin/env python3
"""Probe Hugging Face model/dataset repos before download or training."""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request


def probe(repo_type: str, repo_id: str, timeout: float) -> dict:
    api_path = "models" if repo_type == "model" else "datasets"
    url = f"https://huggingface.co/api/{api_path}/{repo_id}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "mascarade-hf-probe/1.0"},
        method="GET",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=context
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "repo_type": repo_type,
                "repo_id": repo_id,
                "url": url,
                "status": getattr(response, "status", 200),
                "sha": payload.get("sha"),
                "private": payload.get("private"),
                "downloads": payload.get("downloads"),
                "likes": payload.get("likes"),
                "last_modified": payload.get("lastModified"),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "repo_type": repo_type,
            "repo_id": repo_id,
            "url": url,
            "status": exc.code,
            "error": f"http:{exc.code}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "repo_type": repo_type,
            "repo_id": repo_id,
            "url": url,
            "status": None,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id")
    parser.add_argument("--repo-type", choices=("model", "dataset"), default="model")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = probe(args.repo_type, args.repo_id, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["ok"]:
            print(
                f"{result['repo_type']}:{result['repo_id']} ok "
                f"downloads={result.get('downloads')} likes={result.get('likes')}"
            )
        else:
            print(
                f"{result['repo_type']}:{result['repo_id']} failed "
                f"status={result.get('status')} error={result.get('error')}",
                file=sys.stderr,
            )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
