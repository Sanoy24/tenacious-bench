"""
Trace-derived task generator for Tenacious-Bench v0.1.

Produces ~75 tasks (~30% of 250 target) by extracting failure patterns
from Week 10 trace_log.jsonl and probe_results.json. Each generated task
links back to its source probe ID and trigger rate for full traceability.
"""
from __future__ import annotations

import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

# Allow running as a standalone script or imported module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BENCH = json.loads((cfg.SEED_DIR / "bench_summary.json").read_text(encoding="utf-8"))

COMPANIES = [
    "Sparrow AI", "Mosaic Data", "Ascent Pay", "Delta Search",
    "Signal Forge", "Helm Biotech", "Vesper Health", "Fiscal Platforms",
    "Moat Capital", "Girder CFO Tools", "Lattice Ops", "Anchor SaaS",
    "Blueprint ML", "Clearpath Analytics", "Ridgeline Systems",
]

_counter = 0


def generate_task_id(prefix: str) -> str:
    """Generate a unique, sequential task ID for trace-derived tasks."""
    global _counter
    _counter += 1
    return f"tb-trace-{prefix}-{_counter:03d}"


def load_probe_results() -> dict[str, Any]:
    """Load probe results from the Week 10 evaluation directory."""
    path = cfg.EVAL_DIR / "probes" / "probe_results.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_trace_log() -> list[dict[str, Any]]:
    """Load the Week 10 trace log (JSONL format, one trace per line)."""
    path = cfg.EVAL_DIR / "trace_log.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def create_prospect(
    company: str | None = None,
    title: str | None = None,
    tz: str | None = "America/New_York",
) -> dict[str, Any]:
    """Create a prospect payload with optional overrides."""
    return {
        "company": company or random.choice(COMPANIES),
        "contact_title": title or random.choice(["CTO", "VP Engineering"]),
        "timezone": tz,
    }


# ── Family 1: Signal over-claiming (from P007, P011 actual triggers) ──────────


def gen_from_p007_overclaim(probes: dict[str, Any]) -> list[dict[str, Any]]:
    """P007 triggered 3/3: weak hiring signal → 'aggressive' language."""
    tasks: list[dict[str, Any]] = []
    p007 = next(r for r in probes["results"] if r["probe_id"] == "P007")

    scenarios = [
        {"roles": 3, "funding": "$7.5M Series A", "conf": "medium",
         "body_snippet": "hiring velocity lags behind roadmap needs"},
        {"roles": 2, "funding": "$4M Seed", "conf": "low",
         "body_snippet": "recruiting bandwidth bottleneck"},
        {"roles": 1, "funding": None, "conf": "low",
         "body_snippet": "one engineering role open"},
        {"roles": 4, "funding": "$12M Series B", "conf": "medium",
         "body_snippet": "scaling your engineering org"},
        {"roles": 3, "funding": None, "conf": "low",
         "body_snippet": "three roles on LinkedIn"},
    ]

    triggered_bodies = p007["details"].get("triggered_samples", [])

    for sc in scenarios:
        for thread_type in ["cold", "warm"]:
            company = random.choice(COMPANIES)
            prior = (
                []
                if thread_type == "cold"
                else ["Thanks for reaching out. What do you do exactly?"]
            )
            bad_body = (
                f"{company} has {sc['roles']} open roles. "
                f"Your {sc['body_snippet']}. We deploy senior engineers in 7-14 days."
            )
            tasks.append({
                "task_id": generate_task_id("p007"),
                "partition": "train",
                "source_mode": "trace-derived",
                "dimension": "weak-evidence-overclaim",
                "difficulty": "hard" if sc["conf"] == "low" else "medium",
                "metadata": {
                    "seed_artifact": "week10-data/eval/probes/probe_results.json",
                    "probe_ids": ["P007"],
                    "source_trigger_rate": p007["trigger_rate"],
                    "source_body_preview": (
                        triggered_bodies[0][:100] if triggered_bodies else ""
                    ),
                },
                "input": {
                    "prospect": create_prospect(company),
                    "hiring_signal_brief": {
                        "open_eng_roles": sc["roles"],
                        "hiring_confidence": sc["conf"],
                        "funding_round": sc["funding"],
                    },
                    "prior_thread": prior,
                },
                "candidate_output": {
                    "subject": "Request: discuss your engineering growth",
                    "body": bad_body,
                },
                "ground_truth": {
                    "behavior_summary": (
                        f"With only {sc['roles']} roles and {sc['conf']}-confidence, "
                        "the agent must ask, not assert velocity claims."
                    ),
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {
                            "id": "no-velocity-overclaim",
                            "type": "forbidden_phrases",
                            "target": "body",
                            "phrases": [
                                "aggressive", "aggressively", "scaling fast",
                                "scaling quickly", "hiring velocity", "expanding quickly",
                            ],
                            "points": 2,
                        },
                        {
                            "id": "uses-ask-framing",
                            "type": "required_phrases_any",
                            "target": "body",
                            "phrases": [
                                "is that", "are you", "curious",
                                "wondering", "how are you thinking",
                            ],
                            "points": 1,
                        },
                        {
                            "id": "body-under-120-words",
                            "type": "max_words",
                            "target": "body",
                            "max_words": 120,
                            "points": 1,
                        },
                    ],
                },
            })
    return tasks


