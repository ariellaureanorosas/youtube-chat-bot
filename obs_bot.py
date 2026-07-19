#!/usr/bin/env python3
"""
YouTube Chat Bot — Modo OBS
============================
Inicia e para automaticamente o bot de chat conforme a transmissão
ao vivo do OBS Studio.

Se o OBS não estiver disponível (desconectado ou obs.enabled=false),
funciona como o youtube_chat_bot.py normal (polling YouTube).

Uso:
    python obs_bot.py                   # modo OBS (se configurado)
    python obs_bot.py --no-obs          # força modo polling YouTube
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from obs_monitor import OBSMonitor
from youtube_chat_bot import YoutubeChatBot, _setup_logging, CONFIG_PATH

log = logging.getLogger("obs_bot")


class OBSBotLauncher:
    """Orquestra o bot de acordo com o status do OBS Studio."""

    def __init__(self, config: dict) -> None:
        self.config = config

        # Config do OBS
        obs_cfg = config.get("obs", {})
        self._obs_enabled = obs_cfg.get("enabled", False)

        self._obs = OBSMonitor(
            host=obs_cfg.get("host", "localhost"),
            port=obs_cfg.get("port", 4455),
            password=obs_cfg.get("password", ""),
            poll_interval=obs_cfg.get("poll_interval", 2.0),
        )
        self._obs.on_stream_started = self._on_stream_started
        self._obs.on_stream_stopped = self._on_stream_stopped

        self._bot: YoutubeChatBot | None = None
        self._bot_task: asyncio.Task | None = None
        self._running: bool = True

    # -----------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------

    async def run(self, force_no_obs: bool = False) -> None:
        """Loop principal.

        Args:
            force_no_obs: True força modo polling YouTube mesmo com OBS configurado.
        """
        log.info("=" * 58)
        log.info("  YOUTUBE CHAT BOT — TV IEBT")
        if not force_no_obs and self._obs_enabled:
            log.info("  MODO:      OBS (inicia/para com a transmissão)")
        else:
            log.info("  MODO:      Polling YouTube (autônomo)")
        log.info("=" * 58)

        if force_no_obs or not self._obs_enabled:
            # ── Modo autônomo (polling YouTube) ──
            log.info("Rodando em modo autônomo (polling YouTube a cada 30s)...")
            bot = YoutubeChatBot(self.config)
            try:
                await bot.run()
            except KeyboardInterrupt:
                log.info("Bot parado pelo usuário.")
            return

        # ── Modo OBS ──
        obs_ok = await self._obs.connect()

        if not obs_ok:
            log.warning(
                "OBS não disponível — "
                "verifique se o OBS está aberto e o WebSocket ativado.\n"
                "  OBS Studio → Ferramentas → WebSocket Server Settings\n"
                "Rodando em modo autônomo como fallback..."
            )
            bot = YoutubeChatBot(self.config)
            try:
                await bot.run()
            except KeyboardInterrupt:
                log.info("Bot parado pelo usuário.")
            return

        # OBS conectado — inicia monitoramento
        await self._obs.start_monitoring()

        if self._obs.is_streaming:
            log.info("📡 OBS já está transmitindo — iniciando bot imediatamente!")
            await self._on_stream_started()

        log.info("📡 Aguardando sinal do OBS... (Ctrl+C para parar)")

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            log.info("Encerrando...")

    async def shutdown(self) -> None:
        """Desliga tudo: bot, monitor OBS e conexões."""
        log.info("Desligando...")
        self._running = False
        await self._stop_bot()
        await self._obs.stop_monitoring()
        self._obs.disconnect()

    # -----------------------------------------------------------------
    # Callbacks do OBS
    # -----------------------------------------------------------------

    async def _on_stream_started(self) -> None:
        """OBS começou a transmitir → inicia o bot."""
        if self._bot_task and not self._bot_task.done():
            log.info("Bot já está rodando.")
            return
        log.info("📡 OBS transmitindo — iniciando bot...")
        self._bot_task = asyncio.create_task(self._run_bot())

    async def _on_stream_stopped(self) -> None:
        """OBS parou de transmitir → para o bot."""
        log.info("📡 OBS parou — parando bot...")
        await self._stop_bot()

    # -----------------------------------------------------------------
    # Controle do bot
    # -----------------------------------------------------------------

    async def _run_bot(self) -> None:
        """Wrapper que roda o bot e captura erros."""
        try:
            self._bot = YoutubeChatBot(self.config)
            await self._bot.run()
        except asyncio.CancelledError:
            log.info("Bot cancelado (OBS parou).")
            raise
        except Exception as e:
            log.error(f"Bot encerrou com erro: {e}", exc_info=True)
            # Se o bot cair com erro, tenta de novo em 10s se OBS ainda estiver ligado
            if self._obs.is_streaming and self._running:
                log.info("Tentando reiniciar bot em 10s...")
                await asyncio.sleep(10)
                if self._obs.is_streaming and self._running:
                    self._bot_task = asyncio.create_task(self._run_bot())
        finally:
            self._bot = None
            self._bot_task = None

    async def _stop_bot(self) -> None:
        """Para o bot se estiver rodando."""
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


# =====================================================================
# CLI
# =====================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube Chat Bot — Modo OBS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python obs_bot.py              # modo OBS (se configurado)\n"
            "  python obs_bot.py --no-obs     # força polling YouTube\n"
        ),
    )
    parser.add_argument(
        "--no-obs",
        action="store_true",
        help="Ignora configuração OBS e roda em modo polling YouTube",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _setup_logging(cfg)

    launcher = OBSBotLauncher(cfg)
    try:
        await launcher.run(force_no_obs=args.no_obs)
    except KeyboardInterrupt:
        log.info("Encerrado pelo usuário.")
    finally:
        await launcher.shutdown()
        logging.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
