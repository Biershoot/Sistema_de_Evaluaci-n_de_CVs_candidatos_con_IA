"""Logging en JSON, pensado para agregadores de logs."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Atributos que trae LogRecord de serie; todo lo demás que llegue en `extra`
# se considera contexto de negocio y se serializa en la salida.
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "taskName",
    "asctime",
    "message",
}


class JSONFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = {k: v for k, v in vars(record).items() if k not in _RESERVED}
        if extras:
            payload["context"] = extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configura el logger raíz. Idempotente."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
