"""
training/train_judge.py

SimPO preference fine-tuning for the Tenacious-Bench judge.

Backbone: unsloth/Qwen2.5-3B-Instruct  (standard transformer, fp16-safe on T4; Qwen3.5-4B
  requires bf16 via GatedDeltaNet hybrid layers and is Ampere+-only)
  — override via --model (e.g. unsloth/Qwen2.5-7B-Instruct on A100)
Algorithm: SimPO (Meng et al., NeurIPS 2024) via TRL CPOTrainer (loss_type="simpo")
LoRA: rank=16, alpha=32, 16-bit (NO 4-bit quantization — per Week 11 brief)
Precision: fp16 on T4, bf16 on Ampere+ (auto-detected)

Designed to run on Colab T4. Unsloth is used when available for faster LoRA
kernels; falls back to standard transformers + PEFT otherwise.

Usage (Colab):
  # install first — see requirements.txt
  python training/train_judge.py [--gamma 2.5] [--hf-repo your-hf-user/tenacious-judge-qwen3.5-1.7b]

Ablation variant:
  python training/train_judge.py --gamma 1.5

Outputs:
  training/checkpoints/           best checkpoint (by dev pairwise accuracy)
  training/training_run.log       loss curve + pairwise-accuracy evals every 100 steps
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch._dynamo
# T4 (sm75) cannot JIT-compile Triton kernels — disable dynamo to avoid the
# "no kernel image" crash while preserving Unsloth's pre-compiled CUDA kernels.
torch._dynamo.config.disable = True
from datasets import Dataset

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "training_data" / "train.jsonl"
DEV_PATH = ROOT / "training_data" / "dev.jsonl"
CKPT_DIR = ROOT / "training" / "checkpoints"
LOG_PATH = ROOT / "training" / "training_run.log"

# ── Hyperparameters ──────────────────────────────────────────────────────────

# Qwen3.5-4B has GatedDeltaNet layers that require bf16 (Ampere+) — incompatible with T4.
# Qwen2.5-3B-Instruct is a standard transformer that runs in fp16 on T4 with Unsloth.
MODEL_ID = "unsloth/Qwen2.5-3B-Instruct"
BETA = 2.0  # SimPO β (reward scaling)
# γ is passed via CLI --gamma; default 1.0 → γ/β = 0.5, the SimPO paper's
# Mistral/Llama best-region (Meng et al. 2024, Table 3). γ=1.5 → γ/β=0.75 is the
# upper-edge ablation variant. TRL's CPOConfig.simpo_gamma takes γ/β directly.

LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.0
LORA_TARGETS = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

SEED = 42
BATCH_SIZE = 1  # per-device; T4 memory constraint
GRAD_ACCUM = 8  # effective batch = 8
LR = 5e-5
WARMUP_RATIO = 0.1
NUM_EPOCHS = 2
MAX_LEN = 512  # tokens; prompts are ≤200 tokens in this dataset
MAX_PROMPT_LEN = 256
EVAL_STEPS = 100
SAVE_STEPS = 100
DEV_EVAL_LIMIT = 100  # pairs to score per pairwise-accuracy check

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── Data loading ─────────────────────────────────────────────────────────────


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def to_hf_dataset(records: list[dict[str, Any]]) -> Dataset:
    """Convert JSONL records to a HuggingFace Dataset.

    TRL SimPOTrainer expects:
      prompt:   list[dict]  — chat messages up to (not including) the response
      chosen:   list[dict]  — the preferred response as a single assistant message
      rejected: list[dict]  — the dispreferred response as a single assistant message
    """
    return Dataset.from_list(
        [
            {
                "prompt": r["prompt"],
                "chosen": r["chosen"],
                "rejected": r["rejected"],
            }
            for r in records
        ]
    )


# ── Model loading ─────────────────────────────────────────────────────────────


def load_model_and_tokenizer(model_id: str, lora_rank: int, lora_alpha: int):
    """Load model with 16-bit LoRA (no 4-bit quantization per Week 11 brief).

    Prefers Unsloth (~2x faster, less VRAM via fused kernels); falls back to
    standard transformers + PEFT. Precision is fp16 on T4, bf16 on Ampere+.
    """
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    dtype_name = "bf16" if dtype == torch.bfloat16 else "fp16"

    try:
        from unsloth import FastLanguageModel  # type: ignore

        log.info("Unsloth found — loading in 16-bit %s", dtype_name)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=MAX_LEN,
            load_in_4bit=False,  # 16-bit LoRA per Week 11 brief
            dtype=dtype,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=LORA_DROPOUT,
            target_modules=LORA_TARGETS,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=SEED,
        )
        log.info("LoRA applied via Unsloth (rank=%d, alpha=%d)", lora_rank, lora_alpha)
        return model, tokenizer

    except ImportError:
        log.warning(
            "Unsloth not available — falling back to standard transformers + PEFT"
        )

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model, TaskType

    log.info("Loading backbone in 16-bit %s (no quantization)", dtype_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype=dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=LORA_TARGETS,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    log.info("LoRA applied via PEFT (rank=%d, alpha=%d)", lora_rank, lora_alpha)
    model.print_trainable_parameters()
    return model, tokenizer


# ── Pairwise accuracy evaluation ──────────────────────────────────────────────


def compute_pairwise_accuracy(
    model,
    tokenizer,
    dev_records: list[dict[str, Any]],
    limit: int = DEV_EVAL_LIMIT,
) -> float:
    """Fraction of dev pairs where length-normalised log P(chosen) > log P(rejected).

    This is the direct in-training proxy for SimPO optimisation success. Full
    scoring_evaluator.py agreement is measured in the ablation step (Day 6).
    """
    model.eval()
    correct = 0
    total = 0

    records = dev_records[:limit]
    with torch.no_grad():
        for rec in records:
            prompt_msgs = rec["prompt"]
            chosen_msgs = rec["chosen"]
            rejected_msgs = rec["rejected"]

            # Build full conversations
            chosen_conv = prompt_msgs + chosen_msgs
            rejected_conv = prompt_msgs + rejected_msgs

            # Tokenize
            chosen_ids = tokenizer.apply_chat_template(
                chosen_conv,
                tokenize=True,
                add_generation_prompt=False,
                return_tensors="pt",
            ).to(model.device)
            rejected_ids = tokenizer.apply_chat_template(
                rejected_conv,
                tokenize=True,
                add_generation_prompt=False,
                return_tensors="pt",
            ).to(model.device)

            # Log P of response tokens only (mask prompt tokens)
            prompt_ids = tokenizer.apply_chat_template(
                prompt_msgs,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
            ).to(model.device)
            prompt_len = prompt_ids.shape[1]

            def seq_log_prob(input_ids: torch.Tensor) -> float:
                logits = model(input_ids).logits  # (1, seq, vocab)
                log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
                # Shift: predict token i from position i-1
                shift_log_probs = log_probs[:, :-1, :]  # (1, seq-1, vocab)
                shift_labels = input_ids[:, 1:]  # (1, seq-1)
                token_lps = shift_log_probs.gather(
                    -1, shift_labels.unsqueeze(-1)
                ).squeeze(
                    -1
                )  # (1, seq-1)
                # Sum only over response tokens
                resp_lps = token_lps[:, prompt_len - 1 :]
                resp_len = resp_lps.shape[1]
                return (resp_lps.sum() / max(resp_len, 1)).item()

            lp_chosen = seq_log_prob(chosen_ids)
            lp_rejected = seq_log_prob(rejected_ids)

            if lp_chosen > lp_rejected:
                correct += 1
            total += 1

    model.train()
    return correct / total if total > 0 else 0.0


# ── Main ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SimPO judge fine-tuning")
    p.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="SimPO target reward margin γ (default 1.0 → γ/β=0.5; ablation 1.5 → γ/β=0.75)",
    )
    p.add_argument(
        "--model", default=MODEL_ID, help="HuggingFace model ID for the backbone"
    )
    p.add_argument(
        "--hf-repo",
        default="",
        help="HuggingFace repo to push LoRA adapter after training (optional)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and model, verify shapes, exit without training",
    )
    p.add_argument(
        "--platform",
        default="colab",
        choices=["colab", "runpod", "other"],
        help="Compute platform (colab=free; runpod=~$0.34/hr; other=use --hourly-rate)",
    )
    p.add_argument(
        "--hourly-rate",
        type=float,
        default=None,
        help="USD/hr for the GPU (auto: 0.0 for colab, 0.34 for runpod)",
    )
    return p.parse_args()


# Platform hourly rates (USD) — update if pricing changes
_PLATFORM_RATES = {"colab": 0.0, "runpod": 0.34, "other": 0.0}


def append_cost_record(
    platform: str,
    hourly_rate: float,
    wall_time_min: float,
    model_id: str,
    train_pairs: int,
    gamma: float,
) -> None:
    """Append one training-cost entry to training_data/build_cost_log.json."""
    import datetime

    cost_usd = round(wall_time_min / 60 * hourly_rate, 4)
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "bucket": "training_compute",
        "platform": platform,
        "hourly_rate_usd": hourly_rate,
        "wall_time_min": round(wall_time_min, 2),
        "cost_usd": cost_usd,
        "model_id": model_id,
        "train_pairs": train_pairs,
        "gamma": gamma,
        "note": f"SimPO LoRA fine-tune — {train_pairs} pairs, γ={gamma}",
    }

    cost_log_path = ROOT / "training_data" / "build_cost_log.json"
    existing: list[dict] = []
    if cost_log_path.exists():
        try:
            existing = json.loads(cost_log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            existing = []

    existing.append(record)
    cost_log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    log.info(
        "Cost record appended → %s  (platform=%s, %.1f min, $%.4f)",
        cost_log_path,
        platform,
        wall_time_min,
        cost_usd,
    )

def main() -> None:
    args = parse_args()
    gamma = args.gamma
    gamma_beta_ratio = gamma / BETA
    hourly_rate = (
        args.hourly_rate
        if args.hourly_rate is not None
        else _PLATFORM_RATES[args.platform]
    )


    log.info("=" * 60)
    log.info("Tenacious-Bench SimPO Judge Training")
    log.info(
        "model=%s  β=%.1f  γ=%.1f  γ/β=%.3f", args.model, BETA, gamma, gamma_beta_ratio
    )
    log.info("LoRA rank=%d  alpha=%d  seed=%d", LORA_RANK, LORA_ALPHA, SEED)
    log.info("platform=%s  hourly_rate=$%.2f/hr", args.platform, hourly_rate)
    log.info("train=%s  dev=%s", TRAIN_PATH, DEV_PATH)
    log.info("=" * 60)

    # ── Load data ────────────────────────────────────────────────────────────
    train_records = load_jsonl(TRAIN_PATH)
    dev_records = load_jsonl(DEV_PATH)
    log.info(
        "Loaded %d train pairs, %d dev pairs", len(train_records), len(dev_records)
    )

    train_ds = to_hf_dataset(train_records)
    eval_ds = to_hf_dataset(dev_records)

    # ── Load model ───────────────────────────────────────────────────────────
    model, tokenizer = load_model_and_tokenizer(args.model, LORA_RANK, LORA_ALPHA)
    tokenizer = getattr(tokenizer, "tokenizer", tokenizer)  # Bypass vision processor

    if args.dry_run:
        log.info("Dry-run complete — model and data loaded, exiting without training")
        return

    # ── SimPO config ─────────────────────────────────────────────────────────
    try:
        from trl import CPOConfig, CPOTrainer
    except ImportError as e:
        log.error("TRL CPOTrainer not available: %s", e)
        log.error("Install with: pip install trl>=0.9.0")
        sys.exit(1)

    use_bf16 = torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8
    use_fp16 = not use_bf16

    simpo_config = CPOConfig(
        output_dir=str(CKPT_DIR),
        # SimPO-specific
        loss_type="simpo",
        cpo_alpha=0.0,
        beta=BETA,
        simpo_gamma=gamma_beta_ratio,
        # Training
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        warmup_ratio=WARMUP_RATIO,
        lr_scheduler_type="cosine",
        # Precision — T4 uses fp16; Ampere+ uses bf16
        bf16=use_bf16,
        fp16=use_fp16,
        # Evaluation
        eval_strategy="steps",
        eval_steps=EVAL_STEPS,
        # Logging
        logging_steps=10,
        report_to="none",
        # Checkpointing — save by eval loss, keep best
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        save_total_limit=2,
        # Data
        max_length=MAX_LEN,
        max_prompt_length=MAX_PROMPT_LEN,
        # Reproducibility
        seed=SEED,
        data_seed=SEED,
        # Misc
        remove_unused_columns=False,
        dataloader_num_workers=0,
    )

    trainer = CPOTrainer(
        model=model,
        args=simpo_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=getattr(tokenizer, "tokenizer", tokenizer),
    )

    # ── Baseline pairwise accuracy before training ────────────────────────────
    log.info("Computing baseline pairwise accuracy on %d dev pairs...", DEV_EVAL_LIMIT)
    baseline_acc = compute_pairwise_accuracy(model, tokenizer, dev_records)
    log.info("Baseline pairwise accuracy: %.4f", baseline_acc)

    # ── Train ────────────────────────────────────────────────────────────────
    log.info(
        "Starting SimPO training  (γ=%.1f, β=%.1f, γ/β=%.3f)",
        gamma,
        BETA,
        gamma_beta_ratio,
    )
    t0 = time.time()
    train_result = trainer.train()
    elapsed = time.time() - t0

    log.info("Training complete in %.1f min", elapsed / 60)
    log.info(
        "train/loss=%.4f  train/runtime=%.1fs", train_result.training_loss, elapsed
    )
    trainer.log_metrics("train", train_result.metrics)
    trainer.save_metrics("train", train_result.metrics)

    # ── Post-training pairwise accuracy ───────────────────────────────────────
    log.info(
        "Computing post-training pairwise accuracy on %d dev pairs...", DEV_EVAL_LIMIT
    )
    final_acc = compute_pairwise_accuracy(model, tokenizer, dev_records)
    log.info(
        "Post-training pairwise accuracy: %.4f  (delta: %+.4f)",
        final_acc,
        final_acc - baseline_acc,
    )

    # ── Save adapter ──────────────────────────────────────────────────────────
    adapter_path = CKPT_DIR / "final_adapter"
    trainer.save_model(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    log.info("LoRA adapter saved to %s", adapter_path)

    # Write a summary record for the ablation step
    cost_usd = round(elapsed / 3600 * hourly_rate, 4)
    summary = {
        "model_id": args.model,
        "beta": BETA,
        "gamma": gamma,
        "gamma_beta_ratio": gamma_beta_ratio,
        "lora_rank": LORA_RANK,
        "lora_alpha": LORA_ALPHA,
        "seed": SEED,
        "train_pairs": len(train_records),
        "dev_pairs": len(dev_records),
        "num_epochs": NUM_EPOCHS,
        "effective_batch_size": BATCH_SIZE * GRAD_ACCUM,
        "learning_rate": LR,
        "training_loss": train_result.training_loss,
        "baseline_pairwise_acc": baseline_acc,
        "final_pairwise_acc": final_acc,
        "pairwise_acc_delta": final_acc - baseline_acc,
        "wall_time_min": round(elapsed / 60, 2),
        "platform": args.platform,
        "hourly_rate_usd": hourly_rate,
        "cost_usd": cost_usd,
    }
    summary_path = ROOT / "training" / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Training summary -> %s", summary_path)

    # ── Cost tracking ─────────────────────────────────────────────────────────
    append_cost_record(
        platform=args.platform,
        hourly_rate=hourly_rate,
        wall_time_min=elapsed / 60,
        model_id=args.model,
        train_pairs=len(train_records),
        gamma=gamma,
    )

    # ── Optional HF push ──────────────────────────────────────────────────────
    if args.hf_repo:
        log.info("Pushing LoRA adapter to HF Hub: %s", args.hf_repo)
        try:
            model.push_to_hub(args.hf_repo, private=True)
            tokenizer.push_to_hub(args.hf_repo, private=True)
            log.info("Pushed adapter to %s (private)", args.hf_repo)
        except Exception as exc:
            log.error("HF push failed: %s", exc)

    log.info("Done.")


if __name__ == "__main__":
    main()
