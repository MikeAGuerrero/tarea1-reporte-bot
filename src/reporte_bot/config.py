"""Constantes de configuración del proceso."""

RESET_ENDPOINT = "/v3/users_admin/resetuser"
SAP_REGISTER_ENDPOINT = "/v2/sap/register_user"

RESET_ACTION = "reseteo_usuario"
RESET_SYSTEM = "ADManager"
SAP_REGISTER_ACTION = "alta_usuario"
SAP_REGISTER_SYSTEM = "SAP"

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
