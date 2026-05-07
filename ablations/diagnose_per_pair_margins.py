"""
ablations/diagnose_per_pair_margins.py

Per-pair flip diagnostic answering Amir's sharpening questions #1, #2, #4,
extended (post Day-3 paired research) with the per-pair gradient mechanics
from his explainer.

For each pair in dev (first 100) or held-out:
  - Compute base-model length-normalized log-prob margin M (chosen vs rejected)
  - Compute trained-adapter margin M_trained
  - Compute SimPO margin slack s = β·M − γ at the base model (the regime each
    pair sat in at step zero of training)
  - Compute the per-pair gradient strength σ(−s) at step zero (Amir's
    derivation: |∂L/∂θ| ∝ σ(−s); see explainer "The Mechanism: Per-Pair
    Gradient Decay")
  - Bucket each pair by gradient regime (real signal / fading / silent)
  - Identify flipped pairs and cross-reference with adversarial probe IDs

Usage (Colab T4, after training in the same session):
    python ablations/diagnose_per_pair_margins.py \\
        --pairs training_data/dev.jsonl \\
        --limit 100 \\
        --adapter /content/tenacious-bench/training/checkpoints/final_adapter \\
        --output ablations/per_pair_diagnostic_dev100.jsonl

Usage (loading adapter from HuggingFace Hub):
    python ablations/diagnose_per_pair_margins.py \\
        --pairs training_data/dev.jsonl \\
        --limit 100 \\
        --adapter your-hf-user/tenacious-bench-judge \\
        --output ablations/per_pair_diagnostic_dev100.jsonl

Outputs a JSONL with one record per pair (task_id, base_margin, base_slack,
base_grad_strength, trained_margin, base_correct, trained_correct, status,
adversarial_probe) and prints a flip summary plus the slack-bucket histogram.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import math

import torch


ADVERSARIAL_PROBES = ("P007", "P011", "P027")

# SimPO hyperparameters used in this run (see training/train_judge.py)
SIMPO_BETA = 2.0
SIMPO_GAMMA = 1.5  # absolute; γ/β = 0.75


def margin_slack(margin: float, beta: float = SIMPO_BETA, gamma: float = SIMPO_GAMMA) -> float:
    """SimPO margin slack s = β·M − γ. Per Amir's explainer derivation."""
    return beta * margin - gamma


def gradient_strength(slack: float) -> float:
    """Per-pair gradient strength σ(−s). Amir's explainer: |∂L/∂θ| ∝ σ(−s)."""
    # Numerically stable sigmoid of -slack
    if slack >= 0:
        z = math.exp(-slack)
        return z / (1.0 + z)
    return 1.0 / (1.0 + math.exp(slack))


def slack_bucket(slack: float) -> str:
    """Three-bucket regime classifier from Amir's explainer."""
    if slack < 0:
        return "below_gamma_real_signal"  # σ(-s) > 0.5
    if slack < 2.0:
        return "moderate_fading"           # σ(-s) in (0.12, 0.5)
    return "silent_passenger"              # σ(-s) < 0.12


def load_pairs(path: Path, limit: int | None) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if limit is not None:
        records = records[:limit]
    return records


def _to_tensor(result):
    """apply_chat_template may return a Tensor or a BatchEncoding depending on
    transformers version. Normalize to a 2D LongTensor of input_ids."""
    if hasattr(result, "input_ids"):
        return result.input_ids
    if isinstance(result, dict) and "input_ids" in result:
        return result["input_ids"]
    return result  # already a Tensor


def length_normalized_margin(model, tokenizer, prompt_msgs, chosen_msgs, rejected_msgs) -> tuple[float, float]:
    """Returns (lp_chosen_normalized, lp_rejected_normalized) for one pair."""
    device = model.device

    def seq_lp(full_msgs):
        full_ids = _to_tensor(tokenizer.apply_chat_template(
            full_msgs, tokenize=True, add_generation_prompt=False, return_tensors="pt"
        )).to(device)
        prompt_ids = _to_tensor(tokenizer.apply_chat_template(
            prompt_msgs, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        )).to(device)
        prompt_len = prompt_ids.shape[1]

        with torch.no_grad():
            logits = model(full_ids).logits
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        shift_lp = log_probs[:, :-1, :]
        shift_labels = full_ids[:, 1:]
        token_lps = shift_lp.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
        resp_lps = token_lps[:, prompt_len - 1:]
        resp_len = max(resp_lps.shape[1], 1)
        return (resp_lps.sum() / resp_len).item()

    return seq_lp(prompt_msgs + chosen_msgs), seq_lp(prompt_msgs + rejected_msgs)


def score_records(model, tokenizer, records: list[dict]) -> list[dict]:
    out = []
    for rec in records:
        lp_chosen, lp_rejected = length_normalized_margin(
            model, tokenizer, rec["prompt"], rec["chosen"], rec["rejected"]
        )
        margin = lp_chosen - lp_rejected
        out.append({
            "task_id": rec.get("_meta", {}).get("task_id", "<no_task_id>"),
            "lp_chosen": lp_chosen,
            "lp_rejected": lp_rejected,
            "margin": margin,
            "correct": lp_chosen > lp_rejected,
        })
    return out


