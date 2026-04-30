"""
training/colab_smoke_test.py

Day-0 smoke test — run this on Colab T4 BEFORE the real training run.
Verifies: model loads in 16-bit, LoRA attaches, CPOTrainer (SimPO) runs 1 step,
adapter saves, and (optionally) pushes to HuggingFace.

Expected wall time: 6–12 min on T4.

Usage (Colab cell):
  !python training/colab_smoke_test.py --hf-repo your-username/tenacious-smoke-test
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import torch

# ── Config ─────────────────────────────────────────────────────────

# Stable + T4-friendly model (avoids float32 fallback)
DEFAULT_MODEL = "unsloth/Qwen3.5-4B"

LORA_RANK = 16
LORA_ALPHA = 32
LORA_TARGETS = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

MAX_LEN = 256
SEED = 42

# Dummy preference pairs
DUMMY_PAIRS = [
    {
        "prompt": [{"role": "user", "content": f"Draft outreach for prospect {i}."}],
        "chosen": [
            {
                "role": "assistant",
                "content": f"Hi, I saw your recent Series B — exciting milestone. "
                f"We've helped similar-stage teams scale engineering. "
                f"Worth a 20-min call? #{i}",
            }
        ],
        "rejected": [
            {
                "role": "assistant",
                "content": f"Hi, our bench is top-notch and proven. "
                f"We definitely have the engineers you need. Let's talk! #{i}",
            }
        ],
    }
    for i in range(5)
]


# ── Args ───────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Colab Day-0 smoke test")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--hf-repo", default="")
    return p.parse_args()


# ── Model Loader ───────────────────────────────────────────────────


def load_model_and_tokenizer(model_id: str):
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() and torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    dtype_name = "bf16" if dtype == torch.bfloat16 else "fp16"

    print(f"[smoke] Loading {model_id} in {dtype_name}")

    try:
        from unsloth import FastLanguageModel

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
        print("[smoke] Unsloth not found → fallback to transformers")

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model, TaskType

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        torch_dtype=dtype,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_cfg = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        target_modules=LORA_TARGETS,
        lora_dropout=0.0,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    model = get_peft_model(model, lora_cfg)
    print("[smoke] PEFT LoRA attached")

    return model, tokenizer, dtype


# ── Dataset ────────────────────────────────────────────────────────





# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    if not torch.cuda.is_available():
        print("[smoke] WARNING: no GPU detected")

    # Load model
    model, tokenizer, dtype = load_model_and_tokenizer(args.model)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    print(f"[smoke] Trainable params: {trainable:,} / {total:,}")

    # Dataset
    from datasets import Dataset

    ds = Dataset.from_list(DUMMY_PAIRS)
    print(f"[smoke] Dataset size: {len(ds)}")

    # Trainer
    try:
        from trl import CPOConfig, CPOTrainer
    except ImportError:
        print("[smoke] FAIL: Install compatible TRL")
        sys.exit(1)

    use_bf16 = dtype == torch.bfloat16

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = CPOConfig(
            output_dir=tmpdir,
            loss_type="simpo",
            beta=2.0,
            simpo_gamma=1.25,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=5e-5,
            max_steps=1,
            logging_steps=1,
            save_strategy="no",
            report_to="none",
            bf16=use_bf16,
            fp16=not use_bf16,
            max_length=MAX_LEN,
            max_prompt_length=128,
            remove_unused_columns=False,
            dataloader_num_workers=0,
            seed=SEED,
        )

        trainer = CPOTrainer(
            model=model,
            args=cfg,
            train_dataset=ds,
            processing_class=getattr(tokenizer, "tokenizer", tokenizer),
        )

        print("[smoke] Running 1-step SimPO...")
        trainer.train()
        print("[smoke] Training done")

        # Save adapter
        adapter_dir = Path(tmpdir) / "smoke_adapter"
        model.save_pretrained(str(adapter_dir))
        tokenizer.save_pretrained(str(adapter_dir))

        print(f"[smoke] Adapter saved → {adapter_dir}")

        # Optional push
        if args.hf_repo:
            print(f"[smoke] Pushing to HF → {args.hf_repo}")
            model.push_to_hub(args.hf_repo, private=True)
            tokenizer.push_to_hub(args.hf_repo, private=True)

    print("\n" + "=" * 50)
    print("[smoke] ALL CHECKS PASSED")
    print(f"Model: {args.model}")
    print(f"Dtype: {'bf16' if use_bf16 else 'fp16'}")
    print("SimPO: ✅ 1 step complete")
    if args.hf_repo:
        print(f"HF: https://huggingface.co/{args.hf_repo}")
    print("=" * 50)


if __name__ == "__main__":
    main()
