"""
Ícone na bandeja do sistema para o modo OBS.

Usa pystray para criar um ícone leve (sem dependência do Qt/PySide6).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger("obs_tray")


def _make_icon_image(size: int = 64) -> Image.Image:
    """Gera um ícone simples (círculo verde com 'TV')."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=(34, 197, 94, 255))
    draw.text(
        (size // 2, size // 2),
        "TV",
        fill=(255, 255, 255, 255),
        anchor="mm",
    )
    return img


class OBSIconTray:
    """Ícone na bandeja do sistema para o OBS Bot.

    Cria um ícone com menu que permite:
      - Ver status (conectado/transmitindo/aguardando)
      - Iniciar/Parar bot manualmente
      - Sair da aplicação
    """

    def __init__(
        self,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._status = "⏸ Aguardando OBS..."
        self._running = False

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "YouTube Chat Bot — TV IEBT", None, enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: self._status, None, enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "▶ Iniciar Bot",
                self._on_start,
                default=True,
                visible=lambda item: not self._running,
            ),
            pystray.MenuItem(
                "⏹ Parar Bot",
                self._on_stop,
                visible=lambda item: self._running,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._on_quit),
        )

    def run(self) -> None:
        """Inicia o ícone na bandeja (bloqueante). Roda em thread separada."""
        if self._icon:
            return

        self._icon = pystray.Icon(
            "youtube_chat_bot_obs",
            _make_icon_image(),
            "YouTube Chat Bot — TV IEBT",
            self._build_menu(),
        )
        log.info("Ícone da bandeja iniciado.")
        self._icon.run()

    def start_thread(self) -> None:
        """Dispara o ícone em uma thread daemon."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Remove o ícone da bandeja."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        self._thread = None
        log.info("Ícone da bandeja removido.")

    def update_status(self, status: str, is_streaming: bool = False) -> None:
        """Atualiza o texto de status e se o bot está rodando."""
        self._status = status
        self._running = is_streaming
        if self._icon:
            self._icon.title = f"YouTube Chat Bot — TV IEBT\n{status}"
            # Rebuild menu to show/hide start/stop
            self._icon.menu = self._build_menu()
