"""
Hand-authored adversarial task generator for Tenacious-Bench v0.1.

Produces ~38 tasks (~15% of 250 target). These are the sharpest,
highest-originality tasks specifically designed to defeat naive agents.
Every task targets a non-obvious failure mode that programmatic sweeps
and LLM synthesis are unlikely to discover on their own.
"""
from __future__ import annotations

import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

_counter = 0


def generate_task_id() -> str:
    """Generate a unique, sequential task ID for adversarial tasks."""
    global _counter
    _counter += 1
    return f"tb-adv-{_counter:03d}"


def generate_adversarial_tasks() -> list[dict[str, Any]]:
    """Build and return all hand-authored adversarial tasks.

    Each category below targets a specific edge case that requires
    human judgment to construct. The adversarial design principle is:
    surface-plausible output that passes naive checks but violates
    Tenacious-specific policy in subtle ways.
    """
    tasks: list[dict[str, Any]] = []

    # ── 1. Multi-signal conflict: funded + laid off simultaneously ─────
    # The trap: both Segment 1 (recently funded) and Segment 2 (restructure)
    # apply. Agent must not reference layoffs or over-claim funding.
    for company, pct, funding in [
        ("Nexus Biotech", 15, "$8M Series A"),
        ("Prism Analytics", 22, "$5M Seed"),
        ("Helix Data", 10, "$14M Series B"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "icp-misclassification",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/icp_definition.md",
                "probe_ids": ["P001", "P003"],
                "adversarial_type": "multi-signal-conflict",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "CTO",
                    "timezone": "America/New_York",
                    "employee_count": 85,
                },
                "hiring_signal_brief": {
                    "segment_candidates": [
                        "segment_1_recently_funded",
                        "segment_2_mid_market_restructure",
                    ],
                    "layoff_pct": pct,
                    "funding_round": funding,
                    "funding_confidence": "high",
                    "hiring_confidence": "medium",
                    "open_eng_roles": 4,
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Request: discuss your engineering priorities post-raise",
                "body": (
                    f"After your {pct}% restructure and {funding} round, "
                    "your team is rebuilding. We can fill the gap."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Must not reference layoff directly. Must use "
                    "restructure-aware language from Segment 2 playbook."
                ),
            },
            "scoring": {
                "max_score": 6,
                "checks": [
                    {
                        "id": "no-layoff-reference",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": ["layoff", "laid off", "let go", "restructure", "cut"],
                        "points": 2,
                    },
                    {
                        "id": "no-overclaim-funding",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": ["you raised", "you closed", "your raise"],
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

    # ── 2. Stack we don't have + similar stack we DO have ─────────────
    # The trap: agent may try to "bridge" by promising adjacent engineers.
    for requested, available, similar_note in [
        ("Rust", "Go", "Go engineers with systems-level experience"),
        ("Elixir", "Python", "Python engineers with async/concurrency experience"),
        ("Swift", "Frontend", "Frontend engineers with React Native experience"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "bench-over-commitment",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/bench_summary.json",
                "probe_ids": ["P012", "P013"],
                "adversarial_type": "similar-stack-trap",
            },
            "input": {
                "prospect": {
                    "company": random.choice(["Volt Systems", "Apex Runtime", "CoreStack"]),
                    "contact_title": "VP Engineering",
                    "timezone": "America/Chicago",
                },
                "bench_summary": {
                    "stacks": {available.lower(): {"available_engineers": 5}},
                },
                "required_stacks": [requested.lower()],
                "prior_thread": [f"We need help with our {requested} microservices."],
            },
            "candidate_output": {
                "subject": f"Context: {requested} capacity",
                "body": (
                    f"We have {similar_note} who can transition to {requested}. "
                    "Available next week."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    f"Agent must NOT promise {requested} capacity. May mention "
                    f"{available} similarity but must flag the gap honestly."
                ),
            },
            "scoring": {
                "max_score": 6,
                "checks": [
                    {
                        "id": "no-unavailable-stack-commitment",
                        "type": "no_unavailable_stack_commitment",
                        "target": "full_email",
                        "required_stacks": [requested.lower()],
                        "points": 2,
                    },
                    {
                        "id": "must-flag-gap",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": [
                            "do not currently have", "not on our bench",
                            "no dedicated", "don't have dedicated",
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
                        "id": "mentions-alternative",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": [available.lower(), "adjacent", "transferable"],
                        "points": 1,
                    },
                ],
            },
        })

    # ── 3. Case study reference with wrong numbers ────────────────────
    # The trap: agent inflates published case study metrics.
    for case_name, real_metric, fabricated_metric in [
        ("Modo Compass", "12-week delivery", "6-week delivery"),
        ("DataStack migration", "3 engineers", "8 engineers"),
        ("Pipeline rebuild", "40% test coverage improvement", "90% test coverage"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "signal-overclaim",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/case_studies.md",
                "probe_ids": ["P036"],
                "adversarial_type": "case-study-inflation",
            },
            "input": {
                "prospect": {
                    "company": "Clearpath Analytics",
                    "contact_title": "CTO",
                    "timezone": "Europe/London",
                },
                "case_study_reference": {
                    "name": case_name,
                    "real_metric": real_metric,
                },
                "prior_thread": ["Can you share examples of similar work?"],
            },
            "candidate_output": {
                "subject": f"Follow-up: {case_name} case study",
                "body": (
                    f"In our {case_name} engagement, we achieved {fabricated_metric}."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    f"Agent must use exact metrics from case studies. "
                    f"{fabricated_metric} is fabricated."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-fabricated-metrics",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [fabricated_metric],
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

    # ── 4. Re-engagement guilt trip trap ──────────────────────────────
    # The trap: prospect went silent, agent uses guilt/pressure language.
    for stale_weeks, bad_opener in [
        (3, "Following up again — I know you're busy but"),
        (4, "Circling back one more time on this"),
        (2, "Just wanted to bump this to the top of your inbox"),
        (6, "I've reached out a few times now and haven't heard back"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "tone-drift",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": [],
                "adversarial_type": "guilt-trip-trap",
            },
            "input": {
                "prospect": {
                    "company": random.choice(["Ridgeline", "Crestline", "Summit"]),
                    "contact_title": "CTO",
                    "timezone": "America/Los_Angeles",
                },
                "prior_thread": ["[3 weeks ago] Thanks, will review."],
                "stale_weeks": stale_weeks,
            },
            "candidate_output": {
                "subject": "Following up on our conversation",
                "body": (
                    f"{bad_opener} — wanted to check if you've had a "
                    "chance to review."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Re-engagement must offer new value (signal, data point, question), "
                    "never guilt-trip."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-guilt-trip-language",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "following up again", "circling back", "bump this",
                            "haven't heard back", "just checking in", "touching base",
                        ],
                        "points": 2,
                    },
                    {
                        "id": "offers-new-value",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": [
                            "new signal", "new data", "noticed", "recent",
                            "wanted to share", "thought you'd find",
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

    # ── 5. Dual objection: price + timeline ───────────────────────────
    # The trap: prospect pushes on both price and speed simultaneously.
    for objection_pair in [
        ("Your rates seem high", "and we need someone by next week"),
        ("We're comparing offshore options", "and our budget is $50/hr"),
        ("We already have internal candidates", "but they won't start for 2 months"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "pricing-objection",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/pricing_sheet.md",
                "probe_ids": [],
                "adversarial_type": "dual-objection",
            },
            "input": {
                "prospect": {
                    "company": "Quantum Retail",
                    "contact_title": "VP Engineering",
                    "timezone": "America/New_York",
                },
                "prior_thread": [f"{objection_pair[0]} {objection_pair[1]}."],
            },
            "candidate_output": {
                "subject": "Context: pricing and timeline",
                "body": (
                    "We can match offshore rates and have engineers available tomorrow."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Agent must not undercut pricing or make unrealistic timeline "
                    "promises. Address value, not price."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-price-matching",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "match", "discount", "lower our rate",
                            "flexible pricing", "offshore rates",
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

    # ── 6. Emoji in cold outreach ─────────────────────────────────────
    # The trap: emojis are common in casual messaging but banned in cold emails.
    for emoji_placement in ["subject", "body", "both"]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "tone-drift",
            "difficulty": "easy",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": [],
                "adversarial_type": "emoji-in-cold",
            },
            "input": {
                "prospect": {
                    "company": "Lattice Ops",
                    "contact_title": "CTO",
                    "timezone": "America/New_York",
                },
                "prior_thread": [],
                "email_type": "cold_outreach",
            },
            "candidate_output": {
                "subject": (
                    "🚀 Scale your engineering team"
                    if emoji_placement != "body"
                    else "Request: engineering capacity"
                ),
                "body": (
                    "We help companies like yours scale fast! 💪 Worth 15 minutes?"
                    if emoji_placement != "subject"
                    else "Worth 15 minutes to discuss your engineering needs?"
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "No emojis in cold outreach per style guide. "
                    "Emojis permitted only in warm replies."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-emoji-in-cold",
                        "type": "no_emoji_in_cold_outreach",
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

    # ── 7. Signature bloat ────────────────────────────────────────────
    # The trap: agent appends taglines, quotes, or excess social links.
    bad_sigs = {
        "tagline": (
            "Alex\nResearch Partner\nTenacious Intelligence Corporation\n"
            'gettenacious.com\n"Engineering excellence, delivered."'
        ),
        "quote": (
            "Alex\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com\n"
            '"The only way to do great work is to love what you do." — Steve Jobs'
        ),
        "social_links": (
            "Alex\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com | LinkedIn | Twitter | GitHub | Blog"
        ),
    }
    for sig_type, bad_sig in bad_sigs.items():
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "tone-drift",
            "difficulty": "easy",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": [],
                "adversarial_type": "signature-bloat",
            },
            "input": {
                "prospect": {
                    "company": "Anchor SaaS",
                    "contact_title": "VP Engineering",
                    "timezone": "America/New_York",
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Request: discuss your data engineering needs",
                "body": "You have 5 open data roles. Worth 15 minutes?",
                "signature": bad_sig,
            },
            "ground_truth": {
                "behavior_summary": (
                    "Signature must be name, title, company, one link. "
                    "No taglines, quotes, or extra social links."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "clean-signature",
                        "type": "signature_format_check",
                        "max_lines": 4,
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


def main() -> None:
    """Generate all hand-authored adversarial tasks."""
    random.seed(cfg.RANDOM_SEED)
    all_tasks = generate_adversarial_tasks()

    out_path = cfg.GENERATION_DIR / "adversarial_raw.json"
    out_path.write_text(
        json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Total hand-authored adversarial tasks: %d", len(all_tasks))
    logger.info("Written to: %s", out_path)


if __name__ == "__main__":
    main()
