"""
ablations/run_ablations.py

Delta A, Delta B, and cost-Pareto ablations for Tenacious-Bench Path B.

  Delta A  — trained judge (LoRA adapter) vs base model pairwise accuracy
             on sealed held-out (48 tasks). Paired bootstrap, 95% CI, p<0.05.
  Delta B  — base model + explicit rubric system prompt vs trained model.
             Tests whether prompting alone matches training. Report honestly.
  Cost-Pareto — per-task inference latency with/without adapter.

Requires:
  OPENROUTER_API_KEY env var (for generating held-out chosen outputs).
  training/checkpoints/final_adapter/  (from train_judge.py run).

Usage (Colab):
  python ablations/run_ablations.py \\
      --adapter training/checkpoints/final_adapter

  # Skip chosen-output generation if already cached:
  python ablations/run_ablations.py \\
      --adapter training/checkpoints/final_adapter \\
      --skip-generation
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "training_data"))

from scoring_evaluator import evaluate_task  # noqa: E402
from build_pairs import (  # noqa: E402
    build_user_message,
    call_openrouter,
    parse_rewrite,
    SYSTEM_PROMPT,
)

HELD_OUT_PATH = ROOT / "tenacious_bench_v0.1" / "held_out" / "tasks.json"
ABLATIONS_DIR = ROOT / "ablations"
CACHE_PATH = ABLATIONS_DIR / "held_out_chosen_cache.jsonl"

RESULTS_PATH = ABLATIONS_DIR / "ablation_results.json"
TRACES_PATH = ABLATIONS_DIR / "held_out_traces.jsonl"
STATS_PATH = ABLATIONS_DIR / "statistical_tests.json"

MAX_LEN = 512
SEED = 42
BOOTSTRAP_ITERS = 1000

# Judge system prompt for Delta B (prompt-engineering baseline)
JUDGE_SYSTEM_PROMPT = (
    "You are a B2B sales outreach quality evaluator for Tenacious, "
    "a technical staffing company. "
    "Assign higher probability to outreach emails that strictly follow these rules:\n"
    "1. Never commit to a tech stack with zero bench engineers — acknowledge the gap.\n"
    "2. Never use confident velocity language (e.g. 'scaling fast', 'aggressive hiring') "
    "unless hiring confidence is HIGH.\n"
    "3. Never fabricate prospect-local times or timezone labels when no timezone was provided.\n"
    "4. Keep the body under 120 words.\n"
    "5. Ask at most one question.\n"
    "A policy-compliant email is always preferred over a policy-violating one."
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Data helpers ──────────────────────────────────────────────────────────────


def load_held_out() -> list[dict[str, Any]]:
    tasks = json.loads(HELD_OUT_PATH.read_text(encoding="utf-8"))
    log.info("Loaded %d held-out tasks", len(tasks))
    return tasks


def candidate_output_text(task: dict[str, Any]) -> str:
    out = task.get("candidate_output", {})
    subject = out.get("subject", "")
    body = out.get("body", "")
    return f"Subject: {subject}\n\n{body}".strip()


def load_chosen_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    cache: dict[str, str] = {}
    for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rec = json.loads(line)
            cache[rec["task_id"]] = rec["chosen_text"]
    log.info("Loaded %d cached chosen outputs", len(cache))
    return cache


def save_chosen_cache(task_id: str, chosen_text: str) -> None:
    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"task_id": task_id, "chosen_text": chosen_text}) + "\n")


def generate_chosen_outputs(
    tasks: list[dict[str, Any]],
    cache: dict[str, str],
) -> dict[str, str]:
    """Generate corrected chosen outputs for held-out tasks via OpenRouter."""
    updated_cache = dict(cache)
    to_generate = [t for t in tasks if t["task_id"] not in updated_cache]
    log.info("Generating chosen outputs for %d tasks", len(to_generate))

    for i, task in enumerate(to_generate):
        tid = task["task_id"]
        user_msg = build_user_message(task)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        chosen_text: str | None = None
        for attempt in range(1, 4):
            raw = call_openrouter(messages)
            if raw is None:
                break
            parsed = parse_rewrite(raw)
            if parsed is None:
                log.warning("%s attempt %d: unparseable response", tid, attempt)
                continue
            # Validate with scoring_evaluator
            test_task = dict(task)
            test_task["candidate_output"] = parsed
            result = evaluate_task(test_task)
            if result.get("passed_all_checks"):
                chosen_text = f"Subject: {parsed['subject']}\n\n{parsed['body']}"
                break
            log.warning(
                "%s attempt %d: evaluator failed (score %d/%d)",
                tid,
                attempt,
                result.get("score", 0),
                result.get("max_score", 0),
            )

        if chosen_text:
            updated_cache[tid] = chosen_text
            save_chosen_cache(tid, chosen_text)
            log.info("[%d/%d] %s — chosen generated", i + 1, len(to_generate), tid)
        else:
            log.warning("[%d/%d] %s — skipped (no valid rewrite)", i + 1, len(to_generate), tid)

    return updated_cache


def build_eval_pairs(
    tasks: list[dict[str, Any]],
    chosen_cache: dict[str, str],
) -> list[dict[str, Any]]:
    """Build (prompt, chosen, rejected) eval pairs for pairwise accuracy."""
    pairs = []
    for task in tasks:
        tid = task["task_id"]
        chosen_text = chosen_cache.get(tid)
        if not chosen_text:
            log.warning("No chosen output for %s — skipping", tid)
            continue
        # Score the rejected (candidate_output) with the evaluator
        eval_result = evaluate_task(task)
        pairs.append(
            {
                "task_id": tid,
                "dimension": task.get("dimension"),
                "source_mode": task.get("source_mode"),
                "difficulty": task.get("difficulty"),
                "prompt_msgs": [
                    {"role": "user", "content": build_user_message(task)}
                ],
                "chosen_text": chosen_text,
                "rejected_text": candidate_output_text(task),
                "baseline_eval": eval_result,
            }
        )
    log.info("Built %d eval pairs from %d tasks", len(pairs), len(tasks))
    return pairs


# ── Pairwise accuracy ────────────────────────────────────────────────────────


def seq_log_prob(
    model: Any,
    tokenizer: Any,
    conv: list[dict],
    prompt_len: int,
) -> float:
    ids = tokenizer.apply_chat_template(
        conv,
        tokenize=True,
        add_generation_prompt=False,
        return_tensors="pt",
    ).to(model.device)
    with torch.no_grad():
        logits = model(ids).logits  # (1, seq, vocab)
    log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
    shift_lp = log_probs[:, :-1, :]
    shift_labels = ids[:, 1:]
    token_lps = shift_lp.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
    resp_lps = token_lps[:, prompt_len - 1 :]
    resp_len = resp_lps.shape[1]
    return (resp_lps.sum() / max(resp_len, 1)).item()


def evaluate_pairs(
    model: Any,
    tokenizer: Any,
    pairs: list[dict[str, Any]],
    condition: str,
    extra_system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Run pairwise accuracy eval. Returns per-pair result dicts."""
    model.eval()
    results = []

    for pair in pairs:
        t0 = time.perf_counter()
        prompt_msgs = list(pair["prompt_msgs"])

        if extra_system_prompt:
            # Prepend a system message for the prompt-engineered condition
            prompt_msgs = [
                {"role": "system", "content": extra_system_prompt}
            ] + prompt_msgs

        prompt_ids = tokenizer.apply_chat_template(
            prompt_msgs,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(model.device)
        prompt_len = prompt_ids.shape[1]

        chosen_conv = prompt_msgs + [
            {"role": "assistant", "content": pair["chosen_text"]}
        ]
        rejected_conv = prompt_msgs + [
            {"role": "assistant", "content": pair["rejected_text"]}
        ]

        lp_chosen = seq_log_prob(model, tokenizer, chosen_conv, prompt_len)
        lp_rejected = seq_log_prob(model, tokenizer, rejected_conv, prompt_len)
        latency_ms = (time.perf_counter() - t0) * 1000

        correct = lp_chosen > lp_rejected
        results.append(
            {
                "task_id": pair["task_id"],
                "condition": condition,
                "correct": correct,
                "lp_chosen": round(lp_chosen, 6),
                "lp_rejected": round(lp_rejected, 6),
                "lp_margin": round(lp_chosen - lp_rejected, 6),
                "latency_ms": round(latency_ms, 1),
                "dimension": pair["dimension"],
                "source_mode": pair["source_mode"],
                "difficulty": pair["difficulty"],
                "baseline_eval_passed": pair["baseline_eval"].get("passed_all_checks"),
                "baseline_eval_score": pair["baseline_eval"].get("score"),
                "baseline_eval_max": pair["baseline_eval"].get("max_score"),
            }
        )

    model.train()
    return results


# ── Statistical tests ────────────────────────────────────────────────────────


def paired_bootstrap(
    base_correct: list[bool],
    trained_correct: list[bool],
    n_iter: int = BOOTSTRAP_ITERS,
    rng_seed: int = SEED,
) -> dict[str, Any]:
    """Paired bootstrap test for Delta A."""
    rng = random.Random(rng_seed)
    n = len(base_correct)
    assert len(trained_correct) == n, "Mismatched lengths"

    obs_delta = sum(trained_correct) / n - sum(base_correct) / n
    deltas = []
    for _ in range(n_iter):
        idxs = [rng.randint(0, n - 1) for _ in range(n)]
        d = sum(trained_correct[i] for i in idxs) / n - sum(
            base_correct[i] for i in idxs
        ) / n
        deltas.append(d)

    deltas_sorted = sorted(deltas)
    ci_lo = deltas_sorted[int(0.025 * n_iter)]
    ci_hi = deltas_sorted[int(0.975 * n_iter)]
    p_value = sum(1 for d in deltas if d <= 0) / n_iter

    return {
        "observed_delta": round(obs_delta, 4),
        "ci_95_lo": round(ci_lo, 4),
        "ci_95_hi": round(ci_hi, 4),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05 and ci_lo > 0,
        "n_pairs": n,
        "bootstrap_iters": n_iter,
    }


# ── Model loading ─────────────────────────────────────────────────────────────


def load_base_model(model_id: str):
    dtype = (
        torch.bfloat16
        if torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8
        else torch.float16
    )
    dtype_name = "bf16" if dtype == torch.bfloat16 else "fp16"
    log.info("Loading base model %s in %s", model_id, dtype_name)

    try:
        from unsloth import FastLanguageModel  # type: ignore

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=MAX_LEN,
            load_in_4bit=False,
            dtype=dtype,
        )
        tokenizer = getattr(tokenizer, "tokenizer", tokenizer)
        log.info("Loaded via Unsloth (no LoRA)")
        return model, tokenizer

    except ImportError:
        pass

    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype=dtype
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    log.info("Loaded via transformers (no LoRA)")
    return model, tokenizer


