"""Strukturiertes Logging fuer Kontura AI.

Senior-Konzept: structlog + ContextVars
========================================
- In Development: lesbares, farbiges Console-Format.
- In Production: JSON, parsbar von Datadog/Loki/CloudWatch/Splunk.
- Context (request_id, tenant_id, user_id) wird per ContextVar gebunden,
  taucht ab dann in JEDEM Log-Statement im selben Request auf - ohne dass
  wir es in jedem logger.info(...) explizit mitgeben muessen.

Senior-Detail: foreign_pre_chain
=================================
structlog's stdlib-Adapter sorgt dafuer, dass auch Logs von SQLAlchemy,
asyncpg, FastAPI etc. (die alle stdlib-logging nutzen) im selben Format
landen. Kein 'Log-Mischmasch' aus 2 verschiedenen Pipelines.
"""

from __future__ import annotations

import logging
import sys

import structlog

from kontura.core.config import settings


def configure_logging() -> None:
    """Konfiguriert structlog + stdlib-logging einheitlich.

    Wird genau EINMAL beim App-Start aufgerufen (in main.lifespan).
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Pre-Chain: laeuft VOR dem finalen Renderer fuer ALLE Logs
    # (auch fremde Libs wie SQLAlchemy).
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    # Production: JSON-Renderer (Datadog/Loki/CloudWatch frisst das).
    # Development: ConsoleRenderer mit Farben (Mensch frisst das).
    renderer: structlog.types.Processor
    if settings.app_env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # structlog konfigurieren
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # stdlib-logging auf den gleichen Renderer schicken
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Existierende Handler entfernen (z.B. uvicorn's Default), damit alles
    # einheitlich durch unseren Formatter laeuft.
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # SQLAlchemy-Engine-Spam runterdrehen - nur Warnings.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
