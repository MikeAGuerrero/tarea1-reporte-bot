"""Persistencia idempotente del CSV final."""

import csv
import os
import tempfile
from pathlib import Path

from reporte_bot.config import IDEMPOTENCY_KEY, OUTPUT_COLUMNS


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(column, "") for column in IDEMPOTENCY_KEY)


def read_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError(
                "El CSV existente no tiene el esquema esperado. "
                f"Esperado: {OUTPUT_COLUMNS}. Encontrado: {reader.fieldnames}."
            )
        return [dict(row) for row in reader]


def write_rows_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    """Escribe el CSV mediante reemplazo atómico para evitar archivos parcialmente escritos."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        temp_name = temp_file.name

    os.replace(temp_name, path)


def merge_idempotently(
    existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], int]:
    """Conserva filas previas y añade únicamente eventos cuya clave natural no existe."""
    merged = {row_key(row): row for row in existing_rows}
    added = 0

    for row in new_rows:
        key = row_key(row)
        if key not in merged:
            merged[key] = row
            added += 1

    rows = sorted(
        merged.values(),
        key=lambda row: (
            row.get("timestamp", ""),
            row.get("solicitante", ""),
            row.get("target", ""),
        ),
    )
    return rows, added
