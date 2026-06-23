from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

import structlog


def setup_logging(
    log_level: str | None = None,
    json_output: bool | None = None,
    service_name: str = "cdp",
) -> None:
    """Configure structured logging for the entire application.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
            Defaults to env var LOG_LEVEL or "INFO".
        json_output: If True, emit JSON logs. Defaults to env var
            JSON_LOGS or False (human-readable console).
        service_name: Label attached to every log event.
    """
    level = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    use_json = json_output if json_output is not None else os.getenv("JSON_LOGS", "false").lower() == "true"

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    if use_json:
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.processors.JSONRenderer(serializer=self_serialize_json),
            ],
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.dev.ConsoleRenderer(
                    colors=sys.stderr.isatty(),
                    sort_keys=False,
                ),
            ],
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silence noisy third-party loggers
    for name in ("boto3", "botocore", "urllib3", "aiokafka", "pymongo", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger(service_name)
    log.info("logging_configured", level=level, json_output=use_json, service=service_name)


def self_serialize_json(obj: Any, *args: Any, **kwargs: Any) -> str:
    """Fallback JSON serializer for non-serializable types."""
    import json

    return json.dumps(obj, default=str, *args, **kwargs)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with an optional contextual name."""
    return structlog.get_logger(name or __name__)


# ──────────────────────────────────────────────
# Convenience: log helper decorator
# ──────────────────────────────────────────────

def log_call(logger: structlog.stdlib.BoundLogger | None = None):
    """Decorator that logs function entry and exit at DEBUG level.

    Usage:
        @log_call()
        def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        import functools
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"
            logger.debug("call.enter", function=func_name)
            try:
                result = func(*args, **kwargs)
                logger.debug("call.exit", function=func_name)
                return result
            except Exception as exc:
                logger.error("call.error", function=func_name, error=str(exc))
                raise

        return wrapper
    return decorator