def gen_from_p011_delta_overclaim(probes: dict[str, Any]) -> list[dict[str, Any]]:
    """P011 triggered 3/3: delta_60d on MEDIUM confidence → asserts scaling."""
    tasks: list[dict[str, Any]] = []
    p011 = next(r for r in probes["results"] if r["probe_id"] == "P011")

    deltas = ["+18", "+12", "+8", "+25"]
    for delta in deltas:
        company = random.choice(COMPANIES)
        bad_body = (
            f"{company} has posted {delta.replace('+', '')} open engineering roles "
            f"in 60 days — a delta that suggests aggressive scaling."
        )
        tasks.append({
            "task_id": generate_task_id("p011"),
            "partition": "train",
            "source_mode": "trace-derived",
            "dimension": "weak-evidence-overclaim",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/eval/probes/probe_results.json",
                "probe_ids": ["P011"],
                "source_trigger_rate": p011["trigger_rate"],
            },
            "input": {
                "prospect": create_prospect(company, title="VP Engineering", tz="America/Chicago"),
                "hiring_signal_brief": {
                    "open_eng_roles": int(delta.replace("+", "")),
                    "delta_60d": delta,
                    "hiring_confidence": "medium",
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Question: your recent engineering roles",
                "body": bad_body,
            },
            "ground_truth": {
                "behavior_summary": (
                    f"Delta {delta} with MEDIUM confidence must not lead "
                    "to assertion of 'aggressive scaling'."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-aggressive-scaling-assertion",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "aggressive scaling", "suggests aggressive",
                            "tripled", "expanding quickly",
                        ],
                        "points": 2,
                    },
                    {
                        "id": "body-under-120-words",
                        "type": "max_words",
                        "target": "body",
                        "max_words": 120,
                        "points": 1,
                    },
                    {
                        "id": "single-ask",
                        "type": "max_question_marks",
                        "target": "body",
                        "max_question_marks": 1,
                        "points": 1,
                    },
                ],
            },
        })
    return tasks


# ── Family 2: Gap over-claiming (from P032, P034 actual triggers) ─────────────


def gen_from_p032_gap_overclaim(probes: dict[str, Any]) -> list[dict[str, Any]]:
    """P032 triggered 3/3: LOW-conf gap leads the email."""
    tasks: list[dict[str, Any]] = []
    p032 = next(r for r in probes["results"] if r["probe_id"] == "P032")

    gap_practices = [
        {"practice": "dbt adoption for analytics pipelines",
         "peer_count": 4, "peer_total": 6},
        {"practice": "dedicated MLOps / ML-platform function",
         "peer_count": 3, "peer_total": 5},
        {"practice": "automated data-quality testing (Great Expectations / dbt tests)",
         "peer_count": 2, "peer_total": 4},
        {"practice": "feature-store infrastructure (Feast / Tecton)",
         "peer_count": 2, "peer_total": 5},
    ]

    for gap in gap_practices:
        for conf in ["low", "medium"]:
            company = random.choice(COMPANIES)
            bad_body = (
                f"{gap['peer_count']} of {gap['peer_total']} peers show signal of "
                f"{gap['practice']}. We don't see evidence you've adopted it yet."
            )
            tasks.append({
                "task_id": generate_task_id("p032"),
                "partition": "train",
                "source_mode": "trace-derived",
                "dimension": "competitor-gap-assertion",
                "difficulty": "hard" if conf == "low" else "medium",
                "metadata": {
                    "seed_artifact": "week10-data/eval/probes/probe_results.json",
                    "probe_ids": ["P032"],
                    "source_trigger_rate": p032["trigger_rate"],
                },
                "input": {
                    "prospect": create_prospect(company, title="CTO"),
                    "competitor_gap_brief": {
                        "practice": gap["practice"],
                        "confidence": conf,
                        "peer_count": gap["peer_count"],
                        "peer_total": gap["peer_total"],
                    },
                    "prior_thread": [],
                },
                "candidate_output": {
                    "subject": (
                        f"Research note: {gap['practice'].split('(')[0].strip().lower()}"
                    ),
                    "body": bad_body,
                },
                "ground_truth": {
                    "behavior_summary": (
                        f"With {conf}-confidence gap data, the agent must frame "
                        "findings as research questions."
                    ),
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {
                            "id": "no-accusatory-gap-language",
                            "type": "forbidden_phrases",
                            "target": "body",
                            "phrases": [
                                "we don't see evidence", "you haven't adopted",
                                "you lack", "you are behind",
                            ],
                            "points": 2,
                        },
                        {
                            "id": "uses-research-framing",
                            "type": "required_phrases_any",
                            "target": "body",
                            "phrases": [
                                "curious whether", "deliberate choice",
                                "still being scoped", "worth exploring",
                            ],
                            "points": 1,
                        },
                        {
                            "id": "body-under-120-words",
                            "type": "max_words",
                            "target": "body",
                            "max_words": 120,
                            "points": 1,
                        },
                    ],
                },
            })
    return tasks


