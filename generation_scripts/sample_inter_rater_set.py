"""
Build a 30-task stratified sample for inter-rater agreement labeling.

Reads the full benchmark (train + dev + held_out), draws a 30-task sample
stratified across the 14 failure dimensions (proportional to dimension
size, with 2 minimum per dimension where possible), and writes:

  - inter_rater/labeling_sheet.json  — task IDs, dimension, partition,
    input/output previews, and the rubric checks for each sampled task.
  - inter_rater/pass2_input.json     — same content, reshuffled, used as
    the Pass-2 worksheet so positional memory does not contaminate the
    second pass.

The sample is reproducible from the seed in `config.py`.

Usage:
    uv run python generation_scripts/sample_inter_rater_set.py
"""
from __future__ import annotations

import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


SAMPLE_SIZE = 30


def load_dataset() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for partition in ("train", "dev", "held_out"):
        path = cfg.BENCH_DIR / partition / "tasks.json"
        out.extend(json.loads(path.read_text(encoding="utf-8")))
    return out


def stratified_sample(tasks: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    """Stratify by dimension. Allocate at least one slot per dimension when
    possible, then top up proportionally to dimension size."""
    rng = random.Random(seed)
    by_dim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        by_dim[t.get("dimension", "unknown")].append(t)

    dim_names = sorted(by_dim.keys())
    total = sum(len(by_dim[d]) for d in dim_names)

    # Proportional allocation, rounded down, then distribute leftover by
    # remainder size.
    allocations: dict[str, int] = {}
    for d in dim_names:
        allocations[d] = max(1, round(len(by_dim[d]) / total * n))

    # Adjust to hit exactly n.
    diff = n - sum(allocations.values())
    if diff > 0:
        # Add extras to the biggest dimensions first.
        for d in sorted(dim_names, key=lambda x: -len(by_dim[x])):
            if diff == 0: break
            allocations[d] += 1
            diff -= 1
    elif diff < 0:
        for d in sorted(dim_names, key=lambda x: len(by_dim[x])):
            if diff == 0 or allocations[d] <= 1: continue
            allocations[d] -= 1
            diff += 1

    sampled: list[dict[str, Any]] = []
    for d in dim_names:
        pool = by_dim[d]
        rng.shuffle(pool)
        sampled.extend(pool[: allocations[d]])

    rng.shuffle(sampled)
    return sampled[:n]


def render_item(t: dict[str, Any], idx: int) -> dict[str, Any]:
    inp_str = json.dumps(t.get("input", {}), ensure_ascii=False)
    out_str = json.dumps(t.get("candidate_output", {}), ensure_ascii=False)
    return {
        "item_number": idx,
        "task_id": t["task_id"],
        "dimension": t.get("dimension"),
        "difficulty": t.get("difficulty"),
        "partition": t.get("partition"),
        "source_mode": t.get("source_mode"),
        "input_preview": inp_str[:280],
        "candidate_output_preview": out_str[:280],
        "ground_truth": (t.get("ground_truth") or {}).get("behavior_summary", ""),
        "checks": [
            {"id": c["id"], "type": c["type"], "points": c.get("points", 1)}
            for c in t.get("scoring", {}).get("checks", [])
        ],
        "max_score": t.get("scoring", {}).get("max_score"),
    }


def main() -> None:
    tasks = load_dataset()
    logger.info("Loaded %d total tasks", len(tasks))

    sample = stratified_sample(tasks, SAMPLE_SIZE, cfg.RANDOM_SEED)
    items = [render_item(t, i + 1) for i, t in enumerate(sample)]

    out_dir = cfg.ROOT / "inter_rater"
    out_dir.mkdir(parents=True, exist_ok=True)

    sheet_path = out_dir / "labeling_sheet.json"
    sheet_path.write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote %s (%d items)", sheet_path, len(items))

    # Pass-2 worksheet: reshuffled order, so memory of position doesn't carry.
    rng2 = random.Random(cfg.RANDOM_SEED + 99)
    p2 = items.copy()
    rng2.shuffle(p2)
    for i, it in enumerate(p2, start=1):
        it["item_number"] = i
    p2_path = out_dir / "pass2_input.json"
    p2_path.write_text(json.dumps(p2, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s (%d items, reshuffled)", p2_path, len(p2))

    # Distribution summary.
    from collections import Counter
    dim_dist = Counter(it["dimension"] for it in items)
    logger.info("Sample distribution by dimension:")
    for d, n in sorted(dim_dist.items(), key=lambda x: -x[1]):
        logger.info("  %-30s %d", d, n)


if __name__ == "__main__":
    main()
