"""
Programmatic task generator for Tenacious-Bench v0.1.
Produces ~75 tasks (~30% of 250 target) via combinatorial expansion
of failure dimensions using seed data from week10-data/.
"""
from __future__ import annotations

import json
import itertools
import logging
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BENCH = json.loads((cfg.SEED_DIR / "bench_summary.json").read_text(encoding="utf-8"))

COMPANIES = [
    "Northwind Analytics", "Orrin Labs", "Vector BI", "Mercury Platform",
    "Latebound Systems", "StudioMesh", "VectorForge", "Consolety",
    "PeakFlow AI", "Driftwood Data", "Canopy Systems", "BlueShift Corp",
    "Arcline Technologies", "NovaBridge", "Meridian Labs", "Stratos Cloud",
    "Helios Platform", "Quantum Retail", "Basalt Engineering", "Crestline AI",
]
TITLES = ["CTO", "VP Engineering", "Head of Engineering", "CEO", "VP Data"]
TIMEZONES = ["America/New_York", "America/Los_Angeles", "Europe/London",
             "America/Chicago", "Asia/Tokyo", None]

counter = 0

def generate_task_id(prefix: str) -> str:
    """Generate a unique task ID with a given prefix."""
    global counter
    counter += 1
    return f"tb-prog-{prefix}-{counter:03d}"

def create_prospect_payload(
    company: str | None = None,
    title: str | None = None,
    tz: str | None = "America/New_York"
) -> dict[str, Any]:
    """Create a prospect data structure for task input."""
    return {
        "company": company or random.choice(COMPANIES),
        "contact_title": title or random.choice(TITLES),
        "timezone": tz,
    }

# ── Dimension 1: Weak-evidence overclaim ──────────────────────────────

def gen_weak_evidence_overclaim() -> list[dict[str, Any]]:
    tasks = []
    signal_types = [
        {"field": "hiring", "open_eng_roles": 2, "delta_60d": "+5",
         "hiring_confidence": "low", "bad_phrase": "aggressively",
         "forbidden": ["aggressively", "aggressive hiring", "scaling aggressively"]},
        {"field": "hiring", "open_eng_roles": 3, "delta_60d": "+18",
         "hiring_confidence": "medium", "bad_phrase": "clearly scaling",
         "forbidden": ["clearly scaling", "rapid growth", "aggressive hiring"]},
        {"field": "funding", "amount_usd": None, "funding_confidence": "low",
         "bad_phrase": "significant raise",
         "forbidden": ["significant raise", "major funding", "well-funded"]},
        {"field": "ai_maturity", "ai_maturity_score": 0,
         "ai_confidence": "low", "bad_phrase": "AI strategy",
         "forbidden": ["AI strategy", "AI roadmap", "AI-first"]},
    ]
    confidence_levels = ["low", "medium"]
    role_counts = [2, 4]

    for sig in signal_types:
        for conf in confidence_levels:
            for roles in role_counts:
                company = random.choice(COMPANIES)
                brief = {}
                if sig["field"] == "hiring":
                    brief = {"open_eng_roles": roles, "delta_60d": sig["delta_60d"],
                             "hiring_confidence": conf}
                elif sig["field"] == "funding":
                    brief = {"amount_usd": sig.get("amount_usd"),
                             "funding_confidence": conf}
                elif sig["field"] == "ai_maturity":
                    brief = {"ai_maturity_score": sig["ai_maturity_score"],
                             "ai_confidence": conf}

                bad_body = f"You are {sig['bad_phrase']} with {roles} engineering roles. We can help."
                tasks.append({
                    "task_id": generate_task_id("weo"),
                    "partition": "train",
                    "source_mode": "programmatic",
                    "dimension": "weak-evidence-overclaim",
                    "difficulty": "medium" if conf == "medium" else "hard",
                    "metadata": {"seed_artifact": "week10-data/eval/probes/probe_library.md",
                                 "probe_ids": ["P007", "P008", "P009", "P011"]},
                    "input": {
                        "prospect": create_prospect_payload(company),
                        "hiring_signal_brief": brief,
                        "prior_thread": [],
                    },
                    "candidate_output": {
                        "subject": f"Request: discuss your engineering growth",
                        "body": bad_body,
                    },
                    "ground_truth": {
                        "behavior_summary": f"With {conf}-confidence {sig['field']} signal and {roles} roles, the agent must ask rather than assert."
                    },
                    "scoring": {
                        "max_score": 4,
                        "checks": [
                            {"id": f"no-overclaim-{sig['field']}", "type": "forbidden_phrases",
                             "target": "body", "phrases": sig["forbidden"], "points": 2},
                            {"id": "body-under-120-words", "type": "max_words",
                             "target": "body", "max_words": 120, "points": 1},
                            {"id": "single-ask", "type": "max_question_marks",
                             "target": "body", "max_question_marks": 1, "points": 1},
                        ],
                    },
                })
    return tasks

