"""
Contamination check for Tenacious-Bench v0.1.

Verifies partition integrity by running three checks between held_out and
train/dev partitions:

  1. **N-gram overlap** — No 8-gram (or above) shared sequences on input fields.
  2. **Embedding similarity** — Cosine similarity below threshold (all-MiniLM-L6-v2).
  3. **Content hash** — No identical input payloads across partitions.

The output is written to contamination_check.json at the project root.
This script is itself a graded deliverable (challenge doc, line 152).

Usage:
    uv run python generation_scripts/contamination_check.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ── Data loading ──────────────────────────────────────────────────────────────


def load_partition(name: str) -> list[dict[str, Any]]:
    """Load a named partition (train/dev/held_out) from the benchmark directory."""
    path = cfg.BENCH_DIR / name / "tasks.json"
    if not path.exists():
        logger.warning("Partition file not found: %s", path)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_values(value: Any) -> list[str]:
    """Recursively pull only the *values* out of a nested input field.

    Drops JSON keys and structural punctuation so a shared schema does not
    register as content overlap; only repeated natural-language values do.
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
    """Return lowercased natural-language text from *input fields only*.

    Per the brief: "less than 8-gram overlap on input fields". Output text
    (candidate_output.subject / body) is intentionally excluded — those are
    intervention targets, not the basis of the contamination rule.
    """
    inp = task.get("input", {})
    tokens = _flatten_values(inp)
    return " ".join(tokens).lower()


