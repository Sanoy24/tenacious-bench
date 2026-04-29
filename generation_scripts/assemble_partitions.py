"""
Assemble all raw task outputs into the final tenacious_bench_v0.1/ partitions.

Pipeline:
  1. Load raw outputs from all 4 generators.
  2. Deduplicate by task_id (first occurrence wins).
  3. Deduplicate by content hash (SHA-256 of input fields).
  4. Stratified split by dimension into train (50%), dev (30%), held_out (20%).
  5. Write partitions + composition summary.

Usage:
    uv run python generation_scripts/assemble_partitions.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Raw output files from each generator, in priority order.
RAW_FILES = [
    cfg.GENERATION_DIR / "programmatic_raw.json",
    cfg.GENERATION_DIR / "trace_derived_raw.json",
    cfg.GENERATION_DIR / "adversarial_raw.json",
    cfg.GENERATION_DIR / "synthesis_raw.json",
]


def load_all_raw() -> list[dict[str, Any]]:
    """Load and merge all raw task files that exist."""
    all_tasks: list[dict[str, Any]] = []
    for path in RAW_FILES:
        if path.exists():
            tasks = json.loads(path.read_text(encoding="utf-8"))
            logger.info("Loaded %4d tasks from %s", len(tasks), path.name)
            all_tasks.extend(tasks)
        else:
            logger.info("SKIP   %s (not found)", path.name)
    return all_tasks


def dedup_by_id(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate task_ids, keeping the first occurrence."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for t in tasks:
        tid = t.get("task_id", "")
        if tid not in seen:
            seen.add(tid)
            deduped.append(t)
    removed = len(tasks) - len(deduped)
    if removed:
        logger.info("Removed %d duplicate task_ids", removed)
    return deduped


def content_hash(task: dict[str, Any]) -> str:
    """SHA-256 hash of a task's input fields for near-duplicate detection."""
    content = json.dumps(task.get("input", {}), sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


SYNTHETIC_PLACEHOLDER_TIME_WINDOWS = {
    "2026-q1 layoffs.fyi extract",
    "2026-q1 competitor research extract",
    "2026-q1 icp-segment-boundary review",
}


def stamp_signal_lineage(tasks: list[dict[str, Any]]) -> None:
    """Mark each signal-bearing task with an explicit data-lineage label.

    Tenacious-Bench v0.1 is built on synthetic prospect / signal data — no
    task is grounded in a real layoffs.csv row or a real Crunchbase entry.
    Marking `metadata.signal_source = "synthetic"` makes that lineage
    explicit in the dataset itself and lets the contamination check skip
    the time-shift rule (which only applies to tasks grounded in public
    data, per the brief).

    Any placeholder `time_window` strings introduced before this lineage
    field existed are stripped here, so synthetic tasks do not appear to
    claim a real-world snapshot they were never derived from.
    """
    for t in tasks:
        inp = t.get("input", {})
        has_signal = bool(inp.get("hiring_signal_brief")) or bool(inp.get("competitor_gap_brief"))
        if not has_signal:
            continue
        meta = t.setdefault("metadata", {})
        meta.setdefault("signal_source", "synthetic")
        # Drop fabricated placeholder windows on synthetic tasks.
        if meta.get("signal_source") == "synthetic":
            tw = str(meta.get("time_window", "")).strip().lower()
            if tw in SYNTHETIC_PLACEHOLDER_TIME_WINDOWS:
                meta.pop("time_window", None)


def dedup_by_content(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove near-duplicate tasks based on input content hash."""
    seen_hashes: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for t in tasks:
        h = content_hash(t)
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(t)
    removed = len(tasks) - len(deduped)
    if removed:
        logger.info("Removed %d content-duplicate tasks", removed)
    return deduped


def partition_tasks(
    tasks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split tasks into train/dev/held_out with 50/30/20 ratio.

    Stratifies by dimension so each partition covers all dimensions
    proportionally. This prevents the held-out set from missing any
    failure family entirely.
    """
    random.shuffle(tasks)

    # Group by dimension.
    by_dim: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        dim = t.get("dimension", "unknown")
        by_dim.setdefault(dim, []).append(t)

    partitions: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "dev": [],
        "held_out": [],
    }

    for dim, dim_tasks in by_dim.items():
        n = len(dim_tasks)
        n_train = max(1, int(n * 0.50))
        n_dev = max(1, int(n * 0.30))
        # held_out gets the rest.
        partitions["train"].extend(dim_tasks[:n_train])
        partitions["dev"].extend(dim_tasks[n_train : n_train + n_dev])
        partitions["held_out"].extend(dim_tasks[n_train + n_dev :])

    # Stamp partition field on each task.
    for part_name, part_tasks in partitions.items():
        for t in part_tasks:
            t["partition"] = part_name

    return partitions


def log_composition(partitions: dict[str, list[dict[str, Any]]]) -> None:
    """Log a human-readable bench composition summary."""
    total = sum(len(v) for v in partitions.values())
    logger.info("=" * 60)
    logger.info("BENCH COMPOSITION")
    logger.info("=" * 60)
    logger.info("Total tasks: %d", total)

    for name, tasks in partitions.items():
        pct = len(tasks) / total * 100 if total else 0
        logger.info("  %s: %d (%.0f%%)", name, len(tasks), pct)

    # By dimension.
    all_tasks = [t for tasks in partitions.values() for t in tasks]
    logger.info("By dimension:")
    for dim, count in sorted(
        Counter(t.get("dimension", "unknown") for t in all_tasks).items(),
        key=lambda x: -x[1],
    ):
        logger.info("  %s: %d", dim, count)

    # By source mode.
    logger.info("By source mode:")
    for mode, count in sorted(
        Counter(t.get("source_mode", "unknown") for t in all_tasks).items(),
        key=lambda x: -x[1],
    ):
        pct = count / total * 100 if total else 0
        logger.info("  %s: %d (%.0f%%)", mode, count, pct)

    # By difficulty.
    logger.info("By difficulty:")
    for diff, count in sorted(
        Counter(t.get("difficulty", "unknown") for t in all_tasks).items(),
    ):
        logger.info("  %s: %d", diff, count)


def main() -> None:
    """Assemble the final benchmark from all raw generator outputs."""
    random.seed(cfg.RANDOM_SEED)

    logger.info("Loading raw task files...")
    all_tasks = load_all_raw()

    if not all_tasks:
        logger.error("No raw tasks found. Run the generators first:")
        logger.error("  uv run python generation_scripts/run_all.py")
        return

    logger.info("Total raw tasks: %d", len(all_tasks))

    # Dedup.
    logger.info("Deduplicating...")
    all_tasks = dedup_by_id(all_tasks)
    all_tasks = dedup_by_content(all_tasks)
    logger.info("Final task count after dedup: %d", len(all_tasks))

    # Stamp data-lineage metadata before partitioning.
    stamp_signal_lineage(all_tasks)

    # Partition.
    logger.info("Partitioning (50/30/20)...")
    partitions = partition_tasks(all_tasks)

    # Write partitions.
    for name, tasks in partitions.items():
        out_dir = cfg.BENCH_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "tasks.json"
        out_path.write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Written %d tasks to %s", len(tasks), out_path)

    log_composition(partitions)

    # Write composition summary.
    all_tasks_flat = [t for tasks in partitions.values() for t in tasks]
    summary: dict[str, Any] = {
        "total_tasks": sum(len(v) for v in partitions.values()),
        "partitions": {k: len(v) for k, v in partitions.items()},
        "by_dimension": dict(
            Counter(t.get("dimension", "unknown") for t in all_tasks_flat)
        ),
        "by_source_mode": dict(
            Counter(t.get("source_mode", "unknown") for t in all_tasks_flat)
        ),
        "by_difficulty": dict(
            Counter(t.get("difficulty", "unknown") for t in all_tasks_flat)
        ),
    }
    summary_path = cfg.BENCH_DIR / "composition_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Composition summary: %s", summary_path)


if __name__ == "__main__":
    main()
