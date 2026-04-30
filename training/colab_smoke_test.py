"""
training/colab_smoke_test.py

Day-0 smoke test — run this on Colab T4 BEFORE the real training run.
Verifies: model loads in 16-bit, LoRA attaches, SimPOTrainer runs 1 step,
adapter saves, and (optionally) pushes to HuggingFace.

Expected wall time: 8–15 min on T4 (most of that is kernel compile on first run).

Usage (Colab cell):
  !python training/colab_smoke_test.py --hf-repo your-username/tenacious-smoke-test

If it completes without error and you see the adapter in your HF repo,
you are cleared to run the real training script.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import torch

# ── Smoke-test config ─────────────────────────────────────────────────────────

# Verify exact model ID from https://unsloth.ai/docs/models/qwen3.5/fine-tune
# before running. Override with --model if it differs.
DEFAULT_MODEL = "unsloth/Qwen3.5-1.7B-Instruct"

LORA_RANK    = 16
LORA_ALPHA   = 32
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj",
                 "gate_proj", "up_proj", "down_proj"]
MAX_LEN      = 256
SEED         = 42

# 5 dummy preference pairs — generic enough to load without real data
DUMMY_PAIRS = [
    {
        "prompt":   [{"role": "user", "content": f"Draft outreach for prospect {i}."}],
        "chosen":   [{"role": "assistant",
                      "content": f"Hi, I saw your recent Series B — exciting milestone. "
                                 f"We've helped similar-stage teams scale engineering. "
                                 f"Worth a 20-min call? #{i}"}],
        "rejected": [{"role": "assistant",
                      "content": f"Hi, our bench is top-notch and proven. "
                                 f"We definitely have the engineers you need. Let's talk! #{i}"}],
    }
    for i in range(5)
]


def setup_hf_auth(hf_repo: str) -> None:
    """Authenticate with HuggingFace. Only needed when --hf-repo is set.

    Priority order:
      1. HF_TOKEN env var (set in Colab Secrets via the lock icon in the sidebar)
      2. HUGGING_FACE_HUB_TOKEN env var (legacy name)
      3. huggingface_hub.notebook_login() — interactive prompt (last resort)

    In Colab: open the lock icon (Secrets) → add secret named HF_TOKEN with your
    write-access token from https://huggingface.co/settings/tokens
    """
    if not hf_repo:
        return  # no push requested, no auth needed

    from huggingface_hub import HfApi, login

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    if token:
        login(token=token, add_to_git_credential=False)
        print(f"[smoke] HF auth: token loaded from environment")
    else:
        # Try Colab Secrets (available when running in Colab)
        try:
            from google.colab import userdata  # type: ignore
            token = userdata.get("HF_TOKEN")
            if token:
                login(token=token, add_to_git_credential=False)
                print("[smoke] HF auth: token loaded from Colab Secrets")
                return
        except (ImportError, Exception):
            pass

        # Fall back to interactive login
        print("[smoke] No HF_TOKEN found — launching interactive login")
        print("        (To avoid this: add HF_TOKEN to Colab Secrets via the lock icon)")
        try:
            from huggingface_hub import notebook_login  # type: ignore
            notebook_login()
        except Exception:
            login()  # CLI login fallback

    # Verify the token has write access
    try:
        api = HfApi()
        whoami = api.whoami()
        print(f"[smoke] HF auth verified — logged in as: {whoami['name']}")
    except Exception as exc:
        print(f"[smoke] FAIL: HF auth check failed: {exc}")
        print("        Check that your token has 'write' scope at https://huggingface.co/settings/tokens")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Colab Day-0 smoke test")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="HuggingFace / Unsloth model ID to test")
    p.add_argument("--hf-repo", default="",
                   help="HF repo to push smoke-test adapter (optional, confirms HF auth)")
    return p.parse_args()


def load_model_and_tokenizer(model_id: str):
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    dtype_name = "bf16" if dtype == torch.bfloat16 else "fp16"
    print(f"[smoke] Loading {model_id} in 16-bit {dtype_name} (no 4-bit quantization)")

    try:
        from unsloth import FastLanguageModel  # type: ignore
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=MAX_LEN,
            load_in_4bit=False,
            dtype=dtype,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=LORA_RANK,
            lora_alpha=LORA_ALPHA,
            lora_dropout=0.0,
            target_modules=LORA_TARGETS,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=SEED,
        )
        print("[smoke] Unsloth LoRA attached")
        return model, tokenizer, dtype

    except ImportError:
        print("[smoke] Unsloth not found — falling back to transformers + PEFT")

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model, TaskType

    model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype=dtype
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_cfg = LoraConfig(
        r=LORA_RANK, lora_alpha=LORA_ALPHA,
        target_modules=LORA_TARGETS, lora_dropout=0.0,
        bias="none", task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_cfg)
    print("[smoke] PEFT LoRA attached")
    return model, tokenizer, dtype


def main() -> None:
    args = parse_args()

    # Authenticate with HF early so a bad token fails fast, before the 10-min model load
    setup_hf_auth(args.hf_repo)

    if not torch.cuda.is_available():
        print("[smoke] WARNING: no GPU detected — this will be very slow on CPU")

    # ── Load model ───────────────────────────────────────────────────────────
    model, tokenizer, dtype = load_model_and_tokenizer(args.model)
    print(f"[smoke] Model loaded. Trainable params: ", end="")
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"{trainable:,} / {total:,}")

    # ── Build dummy dataset ──────────────────────────────────────────────────
    from datasets import Dataset
    ds = Dataset.from_list(DUMMY_PAIRS)
    print(f"[smoke] Dummy dataset: {len(ds)} pairs")

    # ── 1-step SimPO training ────────────────────────────────────────────────
    try:
        from trl import SimPOConfig, SimPOTrainer
    except ImportError:
        print("[smoke] FAIL: trl.SimPOTrainer not found. Install trl>=0.9.0")
        sys.exit(1)

    use_bf16 = (dtype == torch.bfloat16)

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = SimPOConfig(
            output_dir=tmpdir,
            beta=2.0,
            gamma_beta_ratio=2.5 / 2.0,
            num_train_epochs=1,
            max_steps=1,                    # single step — just prove it works
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=5e-5,
            bf16=use_bf16,
            fp16=not use_bf16,
            logging_steps=1,
            report_to="none",
            save_strategy="no",
            max_length=MAX_LEN,
            max_prompt_length=128,
            seed=SEED,
            remove_unused_columns=False,
            dataloader_num_workers=0,
        )

        trainer = SimPOTrainer(
            model=model,
            args=cfg,
            train_dataset=ds,
            processing_class=tokenizer,
        )

        print("[smoke] Running 1-step SimPO training...")
        trainer.train()
        print("[smoke] Training step completed")

        # Save adapter to a temp dir first
        adapter_dir = Path(tmpdir) / "smoke_adapter"
        model.save_pretrained(str(adapter_dir))
        tokenizer.save_pretrained(str(adapter_dir))
        print(f"[smoke] Adapter saved to {adapter_dir}")

        # ── Optional HF push ─────────────────────────────────────────────────
        if args.hf_repo:
            print(f"[smoke] Pushing adapter to HuggingFace: {args.hf_repo}")
            try:
                model.push_to_hub(args.hf_repo, private=True)
                tokenizer.push_to_hub(args.hf_repo, private=True)
                print(f"[smoke] Pushed to https://huggingface.co/{args.hf_repo}")
            except Exception as exc:
                print(f"[smoke] HF push failed: {exc}")
                sys.exit(1)

    print()
    print("=" * 60)
    print("[smoke] ALL CHECKS PASSED")
    print(f"  Model:    {args.model}")
    print(f"  Dtype:    {'bf16' if use_bf16 else 'fp16'}")
    print(f"  LoRA:     rank={LORA_RANK}, alpha={LORA_ALPHA}")
    print(f"  SimPO:    1 step completed")
    if args.hf_repo:
        print(f"  HF push:  https://huggingface.co/{args.hf_repo}")
    print("=" * 60)
    print()
    print("You are cleared to run the real training:")
    print("  python training/train_judge.py --hf-repo your-username/tenacious-judge-qwen3.5")


if __name__ == "__main__":
    main()