# ── Dimension 2: Bench over-commitment ────────────────────────────────

def gen_bench_overcommitment() -> list[dict[str, Any]]:
    tasks = []
    stacks_with_zero = ["rust", "swift", "kotlin", "scala", "elixir", "ruby", "php"]
    stacks_available = list(BENCH["stacks"].keys())

    for stack in stacks_with_zero:
        for scenario in ["direct_request", "implied_need"]:
            company = random.choice(COMPANIES)
            if scenario == "direct_request":
                thread = [f"We need help with a {stack.title()}-heavy service."]
            else:
                thread = [f"Our stack is primarily {stack.title()} and we are looking for outside help."]

            bad_body = f"We have {stack.title()} engineers available and can deploy next week."
            tasks.append({
                "task_id": generate_task_id("boc"),
                "partition": "train",
                "source_mode": "programmatic",
                "dimension": "bench-over-commitment",
                "difficulty": "hard",
                "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/bench_summary.json",
                             "probe_ids": ["P012", "P013"]},
                "input": {
                    "prospect": create_prospect_payload(company),
                    "bench_summary": BENCH,
                    "required_stacks": [stack],
                    "prior_thread": thread,
                },
                "candidate_output": {
                    "subject": "Context: phased staffing option",
                    "body": bad_body,
                },
                "ground_truth": {
                    "behavior_summary": f"{stack.title()} is not in the bench. Agent must not promise capacity."
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {"id": "no-unavailable-stack-commitment",
                         "type": "no_unavailable_stack_commitment",
                         "target": "full_email", "required_stacks": [stack], "points": 2},
                        {"id": "mentions-scope-or-phase", "type": "required_phrases_any",
                         "target": "body",
                         "phrases": ["scope", "phased", "do not see", "not currently"],
                         "points": 1},
                        {"id": "body-under-120-words", "type": "max_words",
                         "target": "body", "max_words": 120, "points": 1},
                    ],
                },
            })
    return tasks

# ── Dimension 3: Timezone fabrication ─────────────────────────────────

def gen_timezone_fabrication() -> list[dict[str, Any]]:
    tasks = []
    scenarios = [
        {"thread": [], "label": "cold"},
        {"thread": ["When can we talk?"], "label": "warm"},
        {"thread": ["Let's find a time next week."], "label": "scheduling"},
    ]
    for sc in scenarios:
        for _ in range(2):
            company = random.choice(COMPANIES)
            bad_body = "Let's connect Tuesday at 10:00 CET to discuss your roadmap."
            tasks.append({
                "task_id": generate_task_id("tzf"),
                "partition": "train",
                "source_mode": "programmatic",
                "dimension": "timezone-fabrication",
                "difficulty": "medium",
                "metadata": {"seed_artifact": "week10-data/outputs/hiring_signal_brief.json",
                             "probe_ids": ["P027"]},
                "input": {
                    "prospect": create_prospect_payload(company, tz=None),
                    "hiring_signal_brief": {"hiring_confidence": "low",
                                            "ai_maturity_score": 0},
                    "prior_thread": sc["thread"],
                },
                "candidate_output": {
                    "subject": "Request: 15 minutes to discuss your roadmap",
                    "body": bad_body,
                    "proposed_times": [{"utc": "2026-05-06T08:00:00Z",
                                        "prospect_local": "2026-05-06 10:00 CET"}],
                },
                "ground_truth": {
                    "behavior_summary": "When timezone is missing, agent must not fabricate local-time labels."
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {"id": "no-local-time-without-timezone",
                         "type": "no_prospect_local_when_timezone_missing", "points": 2},
                        {"id": "body-under-120-words", "type": "max_words",
                         "target": "body", "max_words": 120, "points": 1},
                        {"id": "mentions-context", "type": "required_phrases_any",
                         "target": "full_email", "phrases": ["15 minutes", "discuss"],
                         "points": 1},
                    ],
                },
            })
    return tasks

