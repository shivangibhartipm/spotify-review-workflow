"""
Pipeline orchestrator.

Runs all phases in order, or a specific phase via --phase.

Usage:
    python run_all.py             # run all phases
    python run_all.py --phase 1   # Phase 1: collect only
    python run_all.py --phase 2   # Phase 2: clean only
    python run_all.py --phase 3   # Phase 3: enrich only
    python run_all.py --phase 4   # Phase 4: build insights only
"""

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_all")


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def run_phase1() -> None:
    """Phase 1 — Data collection (last ~90 days)."""
    logger.info("=" * 60)
    logger.info("PHASE 1 — Data Collection")
    logger.info("=" * 60)

    from src.db import init_db, count_raw_reviews
    init_db()

    totals: dict[str, int] = {}

    # Play Store
    logger.info("--- Play Store ---")
    from src.collect.play_store import collect as collect_play
    totals["play_store"] = collect_play()

    # App Store
    logger.info("--- App Store ---")
    from src.collect.app_store import collect as collect_app
    totals["app_store"] = collect_app()

    # Spotify Community forums
    logger.info("--- Spotify Community Forums ---")
    from src.collect.forums import collect as collect_forums
    totals["forum"] = collect_forums()

    logger.info("=" * 60)
    logger.info("Phase 1 complete. New rows inserted per source:")
    for source, count in totals.items():
        logger.info("  %-15s %d", source, count)
    logger.info("  %-15s %d", "TOTAL", sum(totals.values()))
    logger.info("  %-15s %d", "DB total", count_raw_reviews())
    logger.info("=" * 60)


def run_phase2() -> None:
    """Phase 2 — Data cleaning."""
    logger.info("=" * 60)
    logger.info("PHASE 2 — Data Cleaning")
    logger.info("=" * 60)

    from src.clean.pipeline import run as run_cleaning

    stats = run_cleaning()
    logger.info("=" * 60)
    logger.info("Phase 2 complete:")
    logger.info("  %-18s %d", "Raw rows", stats.raw_rows)
    logger.info("  %-18s %d", "Clean rows", stats.inserted_rows)
    logger.info("  %-18s %d", "Empty rows", stats.empty_rows)
    logger.info("  %-18s %d", "Duplicates", stats.duplicate_rows)
    logger.info("  %-18s %d", "Non-English", stats.non_english_rows)
    logger.info("=" * 60)


def run_phase3() -> None:
    """Phase 3 — Enrichment."""
    logger.info("=" * 60)
    logger.info("PHASE 3 — Enrichment")
    logger.info("=" * 60)

    from src.enrich.pipeline import run as run_enrichment

    stats = run_enrichment()
    logger.info("=" * 60)
    logger.info("Phase 3 complete:")
    logger.info("  %-18s %d", "Clean rows", stats.clean_rows)
    logger.info("  %-18s %d", "Enriched rows", stats.enriched_rows)
    logger.info("  %-18s %d", "Sentiment rows", stats.sentiment_rows)
    logger.info("  %-18s %d", "Topic rows", stats.topic_rows)
    logger.info("  %-18s %d", "Theme rows", stats.theme_rows)
    logger.info("  %-18s %d", "Segment rows", stats.segment_rows)
    logger.info("=" * 60)


def run_phase4() -> None:
    """Phase 4 — Insight extraction."""
    logger.info("=" * 60)
    logger.info("PHASE 4 — Insight Extraction")
    logger.info("=" * 60)

    from src.insights.build_insights import run as run_insights

    stats = run_insights()
    logger.info("=" * 60)
    logger.info("Phase 4 complete:")
    logger.info("  %-18s %d", "Enriched rows", stats.enriched_rows)
    logger.info("  %-18s %d", "Insight rows", stats.insight_rows)
    logger.info("  %-18s %s", "Export", stats.export_path)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PHASES = {
    1: run_phase1,
    2: run_phase2,
    3: run_phase3,
    4: run_phase4,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Review Engine pipeline runner")
    parser.add_argument(
        "--phase",
        type=int,
        choices=list(PHASES.keys()),
        help="Run a single phase (1–4).  Omit to run all phases in order.",
    )
    args = parser.parse_args()

    start = time.time()

    if args.phase:
        PHASES[args.phase]()
    else:
        for phase_num in sorted(PHASES.keys()):
            PHASES[phase_num]()

    elapsed = time.time() - start
    logger.info("Done in %.1f seconds.", elapsed)
    logger.info("Launch dashboard: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
