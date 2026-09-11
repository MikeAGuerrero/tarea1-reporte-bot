"""Reglas de negocio para convertir respuestas técnicas en mensajes humanos."""

from reporte_bot.models import ReportEvent, ResetEvent, SapRegisterEvent
from reporte_bot.utils import normalize_text


def _build_reset_result(event: ResetEvent) -> str:
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

    return "Resultado no clasificado por las reglas actuales del reseteo."


def _build_sap_register_result(event: SapRegisterEvent) -> str:
    status = event.api_status
    requester = event.requester_info
    target = event.target_info

    if status == 200:
        return (
            "El usuario objetivo fue registrado exitosamente en SAP; se creó el ticket "
            "control y se cerró."
        )

    if status == 202:
        if event.ticket_created and not event.ticket_closed:
            return (
                "El usuario objetivo fue registrado exitosamente en SAP; se creó el ticket "
                "control, pero no pudo cerrarse."
            )
        if not event.ticket_created:
            return (
                "El usuario objetivo fue registrado exitosamente en SAP, pero no fue posible "
                "crear el ticket control."
            )
        return (
            "El usuario objetivo fue registrado exitosamente en SAP, pero el proceso del "
            "ticket control no terminó correctamente."
        )

    if status == 208:
        return "El usuario objetivo ya existe en el ambiente ECC ECP de SAP."

    if status == 400:
        if not event.target.isdigit():
            return "El número de empleado no es numérico."

        if normalize_text(event.treatment) not in {"senor", "senora"}:
            return 'El tratamiento no es "señor" ni "señora".'

        if not event.sap_called:
            return "El puesto solicitado no existe."

        return (
            "Todas las validaciones fueron exitosas y el servicio de SAP estaba disponible, "
            "pero no se pudo ejecutar el alta por una razón desconocida."
        )

    if status == 401:
        return "El usuario solicitante no es gerente ni administrador de sistemas."

    if status == 403:
        if requester and normalize_text(requester.office) == "corporativo":
            return (
                "El usuario solicitante pertenece a Corporativo y no tiene permitido ejecutar "
                "el alta de usuarios en SAP."
            )

        if requester and target:
            if normalize_text(requester.office) != normalize_text(target.office):
                return "Los usuarios no pertenecen a la misma oficina."

        return "Conflicto con el puesto solicitado."

    if status == 404:
        requester_found = requester is not None
        target_found = target is not None

        if not requester_found and not target_found:
            return "No existe el usuario solicitante ni el usuario objetivo en ADManager."
        if not requester_found:
            return "No existe el usuario solicitante en ADManager."
        if not target_found:
            return "No existe el usuario objetivo en ADManager."
        return "No fue posible identificar el usuario faltante en ADManager."

    if status == 500:
        return "Ocurrió un error desconocido durante el proceso de alta en SAP."

    if status == 503:
        return "Todas las validaciones fueron exitosas, pero el servicio del lado de SAP falló."

    return "Resultado no clasificado por las reglas actuales del alta de usuario en SAP."


def build_result(event: ReportEvent) -> str:
    """Construye el valor final de resultado según la acción del evento."""
    if isinstance(event, ResetEvent):
        return _build_reset_result(event)
    if isinstance(event, SapRegisterEvent):
        return _build_sap_register_result(event)
    raise TypeError(f"Tipo de evento no soportado: {type(event).__name__}")
