import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
from PySide6.QtCore import QObject, Signal

from obs_monitor import OBSMonitor
from youtube_chat_bot import YoutubeChatBot

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    _cfg = BASE_DIR / "config.yaml"
    if not _cfg.exists():
        _cfg = Path(sys._MEIPASS) / "config.yaml"
else:
    BASE_DIR = Path(__file__).parent.parent
    _cfg = BASE_DIR / "config.yaml"
CONFIG_PATH = Path(
    os.environ.get("YOUTUBE_CHAT_BOT_CONFIG", str(_cfg))
)

log = logging.getLogger("youtube_chat_bot")


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


class BotController(QObject):
    status_changed = Signal(str)
    obs_status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._task: asyncio.Task | None = None
        self._bot: YoutubeChatBot | None = None
        self._bot_task: asyncio.Task | None = None
        self._obs: OBSMonitor | None = None
        self._obs_enabled: bool = False
        self._running: bool = False

    # -----------------------------------------------------------------
    # OBS mode
    # -----------------------------------------------------------------

    async def _start_obs_mode(self, cfg: dict, obs_cfg: dict) -> None:
        self._obs = OBSMonitor(
            host=obs_cfg.get("host", "localhost"),
            port=obs_cfg.get("port", 4455),
            password=obs_cfg.get("password", ""),
            poll_interval=obs_cfg.get("poll_interval", 2.0),
        )
        self._obs.on_stream_started = self._on_stream_started
        self._obs.on_stream_stopped = self._on_stream_stopped

        obs_ok = await self._obs.connect()
        if not obs_ok:
            self.obs_status_changed.emit("offline")
            log.warning("OBS offline — modo manual como fallback")
            self.status_changed.emit("rodando (fallback)")
            await self._run_bot_instance(cfg)
            return

        self.obs_status_changed.emit("conectado")
        self.status_changed.emit("aguardando transmissão...")
        await self._obs.start_monitoring()

        if self._obs.is_streaming:
            await self._on_stream_started()

        while self._running:
            await asyncio.sleep(1)

    async def _on_stream_started(self) -> None:
        if self._bot_task and not self._bot_task.done():
            return
        self.obs_status_changed.emit("transmitindo")
        self.status_changed.emit("rodando (OBS)")
        cfg = load_config()
        self._bot_task = asyncio.create_task(self._run_bot_instance(cfg))

    async def _on_stream_stopped(self) -> None:
        self.obs_status_changed.emit("conectado")
        self.status_changed.emit("aguardando transmissão...")
        if self._bot:
            self._bot._running = False
        if self._bot_task and not self._bot_task.done():
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass
        self._bot = None
        self._bot_task = None

    # -----------------------------------------------------------------
    # Core
    # -----------------------------------------------------------------

    async def _run(self) -> None:
        cfg = load_config()
        self._running = True
        obs_cfg = cfg.get("obs", {})
        self._obs_enabled = obs_cfg.get("enabled", False)

        if self._obs_enabled:
            await self._start_obs_mode(cfg, obs_cfg)
        else:
            self.status_changed.emit("rodando")
            await self._run_bot_instance(cfg)

        self._running = False
        self._task = None
        self.status_changed.emit("parado")
        self.obs_status_changed.emit("desligado")

    async def _run_bot_instance(self, cfg: dict) -> None:
        try:
            self._bot = YoutubeChatBot(cfg)
            self._bot_task = asyncio.current_task()
            await self._bot.run()
        except asyncio.CancelledError:
            self._do_stop()
        except Exception as e:
            log.error(f"Bot encerrou com erro: {e}", exc_info=True)
            self.status_changed.emit("erro")
        finally:
            self._bot = None
            self._bot_task = None

    def _do_stop(self):
        if self._bot:
            self._bot._running = False

    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    def stop(self):
        self._running = False
        self._do_stop()
        if self._obs:
            asyncio.create_task(self._obs.stop_monitoring())
        if self._task and not self._task.done():
            self._task.cancel()

    def cleanup(self):
        if self._obs:
            self._obs.disconnect()
            self._obs = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()
