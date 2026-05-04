"""
Shared terminal styling for the coronary pipeline: banners, phases, footers.

Uses ASCII-only rules for Windows console compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path


RULE = "=" * 58
SUB = "-" * 58


def configure_logging() -> None:
    """Short timestamp + message only (no long logger name noise)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def short_path(p: Path, max_parts: int = 3) -> str:
    """Last ``max_parts`` path segments for compact logs."""
    parts = p.parts
    if len(parts) <= max_parts:
        return str(p)
    return str(Path(*parts[-max_parts:]))


def banner_pipeline(logger: logging.Logger, patient_id: str) -> None:
    logger.info(RULE)
    logger.info("  PIPELINE  |  patient=%s", patient_id)
    logger.info(RULE)


def banner_pipeline_done(logger: logging.Logger, patient_id: str, seconds: float) -> None:
    logger.info(RULE)
    logger.info("  DONE  |  %s  |  %.1fs", patient_id, seconds)
    logger.info(RULE)


def phase(logger: logging.Logger, block_id: str, title: str) -> None:
    logger.info(">> Block %s  %s", block_id, title)


def sub(logger: logging.Logger, fmt: str, *args: object) -> None:
    msg = (fmt % args) if args else fmt
    logger.info("   %s", msg)


def footer_block(
    logger: logging.Logger,
    *,
    block_id: str,
    title: str,
    seconds: float,
    parts: list[str],
) -> None:
    tail = "  |  ".join(parts)
    logger.info("-- Block %s %s --  %.1fs  |  %s", block_id, title, seconds, tail)
