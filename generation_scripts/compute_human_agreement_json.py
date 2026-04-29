"""
Compute inter-rater agreement from JSON-format Pass 1 / Pass 2 label files.

Reads:
  - inter_rater/human_pass1_labels.json
  - inter_rater/human_pass2_labels.json
  - inter_rater/labeling_sheet.json  (for task → dimension mapping)

Writes:
  - inter_rater/human_agreement_results.json (overall + per-dimension matrix
    + Cohen's κ + disagreement records)

A check is counted as agreeing if both passes mark it the same (both true or
both false). Pass-level agreement and per-dimension agreement are reported.

Usage:
    uv run python generation_scripts/compute_human_agreement_json.py
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def cohens_kappa(matches: int, total: int, p1_pos: int, p2_pos: int) -> float:
    if total == 0:
        return 0.0
    po = matches / total
    p1 = p1_pos / total
    p2 = p2_pos / total
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    if pe >= 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 4)


def main() -> None:
    ir = cfg.ROOT / "inter_rater"
    pass1 = json.loads((ir / "human_pass1_labels.json").read_text(encoding="utf-8"))["labels"]
    pass2 = json.loads((ir / "human_pass2_labels.json").read_text(encoding="utf-8"))["labels"]
    sheet = json.loads((ir / "labeling_sheet.json").read_text(encoding="utf-8"))
    dims = {it["task_id"]: it["dimension"] for it in sheet}

    overall_matches = overall_total = p1_pos_total = p2_pos_total = 0
    per_dim: dict[str, dict[str, int]] = defaultdict(
        lambda: {"matches": 0, "total": 0, "p1_pos": 0, "p2_pos": 0}
    )
    disagreements: list[dict[str, Any]] = []

    for tid, p1_checks in pass1.items():
        if tid not in pass2:
            logger.warning("Task %s missing from pass2", tid)
            continue
        p2_checks = pass2[tid]
        dim = dims.get(tid, "unknown")
        for cid, v1 in p1_checks.items():
            if cid not in p2_checks:
                logger.warning("Check %s on %s missing from pass2", cid, tid)
                continue
            v2 = p2_checks[cid]
            overall_total += 1
            per_dim[dim]["total"] += 1
            if v1: p1_pos_total += 1; per_dim[dim]["p1_pos"] += 1
            if v2: p2_pos_total += 1; per_dim[dim]["p2_pos"] += 1
            if v1 == v2:
                overall_matches += 1
                per_dim[dim]["matches"] += 1
            else:
                disagreements.append(
                    {"task_id": tid, "check_id": cid, "dimension": dim, "pass1": v1, "pass2": v2}
                )

    overall_agreement = overall_matches / overall_total if overall_total else 0.0
    overall_kappa = cohens_kappa(overall_matches, overall_total, p1_pos_total, p2_pos_total)

    per_dim_out = {}
    for dim, s in per_dim.items():
        agree = s["matches"] / s["total"] if s["total"] else 0.0
        per_dim_out[dim] = {
            "items": s["total"],
            "matches": s["matches"],
            "agreement": round(agree, 4),
            "kappa": cohens_kappa(s["matches"], s["total"], s["p1_pos"], s["p2_pos"]),
            "passes_threshold": agree >= 0.80,
        }

    result = {
        "tasks_evaluated": len(pass1),
        "total_check_decisions": overall_total,
        "overall_agreement": round(overall_agreement, 4),
        "overall_kappa": overall_kappa,
        "threshold": 0.80,
        "status": (
            "PASS"
            if all(d["passes_threshold"] for d in per_dim_out.values()) and overall_total > 0
            else "FAIL"
        ),
        "per_dimension": per_dim_out,
        "disagreements": disagreements,
    }

    out = ir / "human_agreement_results.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(
        "Status: %s | Overall: %.1f%% | kappa=%s | %d/%d agreed | %d disagreements",
        result["status"],
        overall_agreement * 100,
        overall_kappa,
        overall_matches,
        overall_total,
        len(disagreements),
    )
    for dim, s in per_dim_out.items():
        flag = "OK " if s["passes_threshold"] else "LOW"
        logger.info("  %s  %-30s  %2d/%2d = %.1f%%  kappa=%s",
                    flag, dim, s["matches"], s["items"], s["agreement"] * 100, s["kappa"])


if __name__ == "__main__":
    main()
