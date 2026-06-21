#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from playwright.async_api import async_playwright, Page

from ai_responder import AIResponder
from browser_utils import BROWSER_PATH, ANTI_DETECT_SCRIPT

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    _cfg = BASE_DIR / "config.yaml"
    if not _cfg.exists():
        _cfg = Path(sys._MEIPASS) / "config.yaml"
else:
    BASE_DIR = Path(__file__).parent
    _cfg = BASE_DIR / "config.yaml"
CONFIG_PATH = Path(
    os.environ.get("YOUTUBE_CHAT_BOT_CONFIG", str(_cfg))
)
PROFILE_DIR = BASE_DIR / "browser_profile"
LOG_DIR = BASE_DIR / "logs"
RESPONDED_PATH = BASE_DIR / "responded_messages.json"

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
        self._allow_fallback: bool = cfg.get("ai", {}).get(
            "fallback_to_rules", True
        )

        self._rule_cooldowns: dict[str | int, float] = {}
        self._last_msg_at: float = 0.0
        self._minute_count: int = 0
        self._minute_start: float = time.time()
        self._seen: set[str] = set()
        self._last_save: float = time.time()
        self._save_interval: int = self.s.get("save_interval", 300)
        self._load_responded()
        self._sent: set[str] = set()
        self._sent_responses: dict[str, float] = {}
        self._own_channel_name: str | None = None
        self._last_video_id: str | None = None
        self._running: bool = True

    def _load_responded(self) -> None:
        try:
            if RESPONDED_PATH.exists():
                data = json.loads(RESPONDED_PATH.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._seen = set(data)
                    log.info(
                        f"Carregadas {len(self._seen)} mensagens "
                        f"ja processadas"
                    )
        except Exception as e:
            log.warning(f"Erro ao carregar responded_messages.json: {e}")

    def _save_responded(self) -> None:
        try:
            RESPONDED_PATH.write_text(
                json.dumps(list(self._seen), ensure_ascii=False),
                encoding="utf-8",
            )
            self._last_save = time.time()
        except Exception as e:
            log.warning(f"Erro ao salvar responded_messages.json: {e}")

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

            try:
                while self._running:
                    video_id = await self._find_live(ctx)
                    if video_id:
                        log.info(f"AO VIVO! ID: {video_id}")
                        await self._monitor_chat_with_retry(ctx, video_id)
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
                await self.ai.close()
                await ctx.close()

    async def _find_live(self, ctx: Any) -> str | None:
        page = await ctx.new_page()
        try:
            url = f"https://www.youtube.com/@{self.channel}/live"
            log.info(f"Checando {url}")
            await page.goto(
                url, wait_until="domcontentloaded", timeout=25_000
            )

            try:
                await page.wait_for_selector(
                    "ytd-watch-flexy, ytd-rich-item-renderer, #contents",
                    timeout=10_000,
                )
            except Exception:
                pass

            video_id = None

            m = re.search(r"[?&]v=([\w-]{11})", page.url)
            if m:
                video_id = m.group(1)

            if not video_id:
                try:
                    canon = await page.query_selector(
                        'link[rel="canonical"]'
                    )
                    if canon:
                        href = await canon.get_attribute("href")
                        if href:
                            m = re.search(r"v=([\w-]{11})", href)
                            if m:
                                video_id = m.group(1)
                except Exception:
                    pass

            if not video_id:
                try:
                    vid = await page.evaluate("""
                        () => {
                            function extractId() {
                                const el = document.querySelector(
                                    'ytd-watch-flexy'
                                );
                                if (el) return el.getAttribute('video-id');
                                if (
                                    window.ytInitialPlayerResponse
                                    ?.videoDetails?.videoId
                                )
                                    return window
                                        .ytInitialPlayerResponse
                                        .videoDetails.videoId;
                                const scripts =
                                    document.querySelectorAll('script');
                                for (const s of scripts) {
                                    const t = s.textContent || '';
                                    const m = t.match(
                                        /videoId["']?\\s*[:=]\\s*["']
                                        ([\\w-]{11})["']/
                                    );
                                    if (m) return m[1];
                                }
                                return null;
                            }
                            const badges = document.querySelectorAll(
                                '.badge-style-type-live, yt-icon-badge, '
                                + '[label="AO VIVO"], [label="LIVE"]'
                            );
                            for (const b of badges) {
                                const txt =
                                    b.textContent.trim().toUpperCase();
                                if (
                                    txt.includes('AO VIVO')
                                    || txt.includes('LIVE')
                                ) {
                                    return extractId();
                                }
                            }
                            return null;
                        }
                    """)
                    if vid and len(vid) == 11:
                        video_id = vid
                except Exception:
                    pass

            if video_id:
                return video_id

            log.info(f"Nenhuma live no ar. URL: {page.url}")
            return None
        except Exception as exc:
            log.warning(f"Erro ao checar live: {exc}")
            return None
        finally:
            await page.close()

    async def _monitor_chat_with_retry(
        self, ctx: Any, video_id: str
    ) -> None:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._monitor_chat(ctx, video_id)
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
        try:
            own_name = await page.evaluate("""
                () => {
                    const ownerItems = document.querySelectorAll(
                        'yt-live-chat-text-message-renderer'
                        + '[author-type="owner"]'
                    );
                    for (const item of ownerItems) {
                        const nameEl =
                            item.querySelector('#author-name');
                        if (nameEl)
                            return nameEl.textContent.trim();
                    }
                    const items = document.querySelectorAll(
                        'yt-live-chat-text-message-renderer'
                    );
                    for (const item of items) {
                        const badge =
                            item.querySelector('#author-badge');
                        if (badge) {
                            const txt =
                                badge.textContent.trim();
                            if (
                                txt.includes('Voce')
                                || txt.includes('You')
                            ) {
                                const nameEl =
                                    item.querySelector('#author-name');
                                if (nameEl)
                                    return nameEl.textContent.trim();
                            }
                        }
                    }
                    return null;
                }
            """)
            if own_name:
                self._own_channel_name = own_name
                log.info(f"Nome do canal detectado: {own_name}")
        except Exception as e:
            log.debug(f"Detecao de canal: {e}")

    async def _monitor_chat(
        self, ctx: Any, video_id: str
    ) -> None:
        chat_url = (
            f"https://www.youtube.com/live_chat"
            f"?is_popout=1&v={video_id}"
        )
        page = await ctx.new_page()
        await page.goto(
            chat_url, wait_until="domcontentloaded", timeout=20_000
        )

        try:
            await page.wait_for_selector(
                "yt-live-chat-text-message-renderer", timeout=15_000
            )
        except Exception:
            log.warning(
                "Chat nao renderizou a tempo, continuando..."
            )

        if video_id != self._last_video_id:
            self._seen.clear()
            log.info("Live nova, limpando historico de mensagens")
        else:
            log.info(
                f"Mesma live, mantendo "
                f"{len(self._seen)} mensagens no historico"
            )
        self._last_video_id = video_id
        self._sent.clear()
        self._sent_responses.clear()
        self._rule_cooldowns.clear()
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
            await page.close()

    async def _poll_messages(self, page: Page) -> None:
        if not self._own_channel_name:
            await self._detect_own_channel(page)

        if time.time() - self._last_save >= self._save_interval:
            self._save_responded()

        try:
            els = await page.query_selector_all(
                "yt-live-chat-text-message-renderer"
            )
        except Exception:
            return

        for el in els:
            try:
                author_el = await el.query_selector("#author-name")
                msg_el = await el.query_selector("#message")
                if not msg_el:
                    continue

                author = (
                    (await author_el.inner_text()).strip()
                    if author_el
                    else "?"
                )
                text = (await msg_el.inner_text()).strip()
                if not text:
                    continue

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
                if key in self._seen:
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
                    self._seen.add(key)
                    if len(self._seen) > 2000:
                        self._seen = set(
                            list(self._seen)[-1000:]
                        )

            except Exception:
                continue

    async def _decide_response(
        self, author: str, message: str
    ) -> str | None:
        raw = message.lower().strip()
        if not raw:
            return None

        resolved_keyword = ""
        matched_rule = None
        matched_idx = -1

        for idx, rule in enumerate(self.rules):
            if not rule.get("enabled", True):
                continue
            for kw in rule["keywords"]:
                if kw.lower() in raw:
                    resolved_keyword = kw
                    matched_idx = idx
                    matched_rule = rule
                    break
            if matched_rule:
                break

        if self.ai_mode == "ai" and self.ai.enabled:
            ai_resp = await self.ai.generate(author, message)
            if ai_resp:
                return ai_resp
            if self._allow_fallback and matched_rule and not self.ai._last_skipped:
                log.info("Fallback: IA falhou, usando regra fixa")
                return self._apply_rule(matched_idx, matched_rule)
            if self.ai._last_skipped:
                log.debug(
                    f"IA pulou intencionalmente (SKIP): "
                    f"{author}: {message[:60]}"
                )
            return None

        if self.ai_mode == "hybrid":
            if matched_rule:
                last = self._rule_cooldowns.get(matched_idx, 0.0)
                if time.time() - last < matched_rule.get("cooldown", 20):
                    return None
                self._rule_cooldowns[matched_idx] = time.time()

                if self.ai.enabled:
                    ai_resp = await self.ai.generate(
                        author, message, resolved_keyword
                    )
                    if ai_resp:
                        return ai_resp
                return matched_rule["response"]
            return None

        if matched_rule:
            return self._apply_rule(matched_idx, matched_rule)
        return self._default_response()

    def _apply_rule(self, idx: int, rule: dict) -> str | None:
        last = self._rule_cooldowns.get(idx, 0.0)
        if time.time() - last < rule.get("cooldown", 20):
            return None
        self._rule_cooldowns[idx] = time.time()
        return rule["response"]

    def _default_response(self) -> str | None:
        d = self.default_resp
        if not d.get("enabled", True):
            return None
        last = self._rule_cooldowns.get("__default__", 0.0)
        if time.time() - last < d.get("cooldown", 10):
            return None
        self._rule_cooldowns["__default__"] = time.time()
        return d["response"]

    async def _send(self, page: Page, text: str) -> None:
        log.info(f"-> {text}")

        frames = [page] + [f for f in page.frames]
        selectors = (
            "yt-live-chat-text-input-field-renderer div#input",
            "yt-live-chat-message-input-renderer #input",
            "#input",
            "[contenteditable]",
            "div#input",
            "#chat-input",
            "#message-input",
        )

        # Metodo visual
        for target in frames:
            for sel in selectors:
                try:
                    inp = await target.query_selector(sel)
                    if inp is None:
                        continue

                    await inp.focus()
                    await asyncio.sleep(0.3)
                    await inp.fill("")
                    await asyncio.sleep(0.3)
                    await inp.type(text, delay=0.05)
                    await asyncio.sleep(0.5)
                    await target.keyboard.press("Enter")
                    await asyncio.sleep(1.5)

                    cleared = await target.evaluate("""
                        () => {
                            const ce = document.querySelector(
                                '[contenteditable]'
                            );
                            if (!ce) return false;
                            return ce.textContent.trim().length === 0;
                        }
                    """)
                    if cleared:
                        log.info("Enviado! (visual)")
                        return

                    await target.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    cleared = await target.evaluate("""
                        () => {
                            const ce = document.querySelector(
                                '[contenteditable]'
                            );
                            return ce
                                ? ce.textContent.trim().length === 0
                                : false;
                        }
                    """)
                    if cleared:
                        log.info("Enviado! (Enter2)")
                        return
                except Exception:
                    continue

        # Fallback JS
        log.info("Tentando fallback via JavaScript...")
        safe = (
            text.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
        )

        for target in frames:
            try:
                result = await target.evaluate(
                    """
                    (text) => {
                        function findInput(container) {
                            let el = container.querySelector(
                                '#input, div#input, '
                                + '[contenteditable], textarea'
                            );
                            if (el) return el;
                            if (container.shadowRoot) {
                                el = container.shadowRoot
                                    .querySelector('#input');
                                if (el) return el;
                            }
                            const r = container.querySelector(
                                'yt-live-chat-text-input-field-renderer'
                            );
                            if (r && r.shadowRoot) {
                                el = r.shadowRoot
                                    .querySelector('#input');
                                if (el) return el;
                            }
                            return null;
                        }
                        const inp = findInput(document);
                        if (!inp) return 'NF';
                        inp.focus();
                        if (inp.isContentEditable) {
                            inp.textContent = '';
                            document.execCommand(
                                'insertText', false, text
                            );
                            return 'CE';
                        }
                        if (
                            inp.tagName === 'TEXTAREA'
                            || inp.tagName === 'INPUT'
                        ) {
                            inp.value = text;
                            return inp.tagName;
                        }
                        inp.textContent = text;
                        return 'TXT';
                    }
                """,
                    safe,
                )

                if result and result != "NF":
                    await asyncio.sleep(0.5)
                    await target.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    log.info("Enviado! (JS + Enter)")
                    return
            except Exception as e:
                log.debug(f"JS erro: {str(e)[:100]}")

        log.warning("Todos os metodos de envio falharam")


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
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
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