def adversarial_label(task_id: str) -> str | None:
    for probe in ADVERSARIAL_PROBES:
        if probe.lower() in task_id.lower():
            return probe
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True, help="JSONL with prompt/chosen/rejected and _meta.task_id")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--base-model", default="unsloth/Qwen2.5-3B-Instruct")
    ap.add_argument("--adapter", required=True, help="Local path or HF repo of the trained LoRA adapter")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print(f"Loading base model: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model, device_map="auto", torch_dtype=torch.float16
    )
    base.eval()

    pairs = load_pairs(Path(args.pairs), args.limit)
    print(f"Scoring {len(pairs)} pairs with base model...")
    base_results = score_records(base, tokenizer, pairs)

    print(f"Loading adapter: {args.adapter}")
    trained = PeftModel.from_pretrained(base, args.adapter)
    trained.eval()
    print(f"Scoring {len(pairs)} pairs with trained adapter...")
    trained_results = score_records(trained, tokenizer, pairs)

    combined = []
    flips = {"flipped_to_correct": [], "flipped_to_wrong": [], "stayed_correct": [], "stayed_wrong": []}
    for b, t in zip(base_results, trained_results):
        assert b["task_id"] == t["task_id"]
        s_base = margin_slack(b["margin"])
        rec = {
            "task_id": b["task_id"],
            "adversarial_probe": adversarial_label(b["task_id"]),
            "base_margin": b["margin"],
            "base_slack": s_base,
            "base_grad_strength": gradient_strength(s_base),
            "slack_bucket": slack_bucket(s_base),
            "trained_margin": t["margin"],
            "margin_delta": t["margin"] - b["margin"],
            "base_correct": b["correct"],
            "trained_correct": t["correct"],
        }
        if b["correct"] and t["correct"]:
            rec["status"] = "stayed_correct"
        elif not b["correct"] and t["correct"]:
            rec["status"] = "flipped_to_correct"
        elif b["correct"] and not t["correct"]:
            rec["status"] = "flipped_to_wrong"
        else:
            rec["status"] = "stayed_wrong"
        flips[rec["status"]].append(rec)
        combined.append(rec)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in combined:
            f.write(json.dumps(rec) + "\n")
    print(f"\nPer-pair results written to: {args.output}")

    # Summary
    n = len(combined)
    base_acc = sum(r["base_correct"] for r in combined) / n
    trained_acc = sum(r["trained_correct"] for r in combined) / n
    print(f"\n=== Summary (n={n}) ===")
    print(f"Base accuracy:    {base_acc:.4f} ({sum(r['base_correct'] for r in combined)}/{n})")
    print(f"Trained accuracy: {trained_acc:.4f} ({sum(r['trained_correct'] for r in combined)}/{n})")
    print(f"  flipped_to_correct: {len(flips['flipped_to_correct'])}")
    print(f"  flipped_to_wrong:   {len(flips['flipped_to_wrong'])}")
    print(f"  stayed_correct:     {len(flips['stayed_correct'])}")
    print(f"  stayed_wrong:       {len(flips['stayed_wrong'])}")

    print("\n=== Pairs that flipped to correct ===")
    for rec in flips["flipped_to_correct"]:
        probe = rec["adversarial_probe"] or "(non-adversarial)"
        print(f"  {rec['task_id']:40s}  probe={probe:5s}  base_margin={rec['base_margin']:+.3f}  trained_margin={rec['trained_margin']:+.3f}")

    print("\n=== Pairs that regressed (trained got wrong, base got right) ===")
    for rec in flips["flipped_to_wrong"]:
        probe = rec["adversarial_probe"] or "(non-adversarial)"
        print(f"  {rec['task_id']:40s}  probe={probe:5s}  base_margin={rec['base_margin']:+.3f}  trained_margin={rec['trained_margin']:+.3f}")

    # Slack-bucket histogram (per Amir's gradient decay derivation)
    bucket_counts = {"below_gamma_real_signal": 0, "moderate_fading": 0, "silent_passenger": 0}
    bucket_adv_counts = {"below_gamma_real_signal": 0, "moderate_fading": 0, "silent_passenger": 0}
    for r in combined:
        bucket_counts[r["slack_bucket"]] += 1
        if r["adversarial_probe"]:
            bucket_adv_counts[r["slack_bucket"]] += 1
    print(f"\n=== Base-model slack distribution (β={SIMPO_BETA}, γ={SIMPO_GAMMA}; from Amir's explainer) ===")
    print(f"  s < 0  (real signal, σ(-s) > 0.5):       {bucket_counts['below_gamma_real_signal']:3d} pairs  | adversarial: {bucket_adv_counts['below_gamma_real_signal']}")
    print(f"  0 ≤ s < 2 (fading, σ(-s) ∈ (0.12, 0.5)): {bucket_counts['moderate_fading']:3d} pairs  | adversarial: {bucket_adv_counts['moderate_fading']}")
    print(f"  s ≥ 2  (silent passenger, σ(-s) < 0.12): {bucket_counts['silent_passenger']:3d} pairs  | adversarial: {bucket_adv_counts['silent_passenger']}")
    if bucket_adv_counts["below_gamma_real_signal"] > 0:
        print("  → Verdict: adversarial pairs had real gradient signal at start of training.")
    else:
        print("  → Verdict: NO adversarial pair started in the unsaturated regime; training never had signal on the cases the bench was built for.")

    # Adversarial breakdown
    adv_total = sum(1 for r in combined if r["adversarial_probe"])
    adv_base_correct = sum(1 for r in combined if r["adversarial_probe"] and r["base_correct"])
    adv_trained_correct = sum(1 for r in combined if r["adversarial_probe"] and r["trained_correct"])
    print(f"\n=== Adversarial subset (P007/P011/P027) ===")
    print(f"Total adversarial pairs in window: {adv_total}")
    print(f"  Base correct on adversarial:    {adv_base_correct}/{adv_total}")
    print(f"  Trained correct on adversarial: {adv_trained_correct}/{adv_total}")
    print(f"  Lift on adversarial:            {adv_trained_correct - adv_base_correct:+d}")


if __name__ == "__main__":
    main()
