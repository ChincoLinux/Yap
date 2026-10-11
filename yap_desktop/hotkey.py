"""hotkey.py — Atajo global de teclado para mostrar/ocultar Yap (issue #158).

Intenta registrar un atajo global con pynput. Si no está disponible,
intenta con el módulo keyboard. Si ninguno está instalado, registra
solo el atajo de Qt dentro de la ventana (comportamiento degradado).

Configuración:
    ~/.config/yap/desktop.json → {"hotkey": "ctrl+shift+y"}

Uso:
    listener = HotkeyListener(callback=lambda: widget.show_near_tray())
    listener.start()   # inicia en un hilo daemon
    # ...
    listener.stop()
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

_DEFAULT_HOTKEY = "ctrl+shift+y"
_CONFIG_FILE = Path.home() / ".config" / "yap" / "desktop.json"


def _load_hotkey_config() -> str:
    """Lee la configuración de atajo del archivo de configuración."""
    try:
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("hotkey", _DEFAULT_HOTKEY)
    except Exception:
        pass
    return _DEFAULT_HOTKEY


def _save_hotkey_config(hotkey: str) -> None:
    """Guarda la configuración de atajo."""
    try:
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["hotkey"] = hotkey
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("No se pudo guardar configuración de atajo: %s", e)


# ─── Backend: pynput ─────────────────────────────────────────────────────────


def _try_pynput(hotkey_str: str, callback: Callable) -> Optional[object]:
    """Intenta usar pynput para el atajo global.

    Returns:
        Objeto listener de pynput, o None si no está disponible.
    """
    try:
        from pynput import keyboard

        def _on_activate():
            try:
                callback()
            except Exception as e:
                logger.error("Error en callback de atajo pynput: %s", e)

        listener = keyboard.GlobalHotKeys(
            {f"<{hotkey_str.replace('+', '><')}>": _on_activate}
        )
        return listener
    except ImportError:
        return None
    except Exception as e:
        logger.warning("pynput no pudo registrar el atajo: %s", e)
        return None


# ─── Backend: keyboard ────────────────────────────────────────────────────────


def _try_keyboard(hotkey_str: str, callback: Callable) -> Optional[object]:
    """Intenta usar el módulo keyboard para el atajo global.

    Returns:
        Hotkey handler, o None si no está disponible.
    """
    try:
        import keyboard as kb

        def _on_activate():
            try:
                callback()
            except Exception as e:
                logger.error("Error en callback de atajo keyboard: %s", e)

        kb.add_hotkey(hotkey_str, _on_activate, suppress=False)

        # Devuelve un objeto ficticio que tiene stop() para la interfaz uniforme
        class _KbHandle:
            def start(self_inner):
                pass  # keyboard registra al agregar

            def stop(self_inner):
                try:
                    kb.remove_hotkey(hotkey_str)
                except Exception:
                    pass

        return _KbHandle()
    except ImportError:
        return None
    except Exception as e:
        logger.warning("keyboard no pudo registrar el atajo: %s", e)
        return None


# ─── HotkeyListener ──────────────────────────────────────────────────────────


class HotkeyListener:
    """Registra y gestiona el atajo global de teclado para Yap.

    Intenta los backends en orden: pynput → keyboard → degradado (solo ventana).
    """

    def __init__(self, callback: Callable, hotkey: Optional[str] = None):
        """
        Args:
            callback: función sin args llamada cuando se activa el atajo.
            hotkey:   string del atajo (ej. 'ctrl+shift+y'). Si es None,
                      se lee de la configuración del usuario.
        """
        self._callback = callback
        self._hotkey = hotkey or _load_hotkey_config()
        self._backend = None
        self._backend_name = "none"

    def start(self) -> str:
        """Inicia el listener global.

        Returns:
            Nombre del backend usado: 'pynput', 'keyboard', o 'none'.
        """
        # Intentar pynput
        listener = _try_pynput(self._hotkey, self._callback)
        if listener is not None:
            self._backend = listener
            self._backend_name = "pynput"
            t = threading.Thread(
                target=listener.start, daemon=True, name="YapHotkeyPynput"
            )
            t.start()
            logger.info("Atajo global registrado con pynput: %s", self._hotkey)
            return "pynput"

        # Intentar keyboard
        listener = _try_keyboard(self._hotkey, self._callback)
        if listener is not None:
            self._backend = listener
            self._backend_name = "keyboard"
            logger.info("Atajo global registrado con keyboard: %s", self._hotkey)
            return "keyboard"

        # Degradado: ningún backend disponible
        logger.warning(
            "Atajo global no disponible. Instala pynput o keyboard:\n"
            "  pip install pynput\n"
            "  # o\n"
            "  pip install keyboard"
        )
        self._backend_name = "none"
        return "none"

    def stop(self) -> None:
        """Para el listener."""
        if self._backend is None:
            return
        try:
            if hasattr(self._backend, "stop"):
                self._backend.stop()
        except Exception as e:
            logger.debug("Error al detener hotkey listener: %s", e)
        self._backend = None

    @property
    def hotkey(self) -> str:
        return self._hotkey

    @property
    def backend(self) -> str:
        return self._backend_name

    def change_hotkey(self, new_hotkey: str) -> str:
        """Cambia el atajo en caliente.

        Returns:
            Backend usado para el nuevo atajo.
        """
        self.stop()
        self._hotkey = new_hotkey
        _save_hotkey_config(new_hotkey)
        return self.start()
