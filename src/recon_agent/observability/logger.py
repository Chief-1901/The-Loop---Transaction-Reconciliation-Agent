from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog


def configure_logging(run_dir: Path, level: str = "INFO") -> structlog.BoundLogger:
    """Configure structlog to write JSONL events to run_dir/log.jsonl
    AND keep human-readable lines on stderr at the chosen level."""
    log_path = run_dir / "log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Shared chain of processors that run before the final renderer
    shared_processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # File handler — JSON lines
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    # Stderr handler — human-readable key=value
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(getattr(logging, level))
    stderr_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    # Reset any prior handlers (test isolation)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)
    root.setLevel(logging.DEBUG)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=False,   # important for repeated configuration across runs
    )

    return structlog.get_logger().bind(run_dir=str(run_dir))
