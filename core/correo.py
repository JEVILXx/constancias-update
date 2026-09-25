"""
Envío por correo (opcional): manda por Gmail (o cualquier SMTP) la
constancia de cada persona, adjunta como PDF, al terminar de generarla.
Soporta varias cuentas remitentes con límite diario cada una (ver
CuentaEnvio) para repartir el envío y no topar el límite de una sola.
"""

from __future__ import annotations

import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


@dataclass
class CorreoConfig:
    remitente: str
    contrasena_app: str
    servidor_smtp: str = "smtp.gmail.com"
    puerto: int = 465
    asunto: str = "Tu constancia de participación"
    cuerpo: str = (
        "Hola {nombre},\n\n"
        "Adjunto tu constancia de participación.\n\n"
        "¡Gracias por participar!"
    )


@dataclass
class CuentaEnvio:
    """Una cuenta remitente más su límite diario y cuántos ya lleva
    enviados hoy (para saber cuándo saltar a la siguiente cuenta)."""
    config: CorreoConfig
    limite_diario: int = 500
    ya_enviados_hoy: int = 0

    @property
    def remitente(self) -> str:
        return self.config.remitente

    @property
    def le_queda_cupo(self) -> bool:
        return self.ya_enviados_hoy < self.limite_diario


class ErrorEnvioCorreo(Exception):
    pass


def enviar_correo_con_adjunto(
    cfg: CorreoConfig, destinatario: str, nombre_persona: str, adjunto: Path,
) -> None:
    """Manda un correo con el PDF adjunto. Lanza ErrorEnvioCorreo si algo falla
    (dirección inválida, credenciales incorrectas, sin internet, etc.)."""
    msg = EmailMessage()
    msg["Subject"] = cfg.asunto.replace("{nombre}", nombre_persona)
    msg["From"] = cfg.remitente
    msg["To"] = destinatario
    msg.set_content(cfg.cuerpo.replace("{nombre}", nombre_persona))

    try:
        with open(adjunto, "rb") as f:
            datos = f.read()
    except OSError as e:
        raise ErrorEnvioCorreo(f"No se pudo leer el archivo adjunto: {e}") from e

    msg.add_attachment(datos, maintype="application", subtype="pdf", filename=adjunto.name)

    try:
        with smtplib.SMTP_SSL(cfg.servidor_smtp, cfg.puerto, timeout=30) as servidor:
            servidor.login(cfg.remitente, cfg.contrasena_app)
            servidor.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise ErrorEnvioCorreo(
            "Usuario/contraseña rechazados por el servidor. Si usas Gmail, "
            "recuerda que necesitas una \"contraseña de aplicación\" (no tu "
            "contraseña normal) y tener la verificación en dos pasos activada."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise ErrorEnvioCorreo(f"No se pudo enviar el correo: {e}") from e


def _correo_valido(valor: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valor.strip()))
