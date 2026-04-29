"""
Centralized configuration for Tenacious-Bench.

Loads settings from environment variables (via .env file) with sensible defaults.
All configurable values used across the pipeline are defined here, so no script
needs to hardcode paths, model names, or thresholds.

Usage:
    from config import cfg
    print(cfg.GENERATOR_MODEL)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Load .env file if present — must run before reading os.environ.
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass  # dotenv is optional; env vars can be set directly.


@dataclass(frozen=True)
class Config:
    """Immutable project-wide configuration.

    Values are read once at import time. To override, set the corresponding
    environment variable before importing this module.
    """

    # ── Paths ─────────────────────────────────────────────────────────
    ROOT: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    @property
    def SEED_DIR(self) -> Path:
        return self.ROOT / "week10-data" / "tenacious_sales_data" / "seed"

    @property
    def EVAL_DIR(self) -> Path:
        return self.ROOT / "week10-data" / "eval"

    @property
    def GENERATION_DIR(self) -> Path:
        return self.ROOT / "generation_scripts"

    @property
    def BENCH_DIR(self) -> Path:
        return self.ROOT / "tenacious_bench_v0.1"

    # ── API ────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "")
    )

    # ── Models ─────────────────────────────────────────────────────────
    GENERATOR_MODEL: str = field(
        default_factory=lambda: os.environ.get(
            "GENERATOR_MODEL", "deepseek/deepseek-chat-v3-0324"
        )
    )
    JUDGE_MODEL: str = field(
        default_factory=lambda: os.environ.get(
            "JUDGE_MODEL", "google/gemini-2.0-flash-001"
        )
    )
    EMBEDDING_MODEL: str = field(
        default_factory=lambda: os.environ.get(
            "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        )
    )

    # ── Generation ─────────────────────────────────────────────────────
    SYNTHESIS_TARGET_TASKS: int = field(
        default_factory=lambda: int(os.environ.get("SYNTHESIS_TARGET_TASKS", "63"))
    )
    SYNTHESIS_BATCH_SIZE: int = field(
        default_factory=lambda: int(os.environ.get("SYNTHESIS_BATCH_SIZE", "7"))
    )

    # ── Contamination ──────────────────────────────────────────────────
    NGRAM_THRESHOLD: int = field(
        default_factory=lambda: int(os.environ.get("NGRAM_THRESHOLD", "8"))
    )
    COSINE_THRESHOLD: float = field(
        default_factory=lambda: float(os.environ.get("COSINE_THRESHOLD", "0.85"))
    )

    # ── Reproducibility ────────────────────────────────────────────────
    RANDOM_SEED: int = field(
        default_factory=lambda: int(os.environ.get("RANDOM_SEED", "42"))
    )


# Singleton instance — import this everywhere.
cfg = Config()
