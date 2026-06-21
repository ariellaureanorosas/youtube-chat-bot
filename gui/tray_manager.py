from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from gui.bot_controller import BotController
from gui.main_window import MainWindow


def _make_icon() -> QIcon:
    icon = QApplication.style().standardIcon(
        QApplication.style().StandardPixmap.SP_ComputerIcon
    )
    if not icon.isNull():
        return icon
    pixmap = QPixmap(16, 16)
    pixmap.fill(
        QApplication.palette()
        .highlight()
        .color()
    )
    return QIcon(pixmap)


class TrayManager:
    def __init__(
        self, window: MainWindow, bot_controller: BotController
    ):
        self._window = window
        self._bot = bot_controller
        self._build()

    def _build(self):
        self._tray = QSystemTrayIcon(_make_icon(), self._window)
        self._tray.setToolTip("YouTube Chat Bot - TV IEBT")

        menu = QMenu()

        self._show_act = QAction("Abrir")
        self._show_act.triggered.connect(self._show_window)
        menu.addAction(self._show_act)

        self._toggle_act = QAction("Iniciar Bot")
        self._toggle_act.triggered.connect(self._toggle_bot)
        menu.addAction(self._toggle_act)

        menu.addSeparator()

        self._quit_act = QAction("Sair")
        self._quit_act.triggered.connect(self._quit)
        menu.addAction(self._quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def update_status(self, status: str):
        if status in ("rodando", "live_detectada"):
            self._toggle_act.setText("Parar Bot")
        else:
            self._toggle_act.setText("Iniciar Bot")

    def _show_window(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _toggle_bot(self):
        if self._bot.is_running:
            self._bot.stop()
        else:
            self._bot.start()

    def _on_activated(self, reason: int):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _quit(self):
        if self._bot.is_running:
            self._bot.stop()
        QApplication.quit()
        # Forca a saida completa do processo
        import os
        os._exit(0)
