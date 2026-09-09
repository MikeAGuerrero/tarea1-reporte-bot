"""Orquestación del flujo completo: leer, transformar, combinar y guardar."""

from pathlib import Path

from reporte_bot.config import ACTION, SYSTEM
from reporte_bot.models import ResetEvent
from reporte_bot.parser import parse_reset_events
from reporte_bot.rules import build_result
from reporte_bot.storage import merge_idempotently, read_existing_rows, write_rows_atomic


def event_to_row(event: ResetEvent) -> dict[str, str]:
    requester = event.requester_info
    target = event.target_info

    return {
        "timestamp": event.timestamp,
        "solicitante": event.requester,
        "target": event.target,
        "accion": ACTION,
        "sistema": SYSTEM,
        "nombre_completo_solicitante": requester.full_name if requester else "",
        "nombre_completo_target": target.full_name if target else "",
        "oficina_solicitante": requester.office if requester else "",
        "oficina_target": target.office if target else "",
        "resultado": build_result(event),
    }


def run_pipeline(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de entrada: {input_path}")

    events = parse_reset_events(input_path)
    new_rows = [event_to_row(event) for event in events]
    existing_rows = read_existing_rows(output_path)
    merged_rows, added = merge_idempotently(existing_rows, new_rows)
    write_rows_atomic(output_path, merged_rows)

    return len(events), added, len(merged_rows)
