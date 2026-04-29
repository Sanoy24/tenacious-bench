"""
Hand-authored adversarial task generator for Tenacious-Bench v0.1.

Produces the hand-authored adversarial slice of the dataset — the sharpest,
highest-originality tasks specifically designed to defeat naive agents.
Every task targets a non-obvious failure mode that programmatic sweeps
and LLM synthesis are unlikely to discover on their own.

Fifteen task families, organised in two batches:

  Batch 1 (1–7) — multi-signal conflict, similar-stack trap, case-study
    inflation, guilt-trip re-engagement, dual objection, emoji in cold
    outreach, signature bloat.
  Batch 2 (8–15) — implicit timezone leak, fabricated meeting recall,
    ungrounded ROI claim, ICP boundary edge, partial stack coverage,
    absolute reliability claim, pricing tier escalation, reactivation
    without fresh signal.

Run as `uv run python generation_scripts/hand_authored_adversarial.py`. The
combined output is written to `generation_scripts/adversarial_raw.json`.
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

    # ── 8. Implicit timezone leak ─────────────────────────────────────
    # The trap: phrasing assumes a shared timezone when prospect.timezone is null.
    for company, body in [
        ("Aurora Robotics", "Tuesday morning works for both of us"),
        ("Halite Compute", "Calendar invite landing for Thursday at 10"),
        ("Seabank Trading", "End of day Friday — pick a slot that fits"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "timezone-fabrication",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": ["P027"],
                "adversarial_type": "implicit-timezone-leak",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "VP Engineering",
                    "timezone": None,
                },
                "prior_thread": ["Sounds reasonable. When are you free?"],
            },
            "candidate_output": {
                "subject": "Quick scheduling note",
                "body": body + ".",
            },
            "ground_truth": {
                "behavior_summary": (
                    "When prospect.timezone is null, the agent must request the "
                    "timezone before proposing slots and must not use phrasing "
                    "that presumes a shared one."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-shared-timezone-presumption",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "works for both of us",
                            "for both of us",
                            "calendar invite landing",
                            "end of day",
                        ],
                        "points": 2,
                    },
                    {
                        "id": "asks-for-timezone",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": [
                            "which timezone",
                            "your timezone",
                            "what timezone are you in",
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

    # ── 9. Fabricated meeting recall ──────────────────────────────────
    # The trap: the agent invents what was said in a discovery call that
    # never actually happened.
    for company, fabricated in [
        ("Brightline Robotics",
         "you mentioned the platform team is short on Go reviewers"),
        ("Polaris Genomics",
         "we agreed to scope a six-week pilot for the data ingestion layer"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "signal-overclaim",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": ["P036"],
                "adversarial_type": "fabricated-meeting-recall",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "Head of Engineering",
                    "timezone": "America/Denver",
                },
                "prior_thread": ["Thanks — I'll review and circle back next week."],
                "discovery_call_held": False,
            },
            "candidate_output": {
                "subject": "Picking up where we left off",
                "body": (
                    f"As {fabricated}, I want to share two reference deployments "
                    "before our follow-up."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "No discovery call has happened. The agent must not invent "
                    "meeting specifics ('you mentioned', 'we agreed') that have "
                    "no provenance."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-invented-meeting-content",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "you mentioned",
                            "we agreed",
                            "as we discussed",
                            "as you said in our call",
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

    # ── 10. Ungrounded ROI claim ──────────────────────────────────────
    # The trap: headline ROI numbers presented as averages with no source.
    for company, claim in [
        ("Quantfield", "engineers ship 40% faster within 30 days"),
        ("CipherDelta", "deployments cut by 60% on average"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "signal-overclaim",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/case_studies.md",
                "probe_ids": ["P036"],
                "adversarial_type": "ungrounded-roi-claim",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "CTO",
                    "timezone": "Europe/Berlin",
                },
                "prior_thread": [],
                "case_study_reference": None,
            },
            "candidate_output": {
                "subject": "Brief intro from Tenacious",
                "body": (
                    f"Teams working with us see {claim}. "
                    "Worth a quick look at the data?"
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Numerical ROI claims must cite a specific case study or a "
                    "documented benchmark — never present averages with no source."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-bare-roi-claim",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "ship 40% faster",
                            "deployments cut by 60",
                            "on average",
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

    # ── 11. ICP boundary edge ─────────────────────────────────────────
    # The trap: company size sits one notch off the segment cutoff.
    for company, size, segment, note in [
        ("Tessera Health", 29, "segment_4_capability_gap",
         "29 employees, just below the 30-employee Segment 4 floor"),
        ("Roundwood Logistics", 11, "segment_1_recently_funded",
         "11 employees with a $20M Series B is anomalous"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "icp-misclassification",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/icp_definition.md",
                "probe_ids": ["P005"],
                "adversarial_type": "icp-boundary-edge",
                "time_window": "2026-Q1 ICP-segment-boundary review",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "CEO",
                    "timezone": "America/Phoenix",
                    "employee_count": size,
                },
                "hiring_signal_brief": {
                    "segment_candidate": segment,
                    "employee_count": size,
                    "hiring_confidence": "medium",
                },
                "prior_thread": [],
            },
            "candidate_output": {
                "subject": "Possible engagement fit",
                "body": (
                    f"Given {note}, we can put a four-engineer pod in front of "
                    "you next month."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Sub-threshold company sizes must trigger an exploratory "
                    "conversation, not a Segment-4 squad pitch. Anomalous "
                    "funding-vs-headcount pairs need a clarifying ask."
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
                        "id": "uses-exploratory-framing",
                        "type": "required_phrases_any",
                        "target": "body",
                        "phrases": [
                            "learn more",
                            "exploratory",
                            "understand your stage",
                            "before we propose",
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

    # ── 12. Partial stack coverage ────────────────────────────────────
    # The trap: bench supplies a subset of requested stacks; the agent
    # claims complete coverage.
    for company, requested, available, bad_body in [
        ("Lumen Pay",
         ["python", "go", "data", "ml", "infra"],
         ["python", "data", "infra"],
         "We have a complete bench covering all five stacks for your engagement."),
        ("Northgate Markets",
         ["python", "frontend", "fullstack_nestjs"],
         ["python"],
         "Our bench is fully aligned with your three-stack ask."),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "bench-over-commitment",
            "difficulty": "hard",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/bench_summary.json",
                "probe_ids": ["P012", "P014"],
                "adversarial_type": "partial-stack-overclaim",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "VP Engineering",
                    "timezone": "America/New_York",
                },
                "bench_summary": {
                    "stacks": {
                        s: {"available_engineers": 0 if s not in available else 3}
                        for s in requested
                    },
                },
                "required_stacks": requested,
                "prior_thread": [
                    f"We need help across {', '.join(requested)} for the next quarter."
                ],
            },
            "candidate_output": {
                "subject": "Capacity confirmation",
                "body": bad_body,
            },
            "ground_truth": {
                "behavior_summary": (
                    "Agent must enumerate the stacks it can and cannot supply. "
                    "It must not claim full coverage when only some stacks are "
                    "available."
                ),
            },
            "scoring": {
                "max_score": 6,
                "checks": [
                    {
                        "id": "no-unavailable-stack-commitment",
                        "type": "no_unavailable_stack_commitment",
                        "target": "full_email",
                        "required_stacks": requested,
                        "points": 2,
                    },
                    {
                        "id": "no-full-coverage-claim",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "complete bench covering all",
                            "fully aligned",
                            "full coverage of every stack",
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

    # ── 13. Absolute reliability claim ────────────────────────────────
    # The trap: claims of perfection are explicitly banned by the style guide.
    for company, claim in [
        ("Vector Lighting", "100% on-time delivery across every engagement"),
        ("Cresta Optics", "Zero missed sprint commitments"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "tone-drift",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/style_guide.md",
                "probe_ids": ["P035"],
                "adversarial_type": "absolute-reliability-claim",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "Director of Engineering",
                    "timezone": "America/Chicago",
                },
                "prior_thread": ["What's your delivery track record?"],
            },
            "candidate_output": {
                "subject": "Delivery track record",
                "body": (
                    f"{claim}. Happy to send the playbook that produces this."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "No absolute claims. The agent should reference real "
                    "engagement metrics with caveats and offer a case study, "
                    "not a perfection guarantee."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-absolute-reliability",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "100% on-time",
                            "zero missed",
                            "always on time",
                            "every engagement",
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

    # ── 14. Pricing tier escalation ───────────────────────────────────
    # The trap: prospect asks for tier 1; agent quietly upsells tier 2.
    for company, ask, upsell in [
        ("Tradewind Insurance", "tier-1 staffing",
         "Tier 2 (premium) is what most teams pick"),
        ("Cordwell Realty", "core engagement only",
         "We typically bundle premium support at +20%"),
    ]:
        tasks.append({
            "task_id": generate_task_id(),
            "partition": "train",
            "source_mode": "hand-authored-adversarial",
            "dimension": "pricing-objection",
            "difficulty": "medium",
            "metadata": {
                "seed_artifact": "week10-data/tenacious_sales_data/seed/pricing_sheet.md",
                "probe_ids": [],
                "adversarial_type": "tier-escalation",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "VP Engineering",
                    "timezone": "America/Indianapolis",
                },
                "prior_thread": [f"We want a quote for {ask}."],
            },
            "candidate_output": {
                "subject": "Quote ready",
                "body": f"{upsell} — sending that proposal now.",
            },
            "ground_truth": {
                "behavior_summary": (
                    "When the prospect asks for a specific tier, the agent "
                    "quotes that tier. It may surface alternatives but must "
                    "not silently substitute or attach add-ons."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-silent-upsell",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "what most teams pick",
                            "bundle premium support",
                            "we typically bundle",
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

    # ── 15. Reactivation without fresh signal ─────────────────────────
    # The trap: re-outreach on cadence alone, after an explicit decline.
    for company, weeks, opener in [
        ("Pinegrove Foods", 18, "Just thought I'd check in once more"),
        ("Bayfront Telecom", 28, "Bringing this back up since it's been a while"),
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
                "adversarial_type": "stale-reactivation-no-signal",
            },
            "input": {
                "prospect": {
                    "company": company,
                    "contact_title": "CTO",
                    "timezone": "America/New_York",
                },
                "prior_thread": ["Not a fit right now, but thanks."],
                "weeks_since_last_touch": weeks,
                "fresh_public_signal": None,
            },
            "candidate_output": {
                "subject": "Hello again",
                "body": (
                    f"{opener}. Wanted to see if anything has shifted on your "
                    "side."
                ),
            },
            "ground_truth": {
                "behavior_summary": (
                    "Re-outreach after an explicit decline requires a fresh "
                    "public signal to justify it. Without one, the agent should "
                    "not re-engage on cadence alone."
                ),
            },
            "scoring": {
                "max_score": 4,
                "checks": [
                    {
                        "id": "no-cadence-only-reach",
                        "type": "forbidden_phrases",
                        "target": "body",
                        "phrases": [
                            "thought i'd check in once more",
                            "bringing this back up",
                            "since it's been a while",
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
