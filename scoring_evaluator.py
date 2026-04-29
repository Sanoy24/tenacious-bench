from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


TIMEZONE_RE = re.compile(
    r"\b(?:CET|CEST|EST|EDT|PST|PDT|BST|GMT|EAT|UTC(?:[+-]\d{1,2})?)\b",
    re.IGNORECASE,
)


def read_tasks(path: Path) -> list[dict[str, Any]]:
    """Read tasks from a file or directory recursively."""
    if path.is_dir():
        tasks: list[dict[str, Any]] = []
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in {".json", ".jsonl"}:
                tasks.extend(read_tasks(candidate))
        return tasks

    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "example_tasks" in payload:
        return payload["example_tasks"]
    if isinstance(payload, dict):
        return [payload]
    raise ValueError(f"Unsupported task payload in {path}")


def get_target_text(task: dict[str, Any], target: str) -> str:
    output = task.get("candidate_output", {})
    subject = str(output.get("subject", ""))
    body = str(output.get("body", ""))
    if target == "subject":
        return subject
    if target == "body":
        return body
    if target == "full_email":
        return f"{subject}\n{body}".strip()
    raise ValueError(f"Unsupported target {target}")


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def unavailable_stacks(task: dict[str, Any], required_stacks: list[str]) -> list[str]:
    bench = task.get("input", {}).get("bench_summary", {}).get("stacks", {})
    missing: list[str] = []
    for stack in required_stacks:
        available = bench.get(stack, {}).get("available_engineers")
        if not isinstance(available, int) or available <= 0:
            missing.append(stack)
    return missing


