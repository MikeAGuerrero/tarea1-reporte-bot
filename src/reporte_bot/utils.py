"""Funciones pequeñas reutilizables."""

import unicodedata


def normalize_text(value: str | None) -> str:
    """Normaliza texto para comparaciones tolerantes a mayúsculas y acentos."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.casefold().strip()


def normalize_username(value: str) -> str:
    """Normaliza identificadores de usuario sin modificar su valor de salida."""
    return value.casefold().strip()