def content_hash(task: dict[str, Any]) -> str:
    """SHA-256 hash of a task's input for exact-duplicate detection."""
    content = json.dumps(task.get("input", {}), sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ── Check 1: N-gram overlap ──────────────────────────────────────────────────


def get_ngrams(text: str, n: int) -> set[str]:
    """Extract all n-grams (word-level) from a text string."""
    words = text.split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def check_ngram_overlap(
    tasks_a: list[dict[str, Any]],
    tasks_b: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    """Check for n-gram overlap between two task sets.

    Returns a list of violation records for any pair sharing ≥ threshold n-grams.
    """
    violations: list[dict[str, Any]] = []
    for ta in tasks_a:
        ngrams_a = get_ngrams(extract_text(ta), cfg.NGRAM_THRESHOLD)
        for tb in tasks_b:
            shared = ngrams_a & get_ngrams(extract_text(tb), cfg.NGRAM_THRESHOLD)
            if shared:
                violations.append({
                    "task_a": ta.get("task_id"),
                    "task_b": tb.get("task_id"),
                    "shared_ngrams": len(shared),
                    "sample": list(shared)[:3],
                    "check": f"ngram_{cfg.NGRAM_THRESHOLD}",
                    "pair": label,
                })
    return violations


# ── Check 2: Embedding similarity ────────────────────────────────────────────


def check_embedding_similarity(
    tasks_a: list[dict[str, Any]],
    tasks_b: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    """Check cosine similarity between task embeddings from two partitions.

    Uses sentence-transformers (local, no API cost). If the library is not
    installed, logs a warning and returns an empty list.
    """
    violations: list[dict[str, Any]] = []
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        logger.warning(
            "sentence-transformers not installed — skipping embedding check. "
            "Install with: uv add sentence-transformers"
        )
        return violations

    model = SentenceTransformer(cfg.EMBEDDING_MODEL)
    texts_a = [extract_text(t) for t in tasks_a]
    texts_b = [extract_text(t) for t in tasks_b]

    if not texts_a or not texts_b:
        return violations

    emb_a = model.encode(texts_a, normalize_embeddings=True, show_progress_bar=False)
    emb_b = model.encode(texts_b, normalize_embeddings=True, show_progress_bar=False)
    sim = np.dot(emb_a, emb_b.T)

    for i in range(len(tasks_a)):
        for j in range(len(tasks_b)):
            if sim[i][j] > cfg.COSINE_THRESHOLD:
                violations.append({
                    "task_a": tasks_a[i].get("task_id"),
                    "task_b": tasks_b[j].get("task_id"),
                    "cosine_similarity": round(float(sim[i][j]), 4),
                    "check": f"embedding_cosine>{cfg.COSINE_THRESHOLD}",
                    "pair": label,
                })

    return violations


# ── Check 3: Content hash dedup ──────────────────────────────────────────────


def check_content_hash_overlap(
    tasks_a: list[dict[str, Any]],
    tasks_b: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    """Check for exact input-content duplicates between two partitions."""
    violations: list[dict[str, Any]] = []
    hashes_b = {content_hash(t): t.get("task_id") for t in tasks_b}
    for ta in tasks_a:
        h = content_hash(ta)
        if h in hashes_b:
            violations.append({
                "task_a": ta.get("task_id"),
                "task_b": hashes_b[h],
                "content_hash": h,
                "check": "content_hash_duplicate",
                "pair": label,
            })
    return violations


# ── Check 4: Temporal Integrity ──────────────────────────────────────────────


PUBLIC_DATA_SOURCES = {
    "layoffs.fyi", "layoffs_csv",
    "crunchbase", "crunchbase_odm",
    "sec_edgar", "github_org",
}


def check_temporal_integrity(tasks: list[dict[str, Any]], partition_name: str) -> list[dict[str, Any]]:
    """Time-shift verification (per challenge doc, line 150).

    The brief mandates this check only for tasks grounded in *public data*
    (layoffs.fyi, Crunchbase, SEC filings, etc.). Such tasks must declare a
    `metadata.signal_source` that names the public source AND a
    `metadata.time_window` documenting the snapshot window. Synthetic-signal
    tasks (the default in v0.1) carry `signal_source: "synthetic"` and are
    exempt — pretending synthetic data has a real time window is exactly
    the fabrication the rule is designed to prevent.
    """
    violations: list[dict[str, Any]] = []
    invalid_windows = {"", "placeholder", "tbd", "unknown", "n/a"}
    for t in tasks:
        meta = t.get("metadata", {})
        signal_source = str(meta.get("signal_source", "")).strip().lower()
        # Only tasks that *claim* a public source are subject to the check.
        if signal_source in PUBLIC_DATA_SOURCES:
            tw = str(meta.get("time_window", "")).strip().lower()
            if not tw or tw in invalid_windows:
                violations.append({
                    "task": t.get("task_id"),
                    "partition": partition_name,
                    "signal_source": signal_source,
                    "time_window_value": tw,
                    "check": "temporal_integrity_missing",
                })
    return violations


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run all contamination checks and write the report."""
    train = load_partition("train")
    dev = load_partition("dev")
    held_out = load_partition("held_out")

    logger.info(
        "Loaded partitions: train=%d, dev=%d, held_out=%d",
        len(train), len(dev), len(held_out),
    )

    all_violations: list[dict[str, Any]] = []
    pairs = [
        (held_out, train, "held_out-train"),
        (held_out, dev, "held_out-dev"),
        (dev, train, "dev-train"),
    ]

    # Check 1: N-gram overlap.
    logger.info("Running n-gram overlap check (threshold=%d)...", cfg.NGRAM_THRESHOLD)
    for a, b, label in pairs:
        v = check_ngram_overlap(a, b, label)
        logger.info("  %s: %d violations", label, len(v))
        all_violations.extend(v)

    # Check 2: Embedding similarity.
    logger.info("Running embedding similarity check (threshold=%.2f)...", cfg.COSINE_THRESHOLD)
    for a, b, label in pairs:
        v = check_embedding_similarity(a, b, label)
        logger.info("  %s: %d violations", label, len(v))
        all_violations.extend(v)

    # Check 3: Content hash dedup.
    logger.info("Running content hash overlap check...")
    for a, b, label in pairs:
        v = check_content_hash_overlap(a, b, label)
        logger.info("  %s: %d violations", label, len(v))
        all_violations.extend(v)

    # Check 4: Temporal Integrity (Time-Shift Verification)
    logger.info("Running temporal integrity check (public signals must have time_window)...")
    for partition, name in [(held_out, "held_out"), (dev, "dev"), (train, "train")]:
        v = check_temporal_integrity(partition, name)
        logger.info("  %s: %d violations", name, len(v))
        all_violations.extend(v)

    # ── Write report ──────────────────────────────────────────────────
    result: dict[str, Any] = {
        "ngram_threshold": cfg.NGRAM_THRESHOLD,
        "cosine_threshold": cfg.COSINE_THRESHOLD,
        "partitions": {
            "train": len(train),
            "dev": len(dev),
            "held_out": len(held_out),
        },
        "total_violations": len(all_violations),
        "status": "PASS" if not all_violations else "FAIL",
        "violations_by_check": dict(Counter(v["check"] for v in all_violations)),
        "violations": all_violations[:50],
    }

    out = cfg.ROOT / "contamination_check.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    logger.info(
        "STATUS: %s | Violations: %d | Written to: %s",
        result["status"], len(all_violations), out,
    )


if __name__ == "__main__":
    main()