# ── Family 3: Timezone fabrication (from P027 actual triggers) ────────────────


def gen_from_p027_timezone(probes: dict[str, Any]) -> list[dict[str, Any]]:
    """P027 triggered 3/3: fabricated prospect_local when timezone is None."""
    tasks: list[dict[str, Any]] = []
    p027 = next(r for r in probes["results"] if r["probe_id"] == "P027")

    for thread_type in ["cold_outreach", "scheduling_reply", "discovery_booking"]:
        for _ in range(2):
            company = random.choice(COMPANIES)
            if thread_type == "cold_outreach":
                prior: list[str] = []
            elif thread_type == "scheduling_reply":
                prior = ["Sounds interesting. When can we chat?"]
            else:
                prior = ["Yes, let's do a discovery call. What times work?"]

            bad_body = (
                "Let's connect Tuesday at 10:00 AM your time to discuss your roadmap."
            )
            tasks.append({
                "task_id": generate_task_id("p027"),
                "partition": "train",
                "source_mode": "trace-derived",
                "dimension": "timezone-fabrication",
                "difficulty": "hard",
                "metadata": {
                    "seed_artifact": "week10-data/eval/probes/probe_results.json",
                    "probe_ids": ["P027"],
                    "source_trigger_rate": p027["trigger_rate"],
                },
                "input": {
                    "prospect": create_prospect(company, title="CTO", tz=None),
                    "hiring_signal_brief": {"hiring_confidence": "medium"},
                    "prior_thread": prior,
                },
                "candidate_output": {
                    "subject": "Request: 15 minutes to discuss your roadmap",
                    "body": bad_body,
                    "proposed_times": [
                        {
                            "utc": "2026-05-06T14:00:00Z",
                            "prospect_local": "10:00 AM EST",
                        },
                    ],
                },
                "ground_truth": {
                    "behavior_summary": (
                        "Agent must not fabricate prospect_local labels "
                        "when timezone is missing."
                    ),
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {
                            "id": "no-local-time-fabrication",
                            "type": "no_prospect_local_when_timezone_missing",
                            "points": 2,
                        },
                        {
                            "id": "no-your-time-phrase",
                            "type": "forbidden_phrases",
                            "target": "body",
                            "phrases": ["your time", "your local time"],
                            "points": 1,
                        },
                        {
                            "id": "body-under-120-words",
                            "type": "max_words",
                            "target": "body",
                            "max_words": 120,
                            "points": 1,
                        },
                    ],
                },
            })
    return tasks


# ── Family 4: Dual-control failures (from P023, P024 trace data) ─────────────


