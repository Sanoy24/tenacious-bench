#!/usr/bin/env python3
"""Validate a Tenacious-Bench-style dataset folder."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


EXPECTED_PARTITIONS = ("train", "dev", "held_out")
EXPECTED_RATIOS = {"train": 0.50, "dev": 0.30, "held_out": 0.20}


def iter_records(path: Path) -> Iterable[dict]:
    if path.suffix == ".jsonl":
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSONL on line {line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}: line {line_number} is not a JSON object")
            yield record
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc

    if isinstance(payload, dict):
        yield payload
        return

    if isinstance(payload, list):
        for index, record in enumerate(payload):
            if not isinstance(record, dict):
                raise ValueError(f"{path}: entry {index} is not a JSON object")
            yield record
        return

    raise ValueError(f"{path}: expected a JSON object, JSON array, or JSONL objects")


def extract_source_mode(record: dict) -> str | None:
    if "source_mode" in record:
        return record["source_mode"]
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get("source_mode")
    return None


def extract_task_id(record: dict) -> str | None:
    for key in ("task_id", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("task_id")
        if isinstance(value, str) and value.strip():
            return value
    return None


def validate_partition_dir(partition_dir: Path, partition: str) -> tuple[list[str], Counter, int]:
    issues: list[str] = []
    source_modes: Counter[str] = Counter()
    count = 0

    files = sorted(
        path for path in partition_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".json", ".jsonl"}
    )
    if not files:
        issues.append(f"{partition}: no .json or .jsonl task files found")
        return issues, source_modes, count

    for path in files:
        try:
            records = list(iter_records(path))
        except ValueError as exc:
            issues.append(str(exc))
            continue

        for index, record in enumerate(records, start=1):
            count += 1
            task_id = extract_task_id(record)
            if not task_id:
                issues.append(f"{path}: record {index} is missing task_id/id metadata")

            source_mode = extract_source_mode(record)
            if not source_mode:
                issues.append(f"{path}: record {index} is missing source_mode metadata")
            else:
                source_modes[source_mode] += 1

    return issues, source_modes, count


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Tenacious-Bench directory structure and task metadata.")
    parser.add_argument("bench_dir", help="Path to the dataset root containing train/, dev/, and held_out/")
    parser.add_argument(
        "--ratio-tolerance",
        type=float,
        default=0.05,
        help="Allowed absolute deviation from the target partition ratio (default: 0.05)",
    )
    parser.add_argument(
        "--enforce-total-range",
        action="store_true",
        help="Fail if total task count is outside the challenge target of 200-300 tasks",
    )
    args = parser.parse_args()

    bench_dir = Path(args.bench_dir).resolve()
    if not bench_dir.exists() or not bench_dir.is_dir():
        print(json.dumps({"ok": False, "error": f"{bench_dir} is not a directory"}, indent=2))
        return 2

    summary = {"bench_dir": str(bench_dir), "partitions": {}, "issues": []}
    total_tasks = 0
    combined_source_modes: Counter[str] = Counter()

    for partition in EXPECTED_PARTITIONS:
        partition_dir = bench_dir / partition
        if not partition_dir.is_dir():
            summary["issues"].append(f"missing partition directory: {partition}")
            continue

        issues, source_modes, count = validate_partition_dir(partition_dir, partition)
        total_tasks += count
        combined_source_modes.update(source_modes)
        summary["partitions"][partition] = {
            "count": count,
            "source_modes": dict(source_modes),
        }
        summary["issues"].extend(issues)

    if total_tasks == 0:
        summary["issues"].append("no tasks found across any partition")
    else:
        for partition, expected_ratio in EXPECTED_RATIOS.items():
            actual = summary["partitions"].get(partition, {}).get("count", 0) / total_tasks
            summary["partitions"].setdefault(partition, {})
            summary["partitions"][partition]["ratio"] = round(actual, 4)
            if abs(actual - expected_ratio) > args.ratio_tolerance:
                summary["issues"].append(
                    f"{partition}: ratio {actual:.3f} is outside tolerance {args.ratio_tolerance:.3f} from target {expected_ratio:.2f}"
                )

    if args.enforce_total_range and not (200 <= total_tasks <= 300):
        summary["issues"].append(f"total task count {total_tasks} is outside the target range 200-300")

    summary["total_tasks"] = total_tasks
    summary["all_source_modes"] = dict(combined_source_modes)
    summary["ok"] = not summary["issues"]

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