def load_trained_model(adapter_path: str, model_id: str):
    from peft import PeftModel  # type: ignore

    dtype = (
        torch.bfloat16
        if torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8
        else torch.float16
    )
    log.info("Loading trained model %s + LoRA from %s", model_id, adapter_path)

    try:
        from unsloth import FastLanguageModel  # type: ignore
        from transformers import AutoTokenizer

        base_model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=MAX_LEN,
            load_in_4bit=False,
            dtype=dtype,
        )
        tokenizer = getattr(tokenizer, "tokenizer", tokenizer)
        model = PeftModel.from_pretrained(base_model, adapter_path)
        log.info("Loaded via Unsloth + PeftModel")
        return model, tokenizer

    except ImportError:
        pass

    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype=dtype
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = PeftModel.from_pretrained(base_model, adapter_path)
    log.info("Loaded via transformers + PeftModel")
    return model, tokenizer


# ── Main ──────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tenacious-Bench ablation runner")
    p.add_argument(
        "--adapter",
        default="training/checkpoints/final_adapter",
        help="Path to the trained LoRA adapter directory",
    )
    p.add_argument(
        "--model",
        default="unsloth/Qwen2.5-3B-Instruct",
        help="HuggingFace backbone model ID",
    )
    p.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip OpenRouter generation; use cache only",
    )
    p.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="γ used in the training run (for labelling results)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    torch._dynamo_disable = True  # type: ignore[attr-defined]
    try:
        import torch._dynamo
        torch._dynamo.config.disable = True
    except Exception:
        pass

    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load held-out tasks ────────────────────────────────────────────────
    tasks = load_held_out()

    # ── 2. Deterministic baseline — scoring_evaluator on candidate_outputs ───
    baseline_eval_results = {t["task_id"]: evaluate_task(t) for t in tasks}
    baseline_pass_rate = sum(
        1 for r in baseline_eval_results.values() if r.get("passed_all_checks")
    ) / len(tasks)
    log.info(
        "Deterministic baseline pass rate: %.4f (%d/%d)",
        baseline_pass_rate,
        sum(1 for r in baseline_eval_results.values() if r.get("passed_all_checks")),
        len(tasks),
    )

    # ── 3. Generate / load chosen outputs ────────────────────────────────────
    chosen_cache = load_chosen_cache()
    if not args.skip_generation:
        chosen_cache = generate_chosen_outputs(tasks, chosen_cache)
    else:
        log.info("Skipping generation — using cache only (%d entries)", len(chosen_cache))

    # ── 4. Build eval pairs ───────────────────────────────────────────────────
    eval_pairs = build_eval_pairs(tasks, chosen_cache)
    if not eval_pairs:
        log.error("No eval pairs — aborting. Run without --skip-generation.")
        sys.exit(1)

    # ── 5. Base model evaluation (baseline pairwise accuracy) ────────────────
    log.info("=== Base model (no LoRA) — pairwise accuracy ===")
    base_model, tokenizer = load_base_model(args.model)
    base_results = evaluate_pairs(base_model, tokenizer, eval_pairs, condition="base")
    base_acc = sum(r["correct"] for r in base_results) / len(base_results)
    log.info("Base pairwise accuracy: %.4f", base_acc)

    # ── 6. Delta B — prompt-engineered judge (base model + system prompt) ─────
    log.info("=== Delta B — prompt-engineered judge (no LoRA) ===")
    deltaB_results = evaluate_pairs(
        base_model,
        tokenizer,
        eval_pairs,
        condition="prompt_engineered",
        extra_system_prompt=JUDGE_SYSTEM_PROMPT,
    )
    deltaB_acc = sum(r["correct"] for r in deltaB_results) / len(deltaB_results)
    log.info("Prompt-engineered pairwise accuracy: %.4f", deltaB_acc)

    # Free base model VRAM before loading trained model
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # ── 7. Trained model evaluation (Delta A) ────────────────────────────────
    adapter_path = str(ROOT / args.adapter) if not Path(args.adapter).is_absolute() else args.adapter
    log.info("=== Trained model (LoRA from %s) — pairwise accuracy ===", adapter_path)
    trained_model, _ = load_trained_model(adapter_path, args.model)
    trained_results = evaluate_pairs(
        trained_model, tokenizer, eval_pairs, condition="trained"
    )
    trained_acc = sum(r["correct"] for r in trained_results) / len(trained_results)
    log.info("Trained pairwise accuracy: %.4f", trained_acc)

    del trained_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # ── 8. Statistical tests ─────────────────────────────────────────────────
    # Build per-pair aligned lists
    task_order = [p["task_id"] for p in eval_pairs]
    base_correct_map = {r["task_id"]: r["correct"] for r in base_results}
    trained_correct_map = {r["task_id"]: r["correct"] for r in trained_results}
    deltaB_correct_map = {r["task_id"]: r["correct"] for r in deltaB_results}

    base_correct = [base_correct_map[tid] for tid in task_order]
    trained_correct = [trained_correct_map[tid] for tid in task_order]
    deltaB_correct = [deltaB_correct_map[tid] for tid in task_order]

    stat_delta_a = paired_bootstrap(base_correct, trained_correct)
    stat_delta_b = paired_bootstrap(base_correct, deltaB_correct)

    log.info(
        "Delta A: %.4f  CI=[%.4f, %.4f]  p=%.4f  significant=%s",
        stat_delta_a["observed_delta"],
        stat_delta_a["ci_95_lo"],
        stat_delta_a["ci_95_hi"],
        stat_delta_a["p_value"],
        stat_delta_a["significant"],
    )
    log.info(
        "Delta B: %.4f  CI=[%.4f, %.4f]  p=%.4f",
        stat_delta_b["observed_delta"],
        stat_delta_b["ci_95_lo"],
        stat_delta_b["ci_95_hi"],
        stat_delta_b["p_value"],
    )

    # ── 9. Cost-Pareto ────────────────────────────────────────────────────────
    base_latency_ms = sum(r["latency_ms"] for r in base_results) / len(base_results)
    trained_latency_ms = sum(r["latency_ms"] for r in trained_results) / len(trained_results)
    deltaB_latency_ms = sum(r["latency_ms"] for r in deltaB_results) / len(deltaB_results)

    # ── 10. Write outputs ─────────────────────────────────────────────────────
    ablation_summary = {
        "model_id": args.model,
        "adapter_path": adapter_path,
        "gamma": args.gamma,
        "held_out_tasks": len(tasks),
        "eval_pairs": len(eval_pairs),
        "deterministic_baseline": {
            "metric": "pass_rate (scoring_evaluator on candidate_output)",
            "pass_rate": round(baseline_pass_rate, 4),
            "passed": sum(1 for r in baseline_eval_results.values() if r.get("passed_all_checks")),
            "total": len(tasks),
        },
        "delta_a": {
            "description": "Trained judge (LoRA) vs base model — pairwise accuracy on held-out",
            "base_pairwise_acc": round(base_acc, 4),
            "trained_pairwise_acc": round(trained_acc, 4),
            "delta": round(trained_acc - base_acc, 4),
            "bootstrap_test": stat_delta_a,
        },
        "delta_b": {
            "description": "Prompt-engineered judge (base + rubric system prompt) vs base — pairwise accuracy",
            "note": "Tests whether a careful system prompt matches training; report honestly even if negative.",
            "base_pairwise_acc": round(base_acc, 4),
            "prompt_engineered_acc": round(deltaB_acc, 4),
            "delta": round(deltaB_acc - base_acc, 4),
            "bootstrap_test": stat_delta_b,
        },
        "delta_c": {
            "description": "Informational only — reuse Week 10 tau2-bench score if available.",
            "note": "tau2-bench retail NOT re-run (cost-discipline rule). Use Week 10 score as reference.",
            "week10_tau2_score": None,
        },
        "cost_pareto": {
            "base_avg_latency_ms": round(base_latency_ms, 1),
            "trained_avg_latency_ms": round(trained_latency_ms, 1),
            "prompt_engineered_avg_latency_ms": round(deltaB_latency_ms, 1),
            "latency_overhead_trained_vs_base_ms": round(trained_latency_ms - base_latency_ms, 1),
            "note": "Inference cost is $0 (Colab T4). Latency overhead is the only production cost signal.",
        },
    }

    RESULTS_PATH.write_text(json.dumps(ablation_summary, indent=2), encoding="utf-8")
    log.info("Ablation results → %s", RESULTS_PATH)

    # Held-out traces: merge all per-task results
    traces: list[dict[str, Any]] = []
    for pair in eval_pairs:
        tid = pair["task_id"]
        traces.append(
            {
                "task_id": tid,
                "dimension": pair["dimension"],
                "source_mode": pair["source_mode"],
                "difficulty": pair["difficulty"],
                "baseline_eval": baseline_eval_results.get(tid),
                "conditions": {
                    "base": base_correct_map.get(tid),
                    "trained": trained_correct_map.get(tid),
                    "prompt_engineered": deltaB_correct_map.get(tid),
                },
                "lp_margins": {
                    "base": next(
                        (r["lp_margin"] for r in base_results if r["task_id"] == tid), None
                    ),
                    "trained": next(
                        (r["lp_margin"] for r in trained_results if r["task_id"] == tid), None
                    ),
                    "prompt_engineered": next(
                        (r["lp_margin"] for r in deltaB_results if r["task_id"] == tid), None
                    ),
                },
                "latency_ms": {
                    "base": next(
                        (r["latency_ms"] for r in base_results if r["task_id"] == tid), None
                    ),
                    "trained": next(
                        (r["latency_ms"] for r in trained_results if r["task_id"] == tid), None
                    ),
                },
            }
        )

    with open(TRACES_PATH, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace) + "\n")
    log.info("Held-out traces → %s (%d records)", TRACES_PATH, len(traces))

    stats_output = {
        "delta_a_bootstrap": stat_delta_a,
        "delta_b_bootstrap": stat_delta_b,
        "seed": SEED,
        "bootstrap_iters": BOOTSTRAP_ITERS,
    }
    STATS_PATH.write_text(json.dumps(stats_output, indent=2), encoding="utf-8")
    log.info("Statistical tests → %s", STATS_PATH)

    log.info("=== Ablation summary ===")
    log.info("Deterministic baseline pass rate:  %.4f", baseline_pass_rate)
    log.info("Base pairwise acc:                 %.4f", base_acc)
    log.info("Trained pairwise acc (Delta A):    %.4f  (%+.4f)", trained_acc, trained_acc - base_acc)
    log.info("Prompt-eng pairwise acc (Delta B): %.4f  (%+.4f)", deltaB_acc, deltaB_acc - base_acc)
    log.info(
        "Delta A significant: %s  (p=%.4f, CI=[%.4f, %.4f])",
        stat_delta_a["significant"],
        stat_delta_a["p_value"],
        stat_delta_a["ci_95_lo"],
        stat_delta_a["ci_95_hi"],
    )
    log.info("Done.")


if __name__ == "__main__":
    main()