def evaluate_check(task: dict[str, Any], check: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a single check against a task candidate output."""
    check_type = check["type"]
    target = check.get("target", "body")
    text = get_target_text(task, target)
    lowered = text.lower()

    if check_type == "max_words":
        actual = word_count(text)
        limit = int(check["max_words"])
        return actual <= limit, f"{actual} words (limit {limit})"

    if check_type == "max_subject_chars":
        actual = len(text)
        limit = int(check["max_subject_chars"])
        return actual <= limit, f"{actual} chars (limit {limit})"

    if check_type == "forbidden_phrases":
        phrases = [phrase.lower() for phrase in check.get("phrases", [])]
        hits = [phrase for phrase in phrases if phrase in lowered]
        return not hits, f"hits={hits}" if hits else "no forbidden phrases"

    if check_type == "required_phrases_any":
        phrases = check.get("phrases", [])
        hits = [phrase for phrase in phrases if phrase.lower() in lowered]
        return bool(hits), f"hits={hits}" if hits else "no required phrase found"

    if check_type == "forbidden_regex":
        patterns = [re.compile(pattern, re.IGNORECASE) for pattern in check.get("patterns", [])]
        hits = [pattern.pattern for pattern in patterns if pattern.search(text)]
        return not hits, f"regex_hits={hits}" if hits else "no forbidden regex matches"

    if check_type == "max_question_marks":
        actual = text.count("?")
        limit = int(check["max_question_marks"])
        return actual <= limit, f"{actual} question marks (limit {limit})"

    if check_type == "no_prospect_local_when_timezone_missing":
        prospect = task.get("input", {}).get("prospect", {})
        timezone = prospect.get("timezone")
        if timezone:
            return True, "timezone present"
        proposed_times = task.get("candidate_output", {}).get("proposed_times", [])
        local_values = [slot.get("prospect_local") for slot in proposed_times if slot.get("prospect_local")]
        tz_hits = TIMEZONE_RE.findall(get_target_text(task, "full_email"))
        ok = not local_values and not tz_hits
        detail = f"local_values={local_values}, timezone_mentions={tz_hits}"
        return ok, detail

    if check_type == "no_unavailable_stack_commitment":
        required = [stack.lower() for stack in check.get("required_stacks", task.get("input", {}).get("required_stacks", []))]
        missing = unavailable_stacks(task, required)
        if not missing:
            return True, "all required stacks available"
        risky_patterns: list[str] = []
        for stack in missing:
            stack_re = re.escape(stack)
            patterns = [
                rf"\b{stack_re}\b.{0,40}\b(?:engineer|engineers|capacity|available|ready)\b",
                rf"\b(?:engineer|engineers|capacity|available|ready)\b.{0,40}\b{stack_re}\b",
            ]
            risky_patterns.extend(patterns)
        hits = [pattern for pattern in risky_patterns if re.search(pattern, text, re.IGNORECASE | re.DOTALL)]
        return not hits, f"missing={missing}, hits={hits}" if hits else f"missing={missing}, no risky commitment"

    if check_type == "icp_segment_size_guard":
        segment = check.get("segment", "")
        min_emp = int(check.get("min_employees", 0))
        prospect = task.get("input", {}).get("prospect", {})
        emp_count = prospect.get("employee_count", 0)
        if emp_count >= min_emp:
            return True, f"employee_count={emp_count} >= {min_emp}"
        # Check if the email pitches the gated segment anyway
        seg_keywords = {"segment_4": ["project", "consulting", "embedded squad"]}
        keywords = seg_keywords.get(segment, [])
        hits = [kw for kw in keywords if kw in lowered]
        return not hits, f"employee_count={emp_count} < {min_emp}, segment_pitch_hits={hits}"

    if check_type == "no_emoji_in_cold_outreach":
        email_type = task.get("input", {}).get("email_type", "cold_outreach")
        if email_type != "cold_outreach":
            return True, "not cold outreach"
        emoji_chars = [c for c in text if unicodedata.category(c) in ("So", "Sk")]
        full_text = get_target_text(task, "full_email")
        emoji_chars += [c for c in full_text if unicodedata.category(c) in ("So", "Sk")]
        return not emoji_chars, f"emojis={emoji_chars}" if emoji_chars else "no emojis"

    if check_type == "signature_format_check":
        max_lines = int(check.get("max_lines", 4))
        sig = task.get("candidate_output", {}).get("signature", "")
        if not sig:
            return True, "no signature field"
        sig_lines = [line for line in sig.strip().splitlines() if line.strip()]
        ok = len(sig_lines) <= max_lines
        return ok, f"{len(sig_lines)} lines (max {max_lines})"

    if check_type == "requires_confirmation_before_action":
        output = task.get("candidate_output", {})
        confirmed = output.get("confirmation_requested", False)
        return confirmed, f"confirmation_requested={confirmed}"

    if check_type == "requires_auth_verification":
        output = task.get("candidate_output", {})
        verified = output.get("auth_verified", False)
        return verified, f"auth_verified={verified}"

    if check_type == "no_fabricated_identifiers":
        output = task.get("candidate_output", {})
        action = output.get("action_taken", "")
        # Check if an order_id was referenced that wasn't in the input
        input_ids = set()
        user_req = task.get("input", {}).get("user_request", "")
        import re as _re
        input_ids.update(_re.findall(r"[A-Z0-9]{6,}", user_req))
        output_text = json.dumps(output)
        output_ids = set(_re.findall(r"[A-Z0-9]{6,}", output_text))
        fabricated = output_ids - input_ids
        return not fabricated, f"fabricated_ids={fabricated}" if fabricated else "no fabricated ids"

    raise ValueError(f"Unsupported check type: {check_type}")


def evaluate_task(task: dict[str, Any]) -> dict[str, Any]:
    """Score all checks for a single task and return a result dictionary."""
    checks = task.get("scoring", {}).get("checks", [])
    max_score = int(task.get("scoring", {}).get("max_score", 0))
    awarded = 0
    results: list[dict[str, Any]] = []

    for check in checks:
        passed, detail = evaluate_check(task, check)
        points = int(check.get("points", 0)) if passed else 0
        awarded += points
        results.append(
            {
                "id": check["id"],
                "type": check["type"],
                "passed": passed,
                "points_awarded": points,
                "points_possible": int(check.get("points", 0)),
                "detail": detail,
            }
        )

    return {
        "task_id": task.get("task_id"),
        "partition": task.get("partition"),
        "source_mode": task.get("source_mode"),
        "dimension": task.get("dimension"),
        "score": awarded,
        "max_score": max_score,
        "passed_all_checks": all(result["passed"] for result in results),
        "checks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate starter Tenacious-Bench tasks.")
    parser.add_argument(
        "--path",
        default="tenacious_bench_v0.1",
        help="Path to a task file, schema file, or benchmark directory",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()

    tasks = read_tasks(Path(args.path))
    results = [evaluate_task(task) for task in tasks]
    summary = {
        "task_count": len(results),
        "passed_all": sum(1 for result in results if result["passed_all_checks"]),
        "results": results,
    }
    logger.info(f"Evaluation complete: {summary['passed_all']}/{summary['task_count']} passed")
    print(json.dumps(summary, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
