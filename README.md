# Tarea 1 - Reporte de acciones del bot

## Intención del repositorio

Este proyecto implementa un pipeline de Ingeniería de Datos que actualiza diariamente la tabla
`tabla_reporte_bot.csv` a partir de archivos `.log`.

Actualmente procesa dos acciones:

- reseteo de usuarios de ADManager mediante `users_admin/resetuser`;
- alta de usuarios en SAP mediante `sap/register_user`.

Cada evento se enriquece con la información disponible en ADManager y los resultados técnicos
se convierten en mensajes legibles para una persona.

El diseño busca ser idempotente, recuperable, modular y extensible para incorporar nuevas
acciones en el futuro.

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
data/input/2026-08-31.log
```

## Ejecución

Procesar automáticamente el log más reciente:

```bash
uv run reporte-bot
```

Reprocesar una fecha histórica:

```bash
uv run reporte-bot --date 2026-08-31
```

Procesar un archivo explícito:

```bash
uv run reporte-bot --input /ruta/al/archivo.log
```

La salida se genera en:

```text
data/output/tabla_reporte_bot.csv
```

## Acciones soportadas

| Acción | Sistema | Endpoint |
|---|---|---|
| `reseteo_usuario` | ADManager | `/v3/users_admin/resetuser` |
| `alta_usuario` | SAP | `/v2/sap/register_user` |

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
eventos nuevos que no estén presentes en el CSV acumulado. Como `accion` y `sistema` forman
parte de la clave, distintas acciones del mismo usuario no colisionan entre sí.
