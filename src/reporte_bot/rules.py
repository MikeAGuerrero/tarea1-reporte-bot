"""Reglas de negocio para convertir respuestas técnicas en mensajes humanos."""

from reporte_bot.models import ResetEvent
from reporte_bot.utils import normalize_text


def build_result(event: ResetEvent) -> str:
    """Construye el valor final de la columna resultado sin exponer el status code."""
    status = event.api_status
    requester = event.requester_info
    target = event.target_info

    if status == 200:
        return "Reseteo de usuario realizado correctamente en ADManager."

    if status == 202:
        return (
            "El usuario objetivo pertenece a Corporativo y no puede ser reseteado mediante "
            "el bot; puede autoresetearse."
        )

    if status == 403:
        if requester and target:
            if normalize_text(requester.office) != normalize_text(target.office):
                return "Los usuarios no pertenecen a la misma oficina."

            requester_description = normalize_text(requester.description)
            if not requester_description.startswith(("gerente", "admin")):
                return (
                    "El usuario solicitante no es gerente ni administrador de sistemas y no "
                    "puede realizar el reseteo."
                )

            if normalize_text(target.ou_name) == normalize_text("OAT/Cedis/BY"):
                return (
                    "El usuario objetivo pertenece a OAT/Cedis/BY y no puede ser reseteado "
                    "mediante el bot."
                )

        return "La solicitud fue rechazada por una regla de autorización del bot."

    if status == 404:
        requester_found = requester is not None
        target_found = target is not None

        if not requester_found and not target_found:
            return "Ningún usuario se encontró en ADManager."
        if not requester_found:
            return "El usuario solicitante no se encontró en ADManager."
        if not target_found:
            return "El usuario objetivo no se encontró en ADManager."
        return "No fue posible identificar el usuario faltante en ADManager."

    if status == 429:
        return "No se pudo ejecutar el reseteo porque se agotaron los tokens de ADManager."

    if status == 500:
        return "Ocurrió un error inesperado y crítico durante el proceso de reseteo."

    if status == 503:
        if event.adm_error:
            return f"ADManager no pudo ejecutar el reseteo. Error: {event.adm_error}"
        return "ADManager presentó un error y el reseteo no se pudo ejecutar."

    if status == 504:
        return (
            "Ocurrió un timeout en la comunicación con ADManager; el reseteo no se pudo ejecutar."
        )

    return "Resultado no clasificado por las reglas actuales del proceso."