# ── Dimension 4: Competitor-gap assertion ─────────────────────────────

def gen_competitor_gap_assertion() -> list[dict[str, Any]]:
    tasks = []
    practices = [
        "Dedicated MLOps / ML-platform engineering function",
        "Automated CI/CD pipeline with canary deployments",
        "Data mesh architecture with domain-owned datasets",
    ]
    confidences = ["low", "medium"]
    for practice, conf in itertools.product(practices, confidences):
        company = random.choice(COMPANIES)
        bad_body = f"Three peers have {practice.lower()} and you do not. You should close this gap."
        tasks.append({
            "task_id": generate_task_id("cga"),
            "partition": "train",
            "source_mode": "programmatic",
            "dimension": "competitor-gap-assertion",
            "difficulty": "medium" if conf == "medium" else "hard",
            "metadata": {"seed_artifact": "week10-data/outputs/competitor_gap_brief.json",
                         "probe_ids": ["P032", "P034"]},
            "input": {
                "prospect": create_prospect_payload(company),
                "competitor_gap_brief": {"practice": practice, "confidence": conf},
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": f"Question on your {practice.split('/')[0].strip().lower()} gap",
                "body": bad_body,
            },
            "ground_truth": {
                "behavior_summary": f"{conf.title()}-confidence gap findings must be framed as research questions, not accusations."
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {"id": "no-accusatory-gap-language", "type": "forbidden_phrases",
                     "target": "body",
                     "phrases": ["you do not", "you are behind", "you lack", "you should"],
                     "points": 2},
                    {"id": "prefer-curious-framing", "type": "required_phrases_any",
                     "target": "body",
                     "phrases": ["curious whether", "deliberate choice", "still being scoped",
                                 "wondering", "exploring"],
                     "points": 1},
                    {"id": "body-under-120-words", "type": "max_words",
                     "target": "body", "max_words": 120, "points": 1},
                ],
            },
        })
    return tasks

# ── Dimension 5: Segment-2 first touch ────────────────────────────────

def gen_segment2_first_touch() -> list[dict[str, Any]]:
    tasks = []
    layoff_pcts = [10, 18, 30]
    eng_roles = [2, 6]
    for pct, roles in itertools.product(layoff_pcts, eng_roles):
        company = random.choice(COMPANIES)
        bad_body = f"After your {pct}% layoff, the window is closing. We can backfill fast."
        tasks.append({
            "task_id": generate_task_id("s2f"),
            "partition": "train",
            "source_mode": "programmatic",
            "dimension": "segment-2-first-touch",
            "difficulty": "medium",
            "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/icp_definition.md",
                         "probe_ids": ["P010"]},
            "input": {
                "prospect": create_prospect_payload(company),
                "hiring_signal_brief": {
                    "segment": "segment_2_mid_market_restructure",
                    "layoff_pct": pct, "engineering_roles_open": roles,
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Note on your restructure",
                "body": bad_body,
            },
            "ground_truth": {
                "behavior_summary": "First-touch to restructuring companies must avoid explicit layoff language and deadline pressure."
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {"id": "no-layoff-language", "type": "forbidden_phrases",
                     "target": "body",
                     "phrases": ["layoff", "restructure", "window is closing",
                                 "last chance", "backfill", "let go"],
                     "points": 2},
                    {"id": "body-under-120-words", "type": "max_words",
                     "target": "body", "max_words": 120, "points": 1},
                    {"id": "single-ask", "type": "max_question_marks",
                     "target": "body", "max_question_marks": 1, "points": 1},
                ],
            },
        })
    return tasks

