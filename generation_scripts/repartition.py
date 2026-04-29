"""
Contamination-aware re-partitioner for Tenacious-Bench v0.1.

The default `assemble_partitions.py` stratifies only by dimension. Programmatic
generators emit families of tasks that share template scaffolding, so two
tasks from the same template family routinely share 8-grams. When such
siblings land in different partitions, the contamination check fails.

This script fixes that by:
  1. Loading all assembled tasks from train/dev/held_out.
  2. Building a near-duplicate graph: edge between two tasks iff they share
     any 8-gram on the input/output text OR their cosine similarity > 0.85.
  3. Finding connected components (each component is treated atomically).
  4. Distributing components across partitions per dimension, targeting
     50 / 30 / 20 split as closely as the component sizes permit.

The output replaces the existing partition files. Re-run `contamination_check.py`
afterwards to confirm `status: PASS`.

Usage:
    uv run python generation_scripts/repartition.py
"""
from __future__ import annotations

import json
import logging
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _flatten_values(value: Any) -> list[str]:
    """Recursively pull only the *values* out of an input field, dropping JSON
    keys and structural punctuation. This way a shared schema (`contact_title`,
    `timezone`, ...) does not register as content overlap; only repeated
    natural-language values do.
    """
    out: list[str] = []
    if isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_values(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_flatten_values(v))
    elif value is None or value == "":
        return out
    else:
        out.append(str(value))
    return out


def extract_text(task: dict[str, Any]) -> str:
    """Return lowercased natural-language text from the *input fields only*.

    The challenge brief specifies the contamination rule as "less than 8-gram
    overlap on input fields" — output text is excluded. Values are flattened
    and joined; structural keys are dropped to prevent shared JSON schema
    from masquerading as contamination.
    """
    inp = task.get("input", {})
    tokens = _flatten_values(inp)
    return " ".join(tokens).lower()


def get_ngrams(text: str, n: int) -> set[str]:
    words = text.split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def build_components(
    tasks: list[dict[str, Any]],
    ngram_n: int,
    cosine_threshold: float,
) -> list[list[int]]:
    """Build connected components on the near-duplicate graph.

    An edge connects two tasks iff they share any n-gram on the combined
    input/output text OR their embedding cosine similarity exceeds the
    threshold. Tasks in the same component must go into the same partition.
    """
    n = len(tasks)
    uf = UnionFind(n)
    texts = [extract_text(t) for t in tasks]

    # Edge type 1: shared n-gram. Use inverted index for O(N * avg_ngrams) build.
    logger.info("Building n-gram inverted index (n=%d)...", ngram_n)
    ngram_to_tasks: dict[str, list[int]] = defaultdict(list)
    for i, text in enumerate(texts):
        for g in get_ngrams(text, ngram_n):
            ngram_to_tasks[g].append(i)

    edge_count = 0
    for ngram, idxs in ngram_to_tasks.items():
        if len(idxs) > 1:
            first = idxs[0]
            for j in idxs[1:]:
                if uf.find(first) != uf.find(j):
                    uf.union(first, j)
                    edge_count += 1
    logger.info("  Added %d n-gram-driven union ops", edge_count)

    # Edge type 2: high embedding similarity.
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        logger.info("Computing embeddings (%s)...", cfg.EMBEDDING_MODEL)
        model = SentenceTransformer(cfg.EMBEDDING_MODEL)
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        sim = np.dot(emb, emb.T)
        edge_count = 0
        for i in range(n):
            for j in range(i + 1, n):
                if sim[i][j] > cosine_threshold:
                    if uf.find(i) != uf.find(j):
                        uf.union(i, j)
                        edge_count += 1
        logger.info("  Added %d embedding-driven union ops", edge_count)
    except ImportError:
        logger.warning("sentence-transformers missing; skipping embedding edges")

    # Collect components.
    comps: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        comps[uf.find(i)].append(i)
    components = list(comps.values())
    components.sort(key=len, reverse=True)
    logger.info(
        "Components: %d (largest=%d, singletons=%d)",
        len(components),
        len(components[0]) if components else 0,
        sum(1 for c in components if len(c) == 1),
    )
    return components


def assign_components_to_partitions(
    tasks: list[dict[str, Any]],
    components: list[list[int]],
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    """Assign whole components to partitions, balancing dimension stratification.

    Greedy: for each dimension, walk its components in size-descending order
    and place each into whichever partition is most under its dimension target
    (50/30/20).
    """
    rng = random.Random(seed)
    partitions: dict[str, list[dict[str, Any]]] = {"train": [], "dev": [], "held_out": []}
    targets = {"train": 0.50, "dev": 0.30, "held_out": 0.20}

    # Group components by their dominant dimension.
    comps_by_dim: dict[str, list[list[int]]] = defaultdict(list)
    for comp in components:
        # Dominant dimension within the component.
        dim_counts = Counter(tasks[i].get("dimension", "unknown") for i in comp)
        dim = dim_counts.most_common(1)[0][0]
        comps_by_dim[dim].append(comp)

    for dim, comps in comps_by_dim.items():
        # Shuffle components of equal size for variety, then sort largest first.
        rng.shuffle(comps)
        comps.sort(key=len, reverse=True)
        total_dim = sum(len(c) for c in comps)
        dim_targets = {p: targets[p] * total_dim for p in partitions}
        dim_filled = {p: 0 for p in partitions}

        for comp in comps:
            # Place this component where (current count + comp size) is furthest
            # below target — i.e., the partition with the largest deficit.
            best_p = max(
                partitions.keys(),
                key=lambda p: dim_targets[p] - dim_filled[p],
            )
            for idx in comp:
                t = dict(tasks[idx])
                t["partition"] = best_p
                partitions[best_p].append(t)
            dim_filled[best_p] += len(comp)

    return partitions


def main() -> None:
    rng_seed = cfg.RANDOM_SEED

    # Load currently assembled tasks (any partition).
    all_tasks: list[dict[str, Any]] = []
    for name in ("train", "dev", "held_out"):
        path = cfg.BENCH_DIR / name / "tasks.json"
        if path.exists():
            all_tasks.extend(json.loads(path.read_text(encoding="utf-8")))
    logger.info("Loaded %d total tasks across partitions", len(all_tasks))

    # Drop any cached partition assignments.
    for t in all_tasks:
        t.pop("partition", None)

    components = build_components(
        all_tasks,
        ngram_n=cfg.NGRAM_THRESHOLD,
        cosine_threshold=cfg.COSINE_THRESHOLD,
    )

    partitions = assign_components_to_partitions(all_tasks, components, rng_seed)

    # Write back.
    for name, tasks in partitions.items():
        out = cfg.BENCH_DIR / name / "tasks.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Wrote %3d tasks → %s", len(tasks), out)

    # Composition summary.
    total = sum(len(v) for v in partitions.values())
    flat = [t for ts in partitions.values() for t in ts]
    summary = {
        "total_tasks": total,
        "partitions": {k: len(v) for k, v in partitions.items()},
        "partition_ratios": {
            k: round(len(v) / total, 3) if total else 0
            for k, v in partitions.items()
        },
        "by_dimension": dict(Counter(t.get("dimension", "unknown") for t in flat)),
        "by_source_mode": dict(Counter(t.get("source_mode", "unknown") for t in flat)),
        "by_difficulty": dict(Counter(t.get("difficulty", "unknown") for t in flat)),
    }
    (cfg.BENCH_DIR / "composition_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("=" * 60)
    logger.info("Re-partition complete. Now run contamination_check.py.")


if __name__ == "__main__":
    main()
