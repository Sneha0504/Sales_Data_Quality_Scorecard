"""Shared configuration and logging helpers for the pipeline.

All pipeline modules load their settings through :func:`load_config` so that
paths and parameters live only in ``config/config.yaml`` and never in code.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

# Project root is the directory that contains both ``config/`` and ``src/``.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load the YAML configuration file.

    Args:
        config_path: Optional path to a config file. Defaults to
            ``config/config.yaml`` at the project root.

    Returns:
        The parsed configuration as a nested dictionary.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = yaml.safe_load(handle)
    return config


def resolve_path(relative: str | Path) -> Path:
    """Resolve a config path against the project root.

    Absolute paths are returned unchanged; relative paths are anchored to
    :data:`PROJECT_ROOT` so the pipeline is independent of the current
    working directory.

    Args:
        relative: A path string from the configuration.

    Returns:
        An absolute :class:`~pathlib.Path`.
    """
    candidate = Path(relative)
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def configure_logging(config: dict[str, Any]) -> None:
    """Configure root logging from the ``logging`` section of the config.

    Args:
        config: The parsed configuration dictionary.
    """
    log_cfg = config.get("logging", {})
    level_name = str(log_cfg.get("level", "INFO")).upper()
    fmt = log_cfg.get("format", "%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.basicConfig(level=getattr(logging, level_name, logging.INFO), format=fmt)
