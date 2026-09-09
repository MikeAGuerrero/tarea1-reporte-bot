# Tarea 1 - Reporte de reseteos de ADManager

## Intención del repositorio

Este proyecto implementa un pipeline de Ingeniería de Datos que actualiza diariamente la tabla
`tabla_reporte_bot.csv` a partir de archivos `.log`. El proceso toma únicamente las solicitudes
del endpoint `users_admin/resetuser`, enriquece cada evento con la información de ADManager y
convierte los resultados técnicos en mensajes legibles para una persona.

El diseño busca ser:

- **Idempotente:** reejecutar un mismo log no duplica ni altera registros existentes.
- **Recuperable:** se puede procesar cualquier fecha histórica.
- **Modular:** parsing, reglas de negocio, persistencia y CLI tienen responsabilidades separadas.
- **Extensible:** la acción y el sistema están desacoplados de la persistencia para permitir agregar
  más tipos de eventos en el futuro.

## Estructura

```text
.
├── data/
│   ├── input/       # Logs locales; no se versionan
│   └── output/      # CSV generado; no se versiona
├── notebooks/       # Solo exploración; no forma parte del pipeline
├── src/reporte_bot/
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── parser.py
│   ├── pipeline.py
│   ├── rules.py
│   ├── storage.py
│   └── utils.py
├── .gitignore
├── pyproject.toml
└── README.md
```

## Requisitos

- Linux / WSL
- Python 3.11 o superior
- `uv`

## Instalación

```bash
uv sync
```

## Colocar los datos

Los archivos `.log` se colocan localmente en `data/input/`. Los datos están excluidos del
repositorio mediante `.gitignore`.

Ejemplo:

```text
data/input/2026-09-01.log
```

## Ejecución

### Procesar automáticamente el log más reciente

```bash
uv run reporte-bot
```

### Reprocesar una fecha histórica

```bash
uv run reporte-bot --date 2026-09-01
```

### Procesar un archivo explícito

```bash
uv run reporte-bot --input /ruta/al/archivo.log
```

La salida se genera en:

```text
data/output/tabla_reporte_bot.csv
```

## Validar estilo

```bash
uv run ruff check .
uv run ruff format --check .
```

Para aplicar formato automáticamente:

```bash
uv run ruff format .
```

## Idempotencia

La clave natural utilizada para detectar si un evento ya existe es:

```text
(timestamp, solicitante, target, accion, sistema)
```

Al reejecutar el mismo archivo, el proceso conserva los registros existentes y solamente agrega
eventos nuevos que no estén presentes en el CSV acumulado.
