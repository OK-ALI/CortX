from __future__ import annotations

import argparse
import asyncio
import logging

from PyQt6.QtWidgets import QApplication

from backend.ai.pipeline import CortxPipeline
from backend.utils.config import load_settings
from backend.utils.logger import setup_logger
from backend.utils.startup_checks import run_startup_checks
from frontend.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cortx desktop research assistant")
    parser.add_argument("--query", type=str, help="Query to run through the Cortx pipeline")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive prompt mode")
    parser.add_argument("--gui", action="store_true", help="Run desktop GUI mode")
    return parser.parse_args()


def build_pipeline() -> tuple[CortxPipeline, logging.Logger]:
    settings = load_settings()
    logger = setup_logger(settings.app.log_level)

    for check in run_startup_checks(settings):
        level = "INFO" if check.ok else "WARNING"
        getattr(logger, level.lower())("%s: %s", check.name, check.details)

    pipeline = CortxPipeline(settings=settings, logger=logger)
    return pipeline, logger


async def run_single_query(query: str, pipeline: CortxPipeline) -> None:
    result = await pipeline.run(query)
    print(result.answer)
    if result.sources:
        print("\n--- Sources ---")
        for src in result.sources:
            print(f"  {src}")


async def run_interactive(pipeline: CortxPipeline) -> None:
    while True:
        query = input("Cortx> ").strip()
        if not query or query.lower() in {"exit", "quit"}:
            break
        await run_single_query(query, pipeline)


def main() -> None:
    args = parse_args()
    pipeline, _logger = build_pipeline()

    try:
        if args.gui:
            app = QApplication.instance() or QApplication([])
            window = MainWindow(pipeline=pipeline)
            window.show()
            app.exec()
            return

        if args.interactive:
            asyncio.run(run_interactive(pipeline))
            return

        if args.query:
            asyncio.run(run_single_query(args.query, pipeline))
            return

        print("Provide --query, --interactive, or --gui")
    finally:
        pipeline.shutdown()


if __name__ == "__main__":
    main()
