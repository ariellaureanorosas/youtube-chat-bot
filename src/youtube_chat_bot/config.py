import os
import sys
from pathlib import Path

import yaml

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    _cfg = BASE_DIR / "config.yaml"
    if not _cfg.exists():
        _cfg = Path(sys._MEIPASS) / "config.yaml"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    _cfg = BASE_DIR / "config.yaml"

CONFIG_PATH = Path(os.environ.get("YOUTUBE_CHAT_BOT_CONFIG", str(_cfg)))

PROFILE_DIR = BASE_DIR / "browser_profile"
LOG_DIR = BASE_DIR / "logs"
RESPONDED_PATH = BASE_DIR / "responded_messages.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuracao nao encontrada: {CONFIG_PATH}\n"
            "Copie config.yaml.example para config.yaml "
            "e configure o canal."
        )
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))