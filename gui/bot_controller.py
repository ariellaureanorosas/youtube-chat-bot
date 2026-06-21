import asyncio
import logging
import os
from pathlib import Path

import yaml
from PySide6.QtCore import QObject, Signal

from youtube_chat_bot import YoutubeChatBot

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = Path(
    os.environ.get(
        "YOUTUBE_CHAT_BOT_CONFIG", str(BASE_DIR / "config.yaml")
    )
)

log = logging.getLogger("youtube_chat_bot")


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


class BotController(QObject):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._task: asyncio.Task | None = None
        self._bot: YoutubeChatBot | None = None

    async def _run_bot(self):
        try:
            cfg = load_config()
            self._bot = YoutubeChatBot(cfg)
            self.status_changed.emit("rodando")
            await self._bot.run()
        except asyncio.CancelledError:
            self._do_stop()
            raise
        except Exception as e:
            log.error(f"Bot encerrou com erro: {e}", exc_info=True)
            self.status_changed.emit("erro")
        finally:
            self._bot = None
            self._task = None
            self.status_changed.emit("parado")

    def _do_stop(self):
        if self._bot:
            self._bot._running = False

    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_bot())

    def stop(self):
        self._do_stop()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()
