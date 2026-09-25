"""
Interfaz gráfica del Generador de Constancias y QR, dividida en módulos:

  gui.estilos             -> paleta de colores
  gui.rutas               -> rutas de archivos/preferencias
  gui.dnd                 -> soporte de arrastrar y soltar (opcional)
  gui.dialogos            -> ventanas secundarias (marcadores manuales, cuentas)
  gui.comunes             -> ComunesMixin: layout, cola de progreso, drag&drop
  gui.panel_constancias   -> PanelConstanciasMixin: modo Constancias
  gui.panel_qr            -> PanelQRMixin: modo Códigos QR
  gui.actualizaciones     -> ActualizacionesMixin: botón/aviso de actualizaciones remotas
  gui.app                 -> ConstanciasGUI, la clase final que junta todo
"""

from .app import ConstanciasGUI

__all__ = ["ConstanciasGUI"]