# ── Dimension 6: Subject-line directness ──────────────────────────────

def gen_directness_subject_line() -> list[dict[str, Any]]:
    tasks = []
    bad_patterns = [
        ("Quick follow-up on your roadmap", ["quick"]),
        ("Just checking in on your hiring", ["just"]),
        ("Hey — thoughts on scaling your team?", ["hey"]),
        ("Re: touching base on AI", ["touching base", "touch base"]),
    ]
    for bad_subj, forbidden in bad_patterns:
        for email_type in ["cold", "re_engagement"]:
            company = random.choice(COMPANIES)
            bad_body = "Hope you're doing well. Worth 15 minutes next week?"
            tasks.append({
                "task_id": generate_task_id("dsl"),
                "partition": "train",
                "source_mode": "programmatic",
                "dimension": "directness-subject-line",
                "difficulty": "easy",
                "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                             "probe_ids": []},
                "input": {
                    "prospect": create_prospect_payload(company),
                    "prior_thread": [] if email_type == "cold" else ["Thanks, will review."],
                },
                "candidate_output": {"subject": bad_subj, "body": bad_body},
                "ground_truth": {
                    "behavior_summary": "Subject lines must be direct. No filler words like Quick, Just, Hey."
                },
                "scoring": {
                    "max_score": 4,
                    "checks": [
                        {"id": "no-filler-subject", "type": "forbidden_phrases",
                         "target": "subject", "phrases": forbidden, "points": 2},
                        {"id": "no-hope-youre-well", "type": "forbidden_phrases",
                         "target": "body",
                         "phrases": ["hope you're doing well", "hope this finds you well"],
                         "points": 1},
                        {"id": "body-under-120-words", "type": "max_words",
                         "target": "body", "max_words": 120, "points": 1},
                    ],
                },
            })
    return tasks

# ── Dimension 7: Single clear ask ─────────────────────────────────────

def gen_single_clear_ask() -> list[dict[str, Any]]:
    tasks = []
    multi_ask_bodies = [
        "Could we set up a call? Also, would you share your current architecture? And perhaps your team size?",
        "Worth a call? Also curious about your stack. What tools do you use for CI/CD?",
        "Can we chat? Also wondering about headcount. Are you hiring for ML roles?",
    ]
    for body in multi_ask_bodies:
        company = random.choice(COMPANIES)
        tasks.append({
            "task_id": generate_task_id("sca"),
            "partition": "train",
            "source_mode": "programmatic",
            "dimension": "single-clear-ask",
            "difficulty": "easy",
            "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                         "probe_ids": []},
            "input": {"prospect": create_prospect_payload(company), "prior_thread": []},
            "candidate_output": {
                "subject": "Question on your engineering team",
                "body": body,
            },
            "ground_truth": {
                "behavior_summary": "Cold outreach must carry one clear ask, not multiple parallel questions."
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {"id": "single-question-ask", "type": "max_question_marks",
                     "target": "body", "max_question_marks": 1, "points": 2},
                    {"id": "mentions-15-minutes", "type": "required_phrases_any",
                     "target": "body", "phrases": ["15 minutes", "15 minute", "call"],
                     "points": 1},
                    {"id": "body-under-120-words", "type": "max_words",
                     "target": "body", "max_words": 120, "points": 1},
                ],
            },
        })
    return tasks

# ── Dimension 8: Bench jargon leakage ─────────────────────────────────

