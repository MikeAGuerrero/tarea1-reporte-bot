"""Constantes de configuración del proceso."""

RESET_ENDPOINT = "/v3/users_admin/resetuser"
ACTION = "reseteo_usuario"
SYSTEM = "ADManager"

OUTPUT_COLUMNS = [
    "timestamp",
    "solicitante",
    "target",
    "accion",
    "sistema",
    "nombre_completo_solicitante",
    "nombre_completo_target",
    "oficina_solicitante",
    "oficina_target",
    "resultado",
]

IDEMPOTENCY_KEY = ["timestamp", "solicitante", "target", "accion", "sistema"]
