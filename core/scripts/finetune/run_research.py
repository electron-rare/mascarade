#!/usr/bin/env python3
"""Quick research script — search models and datasets via fine-tuning agents.

Usage:
    python scripts/finetune/run_research.py --task text-generation --domain code
    python scripts/finetune/run_research.py --task code --max-size 3.0 --languages en,fr
"""
import asyncio
import os
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.registry import DatasetEntry, FinetuneRegistry, ModelEntry


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fine-tuning research")
    parser.add_argument("--task", default="text-generation", help="Model task")
    parser.add_argument("--domain", default="code", help="Dataset domain")
    parser.add_argument("--max-size", type=float, default=4.0, help="Max model size GB")
    parser.add_argument("--top-k", type=int, default=5, help="Top candidates")
    parser.add_argument("--languages", default="en", help="Comma-separated languages")
    parser.add_argument("--hf-token", default=os.environ.get("HUGGINGFACE_API_KEY", ""))
    args = parser.parse_args()

    languages = args.languages.split(",")
    registry = FinetuneRegistry()

    # Research models
    print(f"\n{'='*60}")
    print(f"RECHERCHE MODÈLES: task={args.task} max_size={args.max_size}GB")
    print(f"{'='*60}\n")

    researcher = ResearcherAgent(hf_token=args.hf_token)
    report = await researcher.recommend(args.task, max_size_gb=args.max_size, top_k=args.top_k)

    for i, m in enumerate(report["candidates"], 1):
        print(f"  {i}. {m['model_id']}")
        print(f"     downloads={m['downloads']:,} likes={m['likes']:,} license={m['license']} size={m['size_gb']}GB")
        registry.add_model(ModelEntry(
            model_id=m["model_id"], source="huggingface", task=args.task,
            size_gb=m["size_gb"], license=m["license"], downloads=m["downloads"],
            likes=m["likes"],
        ))

    if report["papers"]:
        print("\n  Papers:")
        for p in report["papers"]:
            print(f"    - {p['title'][:80]}")

    # Research datasets
    print(f"\n{'='*60}")
    print(f"RECHERCHE DATASETS: domain={args.domain} languages={languages}")
    print(f"{'='*60}\n")

    documentalist = DocumentalistAgent(hf_token=args.hf_token)
    ds_report = await documentalist.recommend(args.domain, top_k=args.top_k, languages=languages)

    for i, d in enumerate(ds_report["candidates"], 1):
        print(f"  {i}. {d['dataset_id']}")
        print(f"     downloads={d['downloads']:,} likes={d['likes']:,} license={d['license']} langs={d.get('languages', [])}")
        registry.add_dataset(DatasetEntry(
            dataset_id=d["dataset_id"], source="huggingface", domain=args.domain,
            license=d["license"],
        ))

    # Summary
    print(f"\n{'='*60}")
    print("RÉSUMÉ")
    print(f"{'='*60}")
    print(f"  Modèles trouvés: {len(report['candidates'])}")
    print(f"  Datasets trouvés: {len(ds_report['candidates'])}")
    print(f"  Registry: {registry.path}")
    if report["candidates"]:
        print(f"  → Meilleur modèle: {report['candidates'][0]['model_id']}")
    if ds_report["candidates"]:
        print(f"  → Meilleur dataset: {ds_report['candidates'][0]['dataset_id']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
