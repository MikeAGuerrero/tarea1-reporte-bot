"""Interfaz de línea de comandos del pipeline."""

import argparse
from datetime import datetime
from pathlib import Path

from reporte_bot.pipeline import run_pipeline


def _valid_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La fecha debe tener formato YYYY-MM-DD.") from exc
    return value


def _resolve_input(input_file: Path | None, input_dir: Path, date: str | None) -> Path:
    if input_file is not None:
        return input_file

    if date is not None:
        return input_dir / f"{date}.log"

    candidates = sorted(input_dir.glob("*.log"), key=lambda path: path.name)
    if not candidates:
        raise FileNotFoundError(f"No hay archivos .log en {input_dir}")
    return candidates[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Actualiza tabla_reporte_bot.csv a partir de logs de ADManager."
    )
    parser.add_argument(
        "--date",
        type=_valid_date,
        help=(
            "Fecha histórica a procesar en formato YYYY-MM-DD. "
            "Si se omite, usa el log más reciente."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Ruta explícita de un .log. Tiene prioridad sobre --date.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/input"),
        help="Directorio de logs. Default: data/input",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/tabla_reporte_bot.csv"),
        help="CSV acumulado. Default: data/output/tabla_reporte_bot.csv",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        input_path = _resolve_input(args.input, args.input_dir, args.date)
        processed, added, total = run_pipeline(input_path, args.output)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(f"Log procesado: {input_path}")
    print(f"Eventos resetuser encontrados: {processed}")
    print(f"Registros nuevos agregados: {added}")
    print(f"Total de registros en tabla_reporte_bot: {total}")
    print(f"Salida: {args.output}")


if __name__ == "__main__":
    main()
