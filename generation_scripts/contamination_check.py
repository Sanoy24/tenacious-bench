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


def extract_text(task: dict[str, Any]) -> str:
    """Flatten a task's input and output fields into a single lowercase string.

    This is the text representation used for both n-gram and embedding checks.
    """
    parts: list[str] = []

    # Input fields.
    inp = task.get("input", {})
    for key in ["prospect", "hiring_signal_brief", "competitor_gap_brief", "prior_thread"]:
        val = inp.get(key, "")
        if isinstance(val, dict):
            parts.append(json.dumps(val, sort_keys=True))
        elif isinstance(val, list):
            parts.append(" ".join(str(v) for v in val))
        elif val:
            parts.append(str(val))

    # Output fields.
    out = task.get("candidate_output", {})
    parts.append(out.get("subject", ""))
    parts.append(out.get("body", ""))

    return " ".join(parts).lower()


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
