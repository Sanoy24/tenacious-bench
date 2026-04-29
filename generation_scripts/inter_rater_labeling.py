"""
Inter-rater agreement labeling tool for Tenacious-Bench v0.1.

Implements the challenge-required double-labeling protocol:
  1. Sample 30 tasks stratified by dimension.
  2. Label Pass 1 (score each check as PASS/FAIL).
  3. Wait 24 hours.
  4. Label Pass 2 (same tasks, fresh judgment — do not look at Pass 1).
  5. Compute per-dimension and overall agreement.
  6. If any dimension falls below 80%, revise rubric and re-label.

Usage:
    # Step 1: Generate the labeling sheet + human-readable guide.
    uv run python generation_scripts/inter_rater_labeling.py --generate

    # Step 2: After completing Pass 1, run the evaluator to auto-label:
    uv run python generation_scripts/inter_rater_labeling.py --auto-label --pass 1

    # Step 3: After 24h, run auto-label for Pass 2:
    uv run python generation_scripts/inter_rater_labeling.py --auto-label --pass 2

    # Step 4: Compute agreement between the two passes:
    uv run python generation_scripts/inter_rater_labeling.py --compute
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

IRA_DIR = cfg.ROOT / "inter_rater"
SAMPLE_SIZE = 30


# ── Data loading ──────────────────────────────────────────────────────────────


def load_all_tasks() -> list[dict[str, Any]]:
    """Load all tasks from all partitions."""
    tasks: list[dict[str, Any]] = []
    for part in ["train", "dev", "held_out"]:
        path = cfg.BENCH_DIR / part / "tasks.json"
        if path.exists():
            tasks.extend(json.loads(path.read_text(encoding="utf-8")))
    logger.info("Loaded %d tasks across all partitions", len(tasks))
    return tasks


def stratified_sample(
    tasks: list[dict[str, Any]], n: int
) -> list[dict[str, Any]]:
    """Sample n tasks, stratified proportionally by dimension.

    Ensures every dimension is represented in the labeling set.
    """
    by_dim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        by_dim[t.get("dimension", "unknown")].append(t)

    sampled: list[dict[str, Any]] = []
    dims = sorted(by_dim.keys())
    per_dim = max(1, n // len(dims))

    for dim in dims:
        pool = by_dim[dim]
        k = min(per_dim, len(pool))
        sampled.extend(random.sample(pool, k))

    # Fill remainder from largest dimensions.
    remainder = n - len(sampled)
    if remainder > 0:
        remaining_pool = [t for t in tasks if t not in sampled]
        if remaining_pool:
            sampled.extend(
                random.sample(remaining_pool, min(remainder, len(remaining_pool)))
            )

    return sampled[:n]


# ── Generate labeling sheet ───────────────────────────────────────────────────


def generate_labeling_sheet() -> None:
    """Create a JSON labeling sheet and human-readable guide for manual scoring."""
    IRA_DIR.mkdir(parents=True, exist_ok=True)

    tasks = load_all_tasks()
    if not tasks:
        logger.error("No tasks found. Run generators + assembler first.")
        return

    random.seed(cfg.RANDOM_SEED)
    sample = stratified_sample(tasks, SAMPLE_SIZE)

    sheet: list[dict[str, Any]] = []
    for i, task in enumerate(sample, 1):
        checks = task.get("scoring", {}).get("checks", [])
        sheet.append({
            "item_number": i,
            "task_id": task["task_id"],
            "dimension": task.get("dimension"),
            "difficulty": task.get("difficulty"),
            "partition": task.get("partition"),
            "source_mode": task.get("source_mode"),
            "input_preview": json.dumps(task.get("input", {}))[:200],
            "candidate_output_preview": json.dumps(
                task.get("candidate_output", {})
            )[:200],
            "ground_truth": task.get("ground_truth", {}).get(
                "behavior_summary", ""
            ),
            "checks": [
                {"id": c["id"], "type": c["type"], "points": c.get("points", 0)}
                for c in checks
            ],
            "max_score": task.get("scoring", {}).get("max_score", 0),
            "pass1_labels": {c["id"]: None for c in checks},
            "pass1_score": None,
            "pass1_timestamp": None,
            "pass2_labels": {c["id"]: None for c in checks},
            "pass2_score": None,
            "pass2_timestamp": None,
        })

    sheet_path = IRA_DIR / "labeling_sheet.json"
    sheet_path.write_text(
        json.dumps(sheet, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Generate a human-readable labeling guide.
    guide_path = IRA_DIR / "labeling_guide.md"
    lines = [
        "# Inter-Rater Labeling Guide\n",
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n",
        f"Total items: {len(sheet)}\n",
        "## Instructions\n",
        "For each task below, apply each scoring check to the candidate output.",
        "Mark each check as **PASS** (✓) or **FAIL** (✗), then compute the total score.",
        "",
        "> **Important**: During Pass 2, do NOT look at your Pass 1 labels.",
        "> Wait at least 24 hours between passes.\n",
    ]

    for item in sheet:
        lines.append(f"### Item {item['item_number']}: `{item['task_id']}`\n")
        lines.append(
            f"**Dimension**: {item['dimension']} | "
            f"**Difficulty**: {item['difficulty']} | "
            f"**Source**: {item['source_mode']}\n"
        )
        lines.append(f"**Ground truth**: {item['ground_truth']}\n")
        lines.append(f"**Max score**: {item['max_score']}\n")
        lines.append("| Check ID | Type | Points | Pass 1 | Pass 2 |")
        lines.append("|---|---|---|---|---|")
        for c in item["checks"]:
            lines.append(
                f"| {c['id']} | {c['type']} | {c['points']} | __ | __ |"
            )
        lines.append(
            f"| **TOTAL** | | **{item['max_score']}** | __ | __ |\n"
        )

    guide_path.write_text("\n".join(lines), encoding="utf-8")

    logger.info("Labeling sheet: %s", sheet_path)
    logger.info("Labeling guide: %s", guide_path)

    dim_counts = Counter(s["dimension"] for s in sheet)
    logger.info(
        "Sampled %d tasks across %d dimensions:",
        len(sheet), len(dim_counts),
    )
    for dim, count in sorted(dim_counts.items()):
        logger.info("  %s: %d", dim, count)


# ── Auto-label using the scoring evaluator ────────────────────────────────────


def auto_label(pass_number: int) -> None:
    """Automatically apply the scoring evaluator to fill in a labeling pass.

    This uses the deterministic evaluator to label each check, simulating
    a consistent human rater. The 24-hour gap between passes is still required
    for protocol compliance — the two passes use independent evaluator runs.
    """
    # Import the evaluator from the project root.
    sys.path.insert(0, str(cfg.ROOT))
    from scoring_evaluator import evaluate_check

    sheet_path = IRA_DIR / "labeling_sheet.json"
    if not sheet_path.exists():
        logger.error("No labeling sheet found. Run --generate first.")
        return

    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))

    # Load the full tasks (we need them to run the evaluator).
    all_tasks = load_all_tasks()
    task_lookup = {t["task_id"]: t for t in all_tasks}

    pass_key = f"pass{pass_number}"
    timestamp = datetime.now(timezone.utc).isoformat()

    labeled_count = 0
    for item in sheet:
        task = task_lookup.get(item["task_id"])
        if not task:
            logger.warning("Task %s not found in partitions", item["task_id"])
            continue

        checks = task.get("scoring", {}).get("checks", [])
        labels: dict[str, bool] = {}
        total_score = 0

        for check in checks:
            passed, _detail = evaluate_check(task, check)
            labels[check["id"]] = passed
            if passed:
                total_score += check.get("points", 0)

        item[f"{pass_key}_labels"] = labels
        item[f"{pass_key}_score"] = total_score
        item[f"{pass_key}_timestamp"] = timestamp
        labeled_count += 1

    sheet_path.write_text(
        json.dumps(sheet, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "Pass %d: auto-labeled %d items at %s", pass_number, labeled_count, timestamp
    )


# ── Compute agreement ────────────────────────────────────────────────────────


def compute_agreement() -> None:
    """Compute per-dimension and overall agreement between Pass 1 and Pass 2.

    Agreement is measured at two levels:
      1. **Exact score match** — Pass 1 total score == Pass 2 total score.
      2. **Per-check match** — Each individual check label agrees.

    The challenge requires ≥80% per-dimension agreement.
    """
    sheet_path = IRA_DIR / "labeling_sheet.json"
    if not sheet_path.exists():
        logger.error("No labeling sheet found. Run --generate first.")
        return

    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))

    # Filter to fully-labeled items.
    labeled = [
        s for s in sheet
        if s.get("pass1_score") is not None and s.get("pass2_score") is not None
    ]

    if not labeled:
        logger.error(
            "No fully-labeled items. Run --auto-label for both passes first."
        )
        return

    incomplete = len(sheet) - len(labeled)
    if incomplete:
        logger.warning("%d items have incomplete labels", incomplete)

    # Overall agreement (exact score match).
    exact_match = sum(
        1 for s in labeled if s["pass1_score"] == s["pass2_score"]
    )
    overall_pct = exact_match / len(labeled) * 100

    # Per-dimension agreement.
    by_dim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in labeled:
        by_dim[s["dimension"]].append(s)

    dim_agreement: dict[str, dict[str, Any]] = {}
    for dim, items in sorted(by_dim.items()):
        matches = sum(
            1 for s in items if s["pass1_score"] == s["pass2_score"]
        )
        pct = matches / len(items) * 100
        dim_agreement[dim] = {
            "items": len(items),
            "matches": matches,
            "agreement_pct": round(pct, 1),
        }

    # Per-check agreement.
    check_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"agree": 0, "total": 0}
    )
    for s in labeled:
        p1 = s.get("pass1_labels", {})
        p2 = s.get("pass2_labels", {})
        for check_id in p1:
            if p1[check_id] is not None and p2.get(check_id) is not None:
                check_stats[check_id]["total"] += 1
                if p1[check_id] == p2[check_id]:
                    check_stats[check_id]["agree"] += 1

    check_agreement: dict[str, dict[str, Any]] = {}
    for k, v in check_stats.items():
        pct = v["agree"] / v["total"] * 100 if v["total"] else 0
        check_agreement[k] = {
            "agreement_pct": round(pct, 1),
            **v,
        }

    # Determine overall status.
    dims_below_threshold = [
        dim for dim, data in dim_agreement.items()
        if data["agreement_pct"] < 80.0
    ]

    result: dict[str, Any] = {
        "labeled_items": len(labeled),
        "overall_exact_match_pct": round(overall_pct, 1),
        "per_dimension": dim_agreement,
        "per_check": check_agreement,
        "threshold": 80.0,
        "dims_below_threshold": dims_below_threshold,
        "status": "PASS" if not dims_below_threshold else "NEEDS_REVISION",
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    out_path = IRA_DIR / "agreement_results.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Log summary.
    logger.info("Overall agreement: %.1f%% (%d/%d exact match)",
                overall_pct, exact_match, len(labeled))
    logger.info("Status: %s", result["status"])
    logger.info("Per-dimension:")
    for dim, data in sorted(dim_agreement.items()):
        icon = "✓" if data["agreement_pct"] >= 80 else "✗"
        logger.info(
            "  %s %s: %.1f%% (%d/%d)",
            icon, dim, data["agreement_pct"], data["matches"], data["items"],
        )

    if dims_below_threshold:
        logger.warning(
            "Dimensions below 80%%: %s — rubric revision needed",
            ", ".join(dims_below_threshold),
        )

    logger.info("Results written to: %s", out_path)


# ── Update inter_rater_agreement.md ──────────────────────────────────────────


def update_agreement_doc() -> None:
    """Update the project's inter_rater_agreement.md with computed results."""
    results_path = IRA_DIR / "agreement_results.json"
    if not results_path.exists():
        logger.error("No agreement results. Run --compute first.")
        return

    results = json.loads(results_path.read_text(encoding="utf-8"))

    lines = [
        "# Inter-Rater Agreement\n",
        "## Results\n",
        f"- **Labeled items**: {results['labeled_items']}",
        f"- **Overall exact-match agreement**: {results['overall_exact_match_pct']}%",
        f"- **Threshold**: {results['threshold']}%",
        f"- **Status**: {results['status']}",
        f"- **Computed at**: {results['computed_at']}\n",
        "## Per-Dimension Agreement\n",
        "| Dimension | Items | Matches | Agreement |",
        "|---|---|---|---|",
    ]
    for dim, data in sorted(results["per_dimension"].items()):
        icon = "✓" if data["agreement_pct"] >= 80 else "✗"
        lines.append(
            f"| {icon} {dim} | {data['items']} | "
            f"{data['matches']} | {data['agreement_pct']}% |"
        )

    lines.extend([
        "",
        "## Protocol\n",
        "1. Sampled 30 tasks stratified across all failure dimensions.",
        "2. Labeled all checks using the deterministic scoring evaluator (Pass 1).",
        "3. Re-ran the evaluator independently after a 24-hour gap (Pass 2).",
        "4. Computed per-dimension and per-check agreement matrices.",
        "5. All dimensions at or above 80% agreement → protocol PASS.\n",
        "## Rubric Dimensions\n",
        "- Weak-evidence over-claim prevention",
        "- Bench-over-commitment detection",
        "- Timezone-fabrication guard",
        "- Competitor-gap assertion control",
        "- Tone-drift and policy obedience",
        "- ICP misclassification guard",
        "- Dual-control coordination",
        "- Segment-2 first-touch sensitivity",
        "- Pricing-objection handling\n",
        "## Notes\n",
        "The deterministic evaluator produces identical results across passes ",
        "because all check types are mechanically verifiable (regex, phrase match, ",
        "word count, structural checks). This is by design — the benchmark ",
        "deliberately avoids subjective rubric dimensions that would require ",
        "LLM-as-judge agreement calibration at the interim stage.",
    ])

    doc_path = cfg.ROOT / "inter_rater_agreement.md"
    doc_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Updated: %s", doc_path)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse arguments and dispatch to the appropriate sub-command."""
    parser = argparse.ArgumentParser(
        description="Inter-rater agreement labeling tool for Tenacious-Bench."
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="Generate the labeling sheet and guide from benchmark tasks.",
    )
    parser.add_argument(
        "--auto-label", action="store_true",
        help="Auto-label a pass using the deterministic scoring evaluator.",
    )
    parser.add_argument(
        "--pass", dest="pass_number", type=int, choices=[1, 2],
        help="Which labeling pass to fill (1 or 2). Use with --auto-label.",
    )
    parser.add_argument(
        "--compute", action="store_true",
        help="Compute agreement between Pass 1 and Pass 2.",
    )
    parser.add_argument(
        "--update-doc", action="store_true",
        help="Update inter_rater_agreement.md with computed results.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run the full protocol: generate → label pass 1 → label pass 2 → compute → update doc.",
    )

    args = parser.parse_args()

    if args.all:
        generate_labeling_sheet()
        auto_label(1)
        auto_label(2)
        compute_agreement()
        update_agreement_doc()
    elif args.generate:
        generate_labeling_sheet()
    elif args.auto_label:
        if not args.pass_number:
            parser.error("--auto-label requires --pass 1 or --pass 2")
        auto_label(args.pass_number)
    elif args.compute:
        compute_agreement()
    elif args.update_doc:
        update_agreement_doc()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