def gen_bench_jargon() -> list[dict[str, Any]]:
    tasks = []
    jargon_terms = [
        ("bench", ["bench"]),
        ("on the bench", ["on the bench"]),
        ("bench strength", ["bench strength"]),
    ]
    contexts = [
        "What does your available capacity look like for Python backend work?",
        "Do you have engineers who could start soon?",
    ]
    for (term, forbidden), ctx in itertools.product(jargon_terms, contexts):
        company = random.choice(COMPANIES)
        bad_body = f"We have engineers on the {term} who can start next week on your Python project."
        tasks.append({
            "task_id": generate_task_id("bjl"),
            "partition": "train",
            "source_mode": "programmatic",
            "dimension": "bench-jargon",
            "difficulty": "easy",
            "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                         "probe_ids": ["P015"]},
            "input": {"prospect": create_prospect_payload(company), "prior_thread": [ctx]},
            "candidate_output": {
                "subject": "Context: Python capacity",
                "body": bad_body,
            },
            "ground_truth": {
                "behavior_summary": "Professional wording must use capacity language, not internal bench jargon."
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {"id": f"no-{term.replace(' ', '-')}", "type": "forbidden_phrases",
                     "target": "body", "phrases": forbidden, "points": 2},
                    {"id": "mentions-capacity", "type": "required_phrases_any",
                     "target": "body", "phrases": ["capacity", "available", "ready to deploy"],
                     "points": 1},
                    {"id": "body-under-120-words", "type": "max_words",
                     "target": "body", "max_words": 120, "points": 1},
                ],
            },
        })
    return tasks

# ── Dimension 9: Hype vocabulary ──────────────────────────────────────

def gen_hype_vocabulary() -> list[dict[str, Any]]:
    tasks = []
    hype_phrases = [
        (["top talent", "world-class", "A-players"], "top talent and world-class A-players"),
        (["rockstar", "ninja", "10x"], "rockstar engineers who are 10x developers"),
        (["guaranteed savings", "cost savings of"], "guaranteed cost savings of 40%"),
    ]
    for forbidden, bad_snippet in hype_phrases:
        company = random.choice(COMPANIES)
        tasks.append({
            "task_id": generate_task_id("hyp"),
            "partition": "train",
            "source_mode": "programmatic",
            "dimension": "hype-vocabulary",
            "difficulty": "easy",
            "metadata": {"seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                         "probe_ids": ["P016"]},
            "input": {"prospect": create_prospect_payload(company), "prior_thread": []},
            "candidate_output": {
                "subject": "Request: discuss your engineering needs",
                "body": f"We provide {bad_snippet} for companies at your stage. Worth 15 minutes?",
            },
            "ground_truth": {
                "behavior_summary": "Offshore-vendor clichés trigger skepticism in senior engineering leaders."
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {"id": "no-hype-vocab", "type": "forbidden_phrases",
                     "target": "body", "phrases": forbidden, "points": 2},
                    {"id": "body-under-120-words", "type": "max_words",
                     "target": "body", "max_words": 120, "points": 1},
                    {"id": "single-ask", "type": "max_question_marks",
                     "target": "body", "max_question_marks": 1, "points": 1},
                ],
            },
        })
    return tasks


def main() -> None:
    """Generate all programmatic benchmark tasks and write to raw output file."""
    random.seed(cfg.RANDOM_SEED)
    all_tasks: list[dict[str, Any]] = []
    generators = [
        ("weak-evidence-overclaim", gen_weak_evidence_overclaim),
        ("bench-over-commitment", gen_bench_overcommitment),
        ("timezone-fabrication", gen_timezone_fabrication),
        ("competitor-gap-assertion", gen_competitor_gap_assertion),
        ("segment-2-first-touch", gen_segment2_first_touch),
        ("directness-subject-line", gen_directness_subject_line),
        ("single-clear-ask", gen_single_clear_ask),
        ("bench-jargon", gen_bench_jargon),
        ("hype-vocabulary", gen_hype_vocabulary),
    ]

    for name, gen_fn in generators:
        tasks = gen_fn()
        logger.info("Generated %d tasks for dimension: %s", len(tasks), name)
        all_tasks.extend(tasks)

    out_path = cfg.GENERATION_DIR / "programmatic_raw.json"
    out_path.write_text(json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Total programmatic tasks generated: %d", len(all_tasks))
    logger.info("Results written to: %s", out_path)


if __name__ == "__main__":
    main()
