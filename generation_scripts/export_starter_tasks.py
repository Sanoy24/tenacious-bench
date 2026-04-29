from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema.json"
OUTPUT_DIR = ROOT / "tenacious_bench_v0.1"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for task in schema["example_tasks"]:
        grouped[task["partition"]].append(task)

    for partition, tasks in grouped.items():
        partition_dir = OUTPUT_DIR / partition
        partition_dir.mkdir(parents=True, exist_ok=True)
        output_path = partition_dir / "tasks.json"
        output_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(tasks)} task(s) to {output_path}")


if __name__ == "__main__":
    main()
