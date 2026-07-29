#!/usr/bin/env python3
"""
YouTube Chat Bot - Interface Grafica Unificada
===============================================
Inicia o bot com interface grafica e icone na bandeja do sistema.

Modos:
  - Manual:  usa youtube_chat_bot.py diretamente (polling YouTube)
  - OBS:     integrado ao OBS Studio, inicia/para com a transmissao
             (configurado em config.yaml -> obs.enabled)

Uso:
    python gui_main.py                # modo definido pelo config.yaml
    python gui_main.py --obs          # força modo OBS (mesmo se desligado no config)
    python gui_main.py --no-window    # inicia minimizado direto

Comportamento da bandeja:
  - Inicia minimizado (so o icone na bandeja)
  - Fechar/minimizar a janela esconde para a bandeja
  - Unica saida: botao "Sair" no menu da bandeja
"""

import argparse
import asyncio
import logging
import signal
import sys

from qasync import QApplication, QEventLoop

from gui.bot_controller import BotController, load_config
from gui.log_handler import QtLogHandler
from gui.main_window import MainWindow
from gui.tray_manager import TrayManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube Chat Bot - TV IEBT (GUI Unificada)"
    )
    parser.add_argument(
        "--obs",
        action="store_true",
        help="Força modo OBS (ignora config.yaml -> obs.enabled)",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Inicia minimizado na bandeja (sem mostrar janela)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.obs:
        cfg = load_config()
        cfg.setdefault("obs", {})["enabled"] = True

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
    bot_controller.obs_status_changed.connect(window.update_obs_status)
    bot_controller.obs_status_changed.connect(tray.update_obs_status)

    log_handler = QtLogHandler()
    log_handler.log_received.connect(window.append_log)
    logging.getLogger("youtube_chat_bot").addHandler(log_handler)

    if not args.no_window:
        window.show()

    try:
        with loop:
            loop.run_forever()
    finally:
        bot_controller.cleanup()
        logging.shutdown()


if __name__ == "__main__":
    main()
