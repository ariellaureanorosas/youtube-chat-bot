#!/usr/bin/env python3
import asyncio
import logging
import sys
import time
from datetime import datetime

from playwright.async_api import async_playwright, Page

from youtube_chat_bot.ai_responder import AIResponder
from youtube_chat_bot.browser_utils import BROWSER_PATH, ANTI_DETECT_SCRIPT
from youtube_chat_bot.config import (
    CONFIG_PATH,
    LOG_DIR,
    PROFILE_DIR,
    RESPONDED_PATH,
    load_config,
)
from youtube_chat_bot.live_chat import LiveChatClient
from youtube_chat_bot.response_router import ResponseRouter
from youtube_chat_bot.storage import MessageStore

log = logging.getLogger("youtube_chat_bot")


class YoutubeChatBot:
    def __init__(self, cfg: dict) -> None:
        self.config = cfg
        self.channel: str = cfg["channel"]["name"].lstrip("@")
        self.s: dict = cfg["settings"]
        self.rules: list[dict] = cfg["response_rules"]
        self.default_resp: dict = cfg["default_response"]

        self.ai = AIResponder(cfg.get("ai", {}))
        self.ai_mode: str = cfg.get("ai", {}).get("mode", "off")
        self.resposta_biblica: str = cfg.get("ai", {}).get(
            "resposta_pergunta_biblica",
            "Essa é uma ótima pergunta! Para uma orientação mais pessoal "
            "e segura, recomendamos conversar com nossa equipe pastoral "
            "na igreja. Deus abençoe! 🙏",
        )
        horarios = self.ai.culto_horarios
        if horarios:
            self.resposta_horario: str = (
                "Nossos cultos acontecem nos seguintes horários: "
                + "; ".join(horarios)
                + ". Ficaremos felizes em te receber! 🙏"
            )
        else:
            self.resposta_horario: str = (
                "Para saber os horários dos nossos cultos, acompanhe "
                "as nossas redes sociais oficiais. Deus abençoe! 🙏"
            )

        self.router = ResponseRouter(
            ai=self.ai,
            rules=self.rules,
            default_resp=self.default_resp,
            resposta_biblica=self.resposta_biblica,
            resposta_horario=self.resposta_horario,
        )

        self.client = LiveChatClient(self.channel)

        self._last_msg_at: float = 0.0
        self._minute_count: int = 0
        self._minute_start: float = time.time()
        self.store = MessageStore(RESPONDED_PATH)
        self.store.load()
        self._last_save: float = self.store.last_save
        self._save_interval: int = self.s.get("save_interval", 300)
        self._sent: set[str] = set()
        self._sent_responses: dict[str, float] = {}
        self._own_channel_name: str | None = None
        self._last_video_id: str | None = None
        self._running: bool = True

    def _load_responded(self) -> None:
        self.store.load()
        self._last_save = self.store.last_save

    def _save_responded(self) -> None:
        self.store.save()
        self._last_save = self.store.last_save

    def stop(self) -> None:
        """Solicita parada graciosa do bot (pode ser chamado de qualquer thread)."""
        self._running = False

    async def run(self) -> None:
        log.info("=" * 58)
        log.info("  YOUTUBE LIVE CHAT BOT")
        log.info(f"  CANAL: @{self.channel}")
        mode_label = {
            "ai": "IA TOTAL",
            "hybrid": "HIBRIDO (IA + regras)",
            "off": "REGRAS FIXAS",
        }
        log.info(f"  MODO:  {mode_label.get(self.ai_mode, 'DESCONHECIDO')}")
        log.info("=" * 58)

        async with async_playwright() as pw:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                executable_path=BROWSER_PATH,
                headless=self.s.get("headless", False),
                locale=self.s.get("language", "pt"),
                viewport={"width": 420, "height": 680},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/149.0.0.0 Safari/537.36"
                ),
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            await ctx.add_init_script(ANTI_DETECT_SCRIPT)

            # Uma unica aba reutilizada: evita recriar paginas
            # (e piscar "about:blank") a cada ciclo de verificacao.
            page = await ctx.new_page()
            try:
                while self._running:
                    video_id = await self.client.find_live(page)
                    if video_id:
                        log.info(f"AO VIVO! ID: {video_id}")
                        await self._monitor_chat_with_retry(page, video_id)
                        log.info("Stream encerrada.")
                    else:
                        log.info(
                            "Nenhuma live no ar. "
                            "Verifico a cada 30s..."
                        )
                        await asyncio.sleep(30)
            except KeyboardInterrupt:
                log.info("Bot parado pelo usuario.")
            finally:
                await page.close()
                await self.ai.close()
                await ctx.close()

    async def _monitor_chat_with_retry(
        self, page: Page, video_id: str
    ) -> None:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._monitor_chat(page, video_id)
                return
            except Exception as e:
                log.warning(
                    f"Monitor falhou (tentativa {attempt + 1}/"
                    f"{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(10 * (2**attempt))

    async def _detect_own_channel(self, page: Page) -> None:
        if self._own_channel_name:
            return
        own_name = await self.client.detect_own_channel(page)
        if own_name:
            self._own_channel_name = own_name

    async def _monitor_chat(
        self, page: Page, video_id: str
    ) -> None:
        await self.client.open_live_chat(page, video_id)

        if video_id != self._last_video_id:
            self.store.seen.clear()
            log.info("Live nova, limpando historico de mensagens")
        else:
            log.info(
                f"Mesma live, mantendo "
                f"{len(self.store.seen)} mensagens no historico"
            )
        self._last_video_id = video_id
        self._sent.clear()
        self._sent_responses.clear()
        self.router._rule_cooldowns.clear()
        self._last_msg_at = 0.0
        self._minute_count = 0
        self._minute_start = time.time()
        self._last_save = time.time()

        await self._detect_own_channel(page)
        log.info("Monitorando chat... (Ctrl+C para parar)")

        try:
            while self._running:
                if "live_chat" not in page.url and "watch" not in page.url:
                    log.info("Redirecionado — stream encerrou.")
                    break
                await self._poll_messages(page)
                await asyncio.sleep(self.s.get("check_interval", 5))
        except Exception as exc:
            log.warning(f"Erro no monitor: {exc}")
            raise
        finally:
            self._save_responded()

    async def _poll_messages(self, page: Page) -> None:
        if not self._own_channel_name:
            await self._detect_own_channel(page)

        if time.time() - self._last_save >= self._save_interval:
            self._save_responded()

        mensagens = await self.client.fetch_messages(page)

        for author, text in mensagens:
            try:
                if (
                    self._own_channel_name
                    and author == self._own_channel_name
                ):
                    continue

                if text in self._sent:
                    log.info(
                        f"Ja enviei '{text[:40]}...', pulando"
                    )
                    continue

                key = f"{author}|{text}"
                if key in self.store.seen:
                    continue

                # Rate limit centralizado AQUI
                now = time.time()
                if (
                    now - self._last_msg_at
                    < self.s.get("min_response_interval", 20)
                ):
                    continue
                if now - self._minute_start >= 60:
                    self._minute_count = 0
                    self._minute_start = now
                if (
                    self._minute_count
                    >= self.s.get("max_responses_per_minute", 4)
                ):
                    continue

                log.info(f"{author}: {text}")

                try:
                    resp = await self._decide_response(author, text)
                    if resp:
                        dedup_secs = self.s.get("response_dedup_interval", 120)
                        if resp in self._sent_responses:
                            elapsed = time.time() - self._sent_responses[resp]
                            if elapsed < dedup_secs:
                                log.info(
                                    f"Resposta repetida '{resp[:40]}...' "
                                    f"enviada ha {elapsed:.0f}s, pulando"
                                )
                                continue
                        self._sent_responses[resp] = time.time()
                        if len(self._sent_responses) > 100:
                            cutoff = time.time() - 300
                            self._sent_responses = {
                                k: v
                                for k, v in self._sent_responses.items()
                                if v > cutoff
                            }
                        self._sent.add(text)
                        if len(self._sent) > 500:
                            self._sent = set(
                                list(self._sent)[-250:]
                            )
                        await self._send(page, resp)
                        self._last_msg_at = time.time()
                        self._minute_count += 1
                finally:
                    self.store.add(key)

            except Exception:
                continue

    @staticmethod
    def _should_discard(raw: str) -> bool:
        return ResponseRouter.should_discard(raw)

    def _is_bible_question(self, raw: str) -> bool:
        return self.router.is_bible_question(raw)

    def _is_horario_question(self, raw: str) -> bool:
        return self.router.is_horario_question(raw)

    async def _decide_response(
        self, author: str, message: str
    ) -> str | None:
        return await self.router.decide(author, message, self.ai_mode)

    def _apply_rule(self, idx: int, rule: dict) -> str | None:
        return self.router._apply_rule(idx, rule)

    def _default_response(self) -> str | None:
        return self.router._default_response()


    async def _send(self, page: Page, text: str) -> None:
        await self.client.send(page, text)


def _setup_logging(cfg: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    level = getattr(
        logging,
        cfg.get("settings", {}).get("log_level", "INFO").upper(),
        logging.INFO,
    )
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def main() -> None:
    cfg = load_config()
    _setup_logging(cfg)
    bot = YoutubeChatBot(cfg)
    try:
        await bot.run()
    except KeyboardInterrupt:
        log.info("Bot parado pelo usuario.")
    finally:
        logging.shutdown()


if __name__ == "__main__":
    asyncio.run(main())