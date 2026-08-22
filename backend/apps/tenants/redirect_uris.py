"""Normalización de la whitelist `redirect_uris` (lista JSON)."""

from __future__ import annotations

import re
from typing import Any

# Parte un string en URIs cuando el siguiente token empieza por http(s)://.
# No parte comas de query (`?ids=1,2`) porque no van seguidas de un scheme.
_URI_SPLIT = re.compile(r"[\s,]+(?=https?://)", re.IGNORECASE)


def parse_redirect_uris(value: Any) -> list[str]:
    """
    Convierte el valor persistido o enviado por API en una lista de URIs.

    Acepta lista, string único, o entradas concatenadas por coma/salto
    (`["http://a/callback,https://b/callback"]`) — el fallo más común
    al pegar más de una callback en el admin.
    """
    if value is None:
        return []
    if isinstance(value, str):
        items: list[Any] = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise ValueError("Debe ser una lista de URLs.")

    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            raise ValueError("Cada redirect_uri debe ser un string no vacío.")
        for part in _URI_SPLIT.split(item.strip()):
            cleaned = part.strip().strip(",")
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
    return result
