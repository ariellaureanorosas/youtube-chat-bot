#!/usr/bin/env python3
"""
Monitor OBS Studio — Detecta quando a transmissão ao vivo inicia/para
======================================================================
Conecta ao WebSocket do OBS Studio e notifica por callback quando
o status de streaming muda.

Uso:
    monitor = OBSMonitor(host="localhost", port=4455, password="")
    monitor.on_stream_started = minha_callback_start
    monitor.on_stream_stopped = minha_callback_stop
    await monitor.connect()
    await monitor.start_monitoring()
    ...
    await monitor.stop_monitoring()
    monitor.disconnect()
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Coroutine, Any

log = logging.getLogger("obs_monitor")


class OBSMonitor:
    """Monitora status de transmissão do OBS Studio via WebSocket."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4455,
        password: str = "",
        poll_interval: float = 2.0,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.poll_interval = poll_interval

        self._req: Any = None  # ReqClient
        self._connected: bool = False
        self._streaming: bool = False
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="obs"
        )

        # Callbacks assíncronos — atribuir antes de start_monitoring()
        self.on_stream_started: Callable[[], Coroutine[Any, Any, None]] | None = None
        self.on_stream_stopped: Callable[[], Coroutine[Any, Any, None]] | None = None

    # -----------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------

    async def connect(self) -> bool:
        """Tenta conectar ao OBS WebSocket.

        Returns:
            True se conectou, False caso contrário.
        """
        try:
            import obsws_python as obs

            loop = asyncio.get_event_loop()

            self._req = await loop.run_in_executor(
                self._executor,
                lambda: obs.ReqClient(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    timeout=3,
                ),
            )

            resp = await loop.run_in_executor(
                self._executor, self._req.get_version
            )
            log.info(
                "Conectado ao OBS Studio "
                f"(v{resp.obs_version}, WebSocket v{resp.rpc_version})"
            )

            status = await loop.run_in_executor(
                self._executor, self._req.get_stream_status
            )
            self._streaming = bool(status.output_active)
            log.info(
                "Status do streaming: "
                f"{'🔴 AO VIVO' if self._streaming else '⏸️ DESLIGADO'}"
            )

            self._connected = True
            return True
        except Exception as e:
            log.warning(f"Não foi possível conectar ao OBS: {e}")
            self._connected = False
            return False

    async def start_monitoring(self) -> None:
        """Inicia o loop de monitoramento (polling)."""
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop_monitoring(self) -> None:
        """Para o loop de monitoramento."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def disconnect(self) -> None:
        """Desconecta do OBS e libera recursos."""
        self._running = False
        if self._req:
            try:
                self._req.disconnect()
            except Exception:
                pass
            self._req = None
        self._executor.shutdown(wait=False)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_streaming(self) -> bool:
        return self._streaming

    # -----------------------------------------------------------------
    # Loop interno
    # -----------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Polling periódico do status de streaming."""
        prev = self._streaming
        while self._running:
            try:
                loop = asyncio.get_event_loop()

                status = await loop.run_in_executor(
                    self._executor, self._req.get_stream_status
                )
                curr = bool(status.output_active)

                if curr != prev:
                    self._streaming = curr
                    if curr:
                        log.info("📡 OBS INICIOU a transmissão!")
                        if self.on_stream_started:
                            await self.on_stream_started()
                    else:
                        log.info("📡 OBS PAROU a transmissão.")
                        if self.on_stream_stopped:
                            await self.on_stream_stopped()
                prev = curr
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning(f"Erro no monitoramento OBS: {e}")
            await asyncio.sleep(self.poll_interval)
