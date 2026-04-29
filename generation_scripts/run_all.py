"""
Run all generators in sequence, assemble partitions, and run contamination checks.

This is the single entry point for reproducing the full Tenacious-Bench dataset.
Each step runs as a subprocess so that failures are isolated and the pipeline
continues as far as possible.

Usage:
    uv run python generation_scripts/run_all.py [--skip-synthesis]
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Each step: (human label, script filename, requires API key).
STEPS: list[tuple[str, str, bool]] = [
    ("Programmatic generator (~75 tasks)", "programmatic_generator.py", False),
    ("Trace-derived generator (~75 tasks)", "trace_derived_generator.py", False),
    ("Hand-authored adversarial (~38 tasks)", "hand_authored_adversarial.py", False),
    ("Multi-LLM synthesis (~63 tasks)", "multi_llm_synthesis.py", True),
    ("Assemble partitions", "assemble_partitions.py", False),
    ("Contamination check", "contamination_check.py", False),
]


def main() -> None:
    """Execute the full dataset generation pipeline."""
    skip_synthesis = "--skip-synthesis" in sys.argv

    logger.info("=" * 60)
    logger.info("Tenacious-Bench v0.1 — Full Dataset Generation")
    logger.info("=" * 60)

    if skip_synthesis:
        logger.info("Mode: --skip-synthesis (offline generators only)")

    for i, (label, script, needs_api) in enumerate(STEPS, 1):
        if needs_api and skip_synthesis:
            logger.info("[%d/%d] SKIP: %s (--skip-synthesis)", i, len(STEPS), label)
            continue

        logger.info("[%d/%d] %s", i, len(STEPS), label)
        logger.info("-" * 40)

        script_path = cfg.GENERATION_DIR / script
        if not script_path.exists():
            logger.error("Script not found: %s", script_path)
            continue

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(cfg.ROOT),
            capture_output=False,
        )

        if result.returncode != 0:
            logger.error("Step FAILED with exit code %d", result.returncode)
            if needs_api:
                logger.warning(
                    "API key may be missing — set OPENROUTER_API_KEY in .env"
                )
            else:
                sys.exit(1)

    logger.info("=" * 60)
    logger.info("DONE. Next steps:")
    logger.info("  1. Review tenacious_bench_v0.1/composition_summary.json")
    logger.info("  2. Review contamination_check.json")
    logger.info("  3. Run: uv run python generation_scripts/inter_rater_labeling.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
