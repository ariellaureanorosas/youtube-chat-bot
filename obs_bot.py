#!/usr/bin/env python3
"""
YouTube Chat Bot — Modo OBS (Wrapper)
======================================
Inicia a GUI unificada em modo OBS.

Este script agora delega para a GUI unificada (gui_main.py).
O modo OBS é controlado pelo config.yaml (obs.enabled) ou
pela flag --obs.

Uso:
    python obs_bot.py              # modo definido pelo config.yaml
    python obs_bot.py --no-obs     # força modo manual (polling YouTube)
    python obs_bot.py --no-tray    # (ignorado na GUI — bandeja sempre presente)
"""

import sys

FLAGS = ["--obs"]

if "--no-obs" in sys.argv:
    FLAGS = []
elif "--no-tray" in sys.argv:
    pass

sys.argv = [sys.argv[0], *FLAGS, *(a for a in sys.argv[1:]
              if a not in ("--no-obs", "--no-tray"))]

import gui_main
gui_main.main()
