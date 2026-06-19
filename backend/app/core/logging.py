"""
INFRA2-02: Structured JSON logging with structlog.

Every log line emitted by FastAPI or the ARQ worker is a JSON object with:
  - timestamp (ISO 8601)
  - level
  - event (message)
  - logger (module name)
  - Any additional context bound by the caller

Usage in application code:
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("trip_created", trip_id=str(trip.id), driver_id=str(driver.id))

Usage in ARQ worker tasks:
    logger = structlog.get_logger("worker")
    logger.info("task_started", task="task_mark_overdue_billing_documents")
"""

import logging
import sys

import structlog


def configure_structlog(json_logs: bool = True) -> None:
    """Configure structlog for the application.

    Call once at startup in FastAPI lifespan and ARQ worker startup.
    json_logs=True for production (Railway Logs aggregation).
    json_logs=False for local dev (pretty console output).
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Silence noisy libraries in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("arq.worker").setLevel(logging.INFO)
