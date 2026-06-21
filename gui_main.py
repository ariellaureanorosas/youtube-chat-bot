#!/usr/bin/env python3
"""
YouTube Chat Bot - Interface Grafica
=====================================
Inicia o bot com interface grafica e icone na bandeja do sistema.
Use este script em vez de youtube_chat_bot.py para o modo GUI.

Comportamento da bandeja:
  - Inicia minimizado (so o icone na bandeja)
  - Fechar/minimizar a janela esconde para a bandeja
  - Unica saida: botao "Sair" no menu da bandeja
"""

import asyncio
import logging
import signal
import sys

from qasync import QApplication, QEventLoop

from gui.bot_controller import BotController
from gui.log_handler import QtLogHandler
from gui.main_window import MainWindow
from gui.tray_manager import TrayManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Chat Bot - TV IEBT")
    app.setQuitOnLastWindowClosed(False)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    bot_controller = BotController()
    window = MainWindow(bot_controller)
    tray = TrayManager(window, bot_controller)

    bot_controller.status_changed.connect(window.update_status)
    bot_controller.status_changed.connect(tray.update_status)

    log_handler = QtLogHandler()
    log_handler.log_received.connect(window.append_log)
    logging.getLogger("youtube_chat_bot").addHandler(log_handler)

    window.hide()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