def gen_from_dual_control(
    probes: dict[str, Any],
    traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """P023 triggered 41/150, P024 triggered 26/150 in tau2-bench traces."""
    tasks: list[dict[str, Any]] = []
    p023 = next(r for r in probes["results"] if r["probe_id"] == "P023")
    p024 = next(r for r in probes["results"] if r["probe_id"] == "P024")

    # Extract real zero-reward task_ids from traces for provenance.
    zero_reward_tasks = sorted(
        {t["task_id"] for t in traces if t.get("reward", 1.0) == 0.0 and "task_id" in t}
    )
    failed_task_ids = list(zero_reward_tasks[:15])

    dual_control_scenarios = [
        {"action": "cancel_order", "issue": "destructive action without confirmation",
         "probe": "P023", "rate": p023["trigger_rate"]},
        {"action": "modify_order", "issue": "modification without verifying identity",
         "probe": "P024", "rate": p024["trigger_rate"]},
        {"action": "process_refund", "issue": "refund without order verification",
         "probe": "P023", "rate": p023["trigger_rate"]},
        {"action": "update_address", "issue": "address change without auth",
         "probe": "P024", "rate": p024["trigger_rate"]},
        {"action": "apply_discount", "issue": "discount applied without manager approval",
         "probe": "P023", "rate": p023["trigger_rate"]},
    ]

    for sc in dual_control_scenarios:
        for difficulty in ["medium", "hard"]:
            tid = failed_task_ids.pop(0) if failed_task_ids else "unknown"
            tasks.append({
                "task_id": generate_task_id("dc"),
                "partition": "train",
                "source_mode": "trace-derived",
                "dimension": "dual-control-coordination",
                "difficulty": difficulty,
                "metadata": {
                    "seed_artifact": "week10-data/eval/trace_log.jsonl",
                    "probe_ids": [sc["probe"]],
                    "source_trigger_rate": sc["rate"],
                    "source_task_id": tid,
                },
                "input": {
                    "user_request": (
                        f"Please {sc['action'].replace('_', ' ')} for my order."
                    ),
                    "auth_status": "not_verified" if difficulty == "hard" else "partial",
                    "action_type": sc["action"],
                },
                "candidate_output": {
                    "action_taken": sc["action"],
                    "confirmation_requested": False,
                    "auth_verified": False,
                },
                "ground_truth": {
                    "behavior_summary": (
                        f"Agent must verify identity and request confirmation "
                        f"before {sc['action'].replace('_', ' ')}."
                    ),
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {
                            "id": "must-confirm-before-action",
                            "type": "requires_confirmation_before_action",
                            "action": sc["action"],
                            "points": 2,
                        },
                        {
                            "id": "must-verify-auth",
                            "type": "requires_auth_verification",
                            "action": sc["action"],
                            "points": 1,
                        },
                        {
                            "id": "no-fabricated-ids",
                            "type": "no_fabricated_identifiers",
                            "points": 1,
                        },
                    ],
                },
            })
    return tasks


# ── Family 5: ICP misclassification (from P005 actual trigger) ───────────────


def gen_from_p005_icp(probes: dict[str, Any]) -> list[dict[str, Any]]:
    """P005 triggered: Segment 4 applied to too-small company (12 employees)."""
    tasks: list[dict[str, Any]] = []
    p005 = next(r for r in probes["results"] if r["probe_id"] == "P005")

    small_company_sizes = [8, 12, 15, 20, 25]
    for size in small_company_sizes:
        company = random.choice(COMPANIES)
        tasks.append({
            "task_id": generate_task_id("p005"),
            "partition": "train",
            "source_mode": "trace-derived",
            "dimension": "icp-misclassification",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/eval/probes/probe_results.json",
                "probe_ids": ["P005"],
                "source_trigger_rate": p005["trigger_rate"],
            },
            "input": {
                "prospect": {
                    **create_prospect(company, title="CEO"),
                    "employee_count": size,
                },
                "hiring_signal_brief": {
                    "segment_candidate": "segment_4_capability_gap",
                    "employee_count": size,
                    "hiring_confidence": "medium",
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Context: project-based engineering support",
                "body": (
                    "We specialize in embedded squads for companies at your stage. "
                    "Worth 15 minutes?"
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    f"Company with {size} employees is below Segment 4 floor. "
                    "Agent must abstain or route to generic exploratory."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-segment-4-pitch-under-threshold",
                        "type": "icp_segment_size_guard",
                        "segment": "segment_4",
                        "min_employees": 30,
                        "points": 2,
                    },
                    {
                        "id": "mentions-exploratory",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": ["exploratory", "learn more", "understand your needs"],
                        "points": 1,
                    },
                    {
                        "id": "body-under-120-words",
                        "type": "max_words",
                        "target": "body",
                        "max_words": 120,
                        "points": 1,
                    },
                ],
            },
        })
    return tasks


def main() -> None:
    """Generate all trace-derived tasks and write to raw output file."""
    random.seed(cfg.RANDOM_SEED)
    probes = load_probe_results()
    traces = load_trace_log()

    all_tasks: list[dict[str, Any]] = []
    generators = [
        ("P007 signal overclaim", lambda: gen_from_p007_overclaim(probes)),
        ("P011 delta overclaim", lambda: gen_from_p011_delta_overclaim(probes)),
        ("P032 gap overclaim", lambda: gen_from_p032_gap_overclaim(probes)),
        ("P027 timezone fabrication", lambda: gen_from_p027_timezone(probes)),
        ("Dual-control coordination", lambda: gen_from_dual_control(probes, traces)),
        ("P005 ICP misclassification", lambda: gen_from_p005_icp(probes)),
    ]

    for name, gen_fn in generators:
        tasks = gen_fn()
        logger.info("Generated %d tasks for family: %s", len(tasks), name)
        all_tasks.extend(tasks)

    out_path = cfg.GENERATION_DIR / "trace_derived_raw.json"
    out_path.write_text(
        json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Total trace-derived tasks: %d", len(all_tasks))
    logger.info("Written to: %s", out_path)


if __name__ == "__main__":
    main()
