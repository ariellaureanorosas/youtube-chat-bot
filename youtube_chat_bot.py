#!/usr/bin/env python3
"""
YouTube Live Chat Bot — Resposta automática para irmãos durante culto ao vivo
================================================================================
Com IA: usa Deepseek (opencode-zen) pra gerar respostas autênticas e variadas.
Fallback: se a IA falhar, usa as respostas fixas do config.yaml.

Funcionamento:
  1. Abre um navegador Chromium (controlado via Playwright)
  2. Verifica se o canal do YouTube está AO VIVO
  3. Se estiver, entra no chat e monitora mensagens
  4. Responde com IA (ou respostas fixas como fallback)
  5. Quando a live acaba, fica esperando a próxima
"""

import asyncio
import json
import os
import re
import shutil
import time
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from playwright.async_api import async_playwright, Page

from ai_responder import AIResponder

# ── PATHS ─────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
PROFILE_DIR = BASE_DIR / "browser_profile"
LOG_DIR = BASE_DIR / "logs"
RESPONDED_PATH = BASE_DIR / "responded_messages.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

config = load_config()
log_level = getattr(logging, config.get("settings", {}).get("log_level", "INFO").upper(), logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("youtube_chat_bot")

# ── ANTI-DETECTION: esconde do Google que é um navegador automatizado ──
ANTI_DETECT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = {
    runtime: { onConnect: { addListener: () => {} } },
    loadTimes: () => {}, csi: () => {}, app: {},
};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: 'prompt' })
        : originalQuery(parameters)
);
"""


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


BROWSER_PATHS = [
    # Brave
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    # Chrome
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # Chromium
    r"C:\Program Files\Chromium\Application\chrome.exe",
    r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
]


def _find_browser() -> str | None:
    for path in BROWSER_PATHS:
        if os.path.isfile(path):
            return path
    return shutil.which("brave") or shutil.which("brave-browser") or shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("google-chrome-stable")


BROWSER_PATH = _find_browser() or "chrome"


class YoutubeChatBot:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.channel: str = config["channel"]["name"].lstrip("@")
        self.s: dict = config["settings"]
        self.rules: list[dict] = config["response_rules"]
        self.default_resp: dict = config["default_response"]

        self.ai = AIResponder(config.get("ai", {}))
        self.ai_mode: str = config.get("ai", {}).get("mode", "off")

        self._rule_cooldowns: dict[str | int, float] = {}
        self._last_msg_at: float = 0.0
        self._minute_count: int = 0
        self._minute_start: float = time.time()
        self._seen: set[str] = set()
        self._load_responded()
        self._sent: set[str] = set()
        self._own_channel_name: str | None = None
        self._last_video_id: str | None = None

    # ── PERSISTÊNCIA (mensagens já processadas sobrevivem a reinícios) ──
    def _load_responded(self) -> None:
        try:
            if RESPONDED_PATH.exists():
                data = json.loads(RESPONDED_PATH.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._seen = set(data)
                    log.info(f"📂 Carregadas {len(self._seen)} mensagens já processadas")
        except Exception as e:
            log.warning(f"⚠️ Erro ao carregar responded_messages.json: {e}")

    def _save_responded(self) -> None:
        try:
            RESPONDED_PATH.write_text(
                json.dumps(list(self._seen), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"⚠️ Erro ao salvar responded_messages.json: {e}")

    # ── MAIN LOOP ──────────────────────────────
    async def run(self):
        log.info("═" * 58)
        log.info("  YOUTUBE LIVE CHAT BOT")
        log.info(f"  CANAL: @{self.channel}")
        mode_label = {"ai": "IA TOTAL", "hybrid": "HÍBRIDO (IA + regras)", "off": "REGRAS FIXAS"}
        log.info(f"  MODO:  {mode_label.get(self.ai_mode, 'DESCONHECIDO')}")
        log.info("═" * 58)

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
            # Anti-detection em todas as abas
            await ctx.add_init_script(ANTI_DETECT_SCRIPT)
            try:
                while True:
                    video_id = await self._find_live(ctx)
                    if video_id:
                        log.info(f"✅ AO VIVO! ID: {video_id}")
                        await self._monitor_chat(ctx, video_id)
                        log.info("📴 Stream encerrada.")
                    else:
                        log.info("💤 Nenhuma live no ar. Verifico a cada 30s...")
                        await asyncio.sleep(30)
            finally:
                await ctx.close()

    # ── FIND LIVE ──────────────────────────────
    async def _find_live(self, ctx: Any) -> str | None:
        page = await ctx.new_page()
        try:
            url = f"https://www.youtube.com/@{self.channel}/live"
            log.info(f"🔍 {url}")
            await page.goto(url, wait_until="load", timeout=25_000)
            await asyncio.sleep(5)

            # Tenta extrair o video_id de várias fontes na página
            video_id = None

            # 1. URL com ?v=
            m = re.search(r"[?&]v=([\w-]{11})", page.url)
            if m:
                video_id = m.group(1)

            # 2. Link canônico com /watch?v=
            if not video_id:
                try:
                    canon = await page.query_selector('link[rel="canonical"]')
                    if canon:
                        href = await canon.get_attribute("href")
                        if href:
                            m = re.search(r"v=([\w-]{11})", href)
                            if m:
                                video_id = m.group(1)
                except Exception:
                    pass

            # 3. Canal com LIVE badge na página (para /@channel/live que não redireciona)
            if not video_id:
                try:
                    # Procura o badge "AO VIVO" ou "LIVE" na página
                    live_badge = await page.query_selector(
                        "ytd-badge-supported-renderer:has(#badges) #live-badge, "
                        ".badge-style-type-live, "
                        "[label='AO VIVO'], [label='LIVE'], "
                        "yt-icon-badge:has-text('AO VIVO'), yt-icon-badge:has-text('LIVE')"
                    )
                    if live_badge:
                        # Tem um badge AO VIVO — extrai video_id do player
                        try:
                            vid = await page.evaluate("""
                                () => {
                                    const el = document.querySelector('ytd-watch-flexy');
                                    if (el) return el.getAttribute('video-id');
                                    // Fallback: procura na ytInitialPlayerResponse
                                    if (window.ytInitialPlayerResponse?.videoDetails?.videoId)
                                        return window.ytInitialPlayerResponse.videoDetails.videoId;
                                    // Procura em qualquer script com ytInitialData
                                    const scripts = document.querySelectorAll('script');
                                    for (const s of scripts) {
                                        const t = s.textContent || '';
                                        const m = t.match(/videoId["']?\\s*[:=]\\s*["']([\\w-]{11})["']/);
                                        if (m) return m[1];
                                    }
                                    return null;
                                }
                            """)
                            if vid and len(vid) == 11 and vid.strip("-"):
                                video_id = vid
                        except Exception:
                            pass
                except Exception:
                    pass

            if video_id:
                return video_id

            log.info(f"💤 Nenhuma live no ar. URL: {page.url}")
            return None
        except Exception as exc:
            log.warning(f"⚠️ Erro ao checar live: {exc}")
            return None
        finally:
            await page.close()

    # ── DETECT OWN CHANNEL ────────────────────
    async def _detect_own_channel(self, page):
        """Detecta o nome do próprio canal no chat (para filtrar auto-mensagens).
        Tenta múltiplas estratégias. Chamado no início e em cada poll até conseguir."""
        if self._own_channel_name:
            return  # já detectou
        try:
            own_name = await page.evaluate("""
                () => {
                    // Estratégia 1: badge "owner" no atributo author-type
                    const ownerItems = document.querySelectorAll(
                        'yt-live-chat-text-message-renderer[author-type="owner"]'
                    );
                    for (const item of ownerItems) {
                        const nameEl = item.querySelector('#author-name');
                        if (nameEl) return nameEl.textContent.trim();
                    }
                    // Estratégia 2: badge com texto "Você" ou "You"
                    const items = document.querySelectorAll('yt-live-chat-text-message-renderer');
                    for (const item of items) {
                        const badge = item.querySelector('#author-badge');
                        if (badge) {
                            const txt = badge.textContent.trim();
                            if (txt.includes('Você') || txt.includes('You')) {
                                const nameEl = item.querySelector('#author-name');
                                if (nameEl) return nameEl.textContent.trim();
                            }
                        }
                    }
                    // Estratégia 3: header do chat
                    const header = document.querySelector('#view-selector #channel-name');
                    if (header) return header.textContent.trim();
                    // Estratégia 4: página do canal (se disponível)
                    const channelLink = document.querySelector(
                        'a[href*="/@"], a[href*="/channel/"]'
                    );
                    if (channelLink) {
                        const text = channelLink.textContent.trim();
                        if (text) return text;
                    }
                    return null;
                }
            """)
            if own_name:
                self._own_channel_name = own_name
                log.info(f"🔍 Nome do canal detectado: {own_name}")
            else:
                log.debug("⌛ Ainda não foi possível detectar nome do canal (tentando de novo no próximo poll)")
        except Exception as e:
            log.debug(f"Detecção de canal: {e}")

    # ── MONITOR CHAT ───────────────────────────
    async def _monitor_chat(self, ctx, video_id: str):
        chat_url = f"https://www.youtube.com/live_chat?is_popout=1&v={video_id}"
        page = await ctx.new_page()
        await page.goto(chat_url, wait_until="domcontentloaded", timeout=20_000)
        await asyncio.sleep(6)

        # Se for live nova (video_id diferente), limpa histórico — mensagens antigas não estão aqui
        if video_id != self._last_video_id:
            self._seen.clear()
            log.info("🆕 Live nova, limpando histórico de mensagens")
        else:
            log.info(f"🔄 Mesma live (caiu/reiniciou), mantendo {len(self._seen)} mensagens no histórico")
        self._last_video_id = video_id
        self._sent.clear()
        self._rule_cooldowns.clear()
        self._last_msg_at = 0.0
        self._minute_count = 0
        self._minute_start = time.time()

        # Detecta o nome do próprio canal (tentativa inicial, re-tentado nos polls)
        await self._detect_own_channel(page)

        log.info("💬 Monitorando chat... (Ctrl+C para parar)")

        try:
            while True:
                final = page.url
                if "live_chat" not in final and "watch" not in final:
                    log.info("📴 Redirecionado — stream encerrou.")
                    break
                await self._poll_messages(page)
                await asyncio.sleep(self.s.get("check_interval", 5))
        except Exception as exc:
            log.warning(f"⚠️ Erro no monitor: {exc}")
        finally:
            self._save_responded()
            await page.close()

    # ── POLL MESSAGES ──────────────────────────
    async def _poll_messages(self, page: Page):
        # Tenta detectar o nome do canal se ainda não conseguiu
        if not self._own_channel_name:
            await self._detect_own_channel(page)

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

                author = (await author_el.inner_text()).strip() if author_el else "?"
                text = (await msg_el.inner_text()).strip()
                if not text:
                    continue

                # Pula se for mensagem do próprio canal (evita loop de auto-resposta)
                if self._own_channel_name and author == self._own_channel_name:
                    log.info(f"⏭️ Auto-mensagem do canal, pulando")
                    continue

                # Pula se já enviei esse texto antes (evita responder a mesma coisa de novo)
                if text in self._sent:
                    log.info(f"⏭️ Já enviei '{text[:40]}...', pulando")
                    continue

                key = f"{author}|{text}"
                if key in self._seen:
                    continue

                # ⏱️ Rate limit: verifica ANTES de marcar como visto
                now = time.time()
                if now - self._last_msg_at < self.s.get("min_response_interval", 20):
                    continue  # não marca como visto — tenta de novo no próximo poll
                if self._minute_count >= self.s.get("max_responses_per_minute", 4):
                    now_m = time.time()
                    if now_m - self._minute_start >= 60:
                        self._minute_count = 0
                        self._minute_start = now_m
                    else:
                        continue  # não marca como visto

                log.info(f"💬 {author}: {text}")

                try:
                    resp = await self._decide_response(author, text)
                    if resp:
                        self._sent.add(text)
                        if len(self._sent) > 500:
                            self._sent = set(list(self._sent)[-250:])
                        await self._send(page, resp)
                finally:
                    self._seen.add(key)
                    if len(self._seen) > 2000:
                        self._seen = set(list(self._seen)[-1000:])

            except Exception:
                continue

    # ── DECIDE RESPONSE ────────────────────────
    async def _decide_response(self, author: str, message: str) -> str | None:
        """
        Decide a resposta baseada no modo configurado:

        Modo "ai":
          - Se passar nos rate limits, chama a IA SEMPRE
          - Fallback pra resposta fixa se IA falhar

        Modo "hybrid":
          - Match de keyword primeiro
          - Se matched: IA gera resposta variada
          - Se IA falhar: usa resposta fixa da rule
          - Se não matched: usa resposta default

        Modo "off":
          - Usa o sistema de regras fixas original
        """
        raw = message.lower().strip()
        if not raw:
            return None

        now = time.time()

        # ── Rate limits (comuns a todos os modos) ──
        if now - self._minute_start >= 60:
            self._minute_count = 0
            self._minute_start = now
        if self._minute_count >= self.s.get("max_responses_per_minute", 8):
            return None
        if now - self._last_msg_at < self.s.get("min_response_interval", 8):
            return None

        resolved_keyword = ""
        matched_idx = -1
        matched_rule = None

        # ── Keyword matching ──
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

        # ── Mode: AI ──
        if self.ai_mode == "ai" and self.ai.enabled:
            # IA decide TUDO: se responder, o quê, e quando
            ai_resp = await self.ai.generate(author, message)
            if ai_resp:
                self._last_msg_at = now
                self._minute_count += 1
                return ai_resp
            # IA retornou None (SKIP ou erro) → não responde, sem fallback
            return None

        # ── Mode: HYBRID ──
        if self.ai_mode == "hybrid":
            if matched_rule:
                # Verifica cooldown da regra
                last = self._rule_cooldowns.get(matched_idx, 0.0)
                cd = matched_rule.get("cooldown", 20)
                if now - last < cd:
                    return None
                self._rule_cooldowns[matched_idx] = now

                # Tenta IA primeiro, fallback pra resposta fixa
                if self.ai.enabled:
                    ai_resp = await self.ai.generate(author, message, resolved_keyword)
                    if ai_resp:
                        self._last_msg_at = now
                        self._minute_count += 1
                        return ai_resp

                # Fallback: resposta fixa da regra
                self._last_msg_at = now
                self._minute_count += 1
                return matched_rule["response"]

            # Sem keyword match → não responde (default desligado em hybrid)
            return None

        # ── Mode: OFF (modo original) ──
        if matched_rule:
            return self._apply_rule_cooldown(matched_idx, matched_rule, now)
        return self._default_response(now)

    def _apply_rule_cooldown(self, idx: int, rule: dict, now: float) -> str | None:
        """Aplica cooldown e retorna resposta fixa de uma regra."""
        last = self._rule_cooldowns.get(idx, 0.0)
        cd = rule.get("cooldown", 20)
        if now - last < cd:
            return None
        self._rule_cooldowns[idx] = now
        self._last_msg_at = now
        self._minute_count += 1
        return rule["response"]

    def _default_response(self, now: float) -> str | None:
        """Resposta padrão (com cooldown)."""
        d = self.default_resp
        if not d.get("enabled", True):
            return None
        last = self._rule_cooldowns.get("__default__", 0.0)
        cd = d.get("cooldown", 10)
        if now - last < cd:
            return None
        self._rule_cooldowns["__default__"] = now
        self._last_msg_at = now
        self._minute_count += 1

        # IA mode: tenta IA pra default também
        if self.ai_mode == "ai" and self.ai.enabled:
            # Já tentamos IA no _decide_response, aqui é fallback final
            pass

        return d["response"]

    # ── SEND ───────────────────────────────────
    async def _send(self, page: Page, text: str):
        log.info(f"🤖 → {text}")

        sel = (
            "[contenteditable]",
            "#input",
            "input#input",
            "#chat-input",
            "yt-live-chat-text-input-field-renderer div#input",
            "yt-live-chat-text-input-field-renderer input",
            "yt-live-chat-message-input-renderer #input",
            "#message-input",
            "div#input",
        )

        # Tenta método visual: principal + iframes
        for target, label in [(page, "principal")] + [(f, f"iframe:{f.url[:50]}") for f in page.frames]:
            for s in sel:
                try:
                    inp = await target.query_selector(s)
                    if inp:
                        log.info(f"🔍 Input encontrado ({label}): {s}")
                        try:
                            # Verifica se o elemento encontrado é interagível
                            tag = await inp.evaluate("el => el.tagName")
                            objtype = await inp.evaluate("el => el.id + ' ' + el.className.slice(0,60)")
                            log.info(f"🔍 {tag} #{objtype}")
                        except Exception:
                            pass

                        try:
                            await inp.focus()
                            await asyncio.sleep(0.3)
                            await inp.fill("")
                            await asyncio.sleep(0.3)
                            await inp.type(text, delay=0.05)
                            await asyncio.sleep(0.5)
                            await target.keyboard.press("Enter")
                            await asyncio.sleep(2)
                            # Verificação: input foi limpo = enviado
                            try:
                                after = await target.evaluate("""
                                    () => {
                                        const ce = document.querySelector('[contenteditable]');
                                        if (!ce) return 'no-ce';
                                        return ce.textContent.length === 0 ? 'vazio' : ce.textContent;
                                    }
                                """)
                                if after == 'vazio':
                                    log.info("✅ Enviado! (input limpo)")
                                else:
                                    log.warning(f"⚠️ Input ainda tem texto: '{after[:50]}'")
                                # Se input não tá vazio, tenta Enter de novo
                                if after and after != 'vazio' and after != 'no-ce':
                                    await target.keyboard.press("Enter")
                                    await asyncio.sleep(1)
                                    after2 = await target.evaluate("() => document.querySelector('[contenteditable]')?.textContent?.length")
                                    if after2 == 0:
                                        log.info("✅ Enviado! (Enter2)")
                            except Exception as ve:
                                log.warning(f"⚠️ Verificação: {ve}")
                            return
                        except Exception as e:
                            log.warning(f"⚠️ Input ({label}) falhou: {e}")
                            break  # só tenta esse frame uma vez
                except Exception:
                    continue

        # Fallback: JS no documento e em cada iframe
        log.info("⚡ Tentando fallback via JavaScript...")
        safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

        for target, label in [(page, "principal")] + [(f, f"iframe:{f.url[:50]}") for f in page.frames]:
            try:
                result = await target.evaluate("""
                    (text) => {
                        function findInput(container) {
                            let el = container.querySelector('#input, div#input, [contenteditable], textarea');
                            if (el) return el;
                            if (container.shadowRoot) {
                                el = container.shadowRoot.querySelector('#input');
                                if (el) return el;
                            }
                            const renderer = container.querySelector('yt-live-chat-text-input-field-renderer');
                            if (renderer && renderer.shadowRoot) {
                                el = renderer.shadowRoot.querySelector('#input');
                                if (el) return el;
                            }
                            const msgInput = container.querySelector('yt-live-chat-message-input-renderer');
                            if (msgInput && msgInput.shadowRoot) {
                                el = msgInput.shadowRoot.querySelector('#input');
                                if (el) return el;
                            }
                            // contenteditable mesmo invisível
                            const allCe = container.querySelectorAll('[contenteditable]');
                            for (const e of allCe) {
                                if (e.offsetParent !== null) return e;
                            }
                            return null;
                        }
                        const inp = findInput(document);
                        if (!inp) return 'NF';
                        inp.focus();
                        if (inp.isContentEditable) {
                            inp.textContent = '';
                            document.execCommand('insertText', false, text);
                            return 'CE';
                        }
                        if (inp.tagName === 'TEXTAREA' || inp.tagName === 'INPUT') {
                            inp.value = text;
                            return inp.tagName;
                        }
                        inp.textContent = text;
                        return 'TXT';
                    }
                """ , safe_text)

                if result and result != 'NF':
                    log.info(f"⚡ JS ({label}): {result}")
                    await asyncio.sleep(0.5)
                    await target.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    log.info("✅ Enviado! (JS + Enter)")
                    return
            except Exception as e:
                log.debug(f"JS ({label}) erro: {str(e)[:100]}")

        log.warning("⚠️ Todos os métodos de envio falharam")


# ── ENTRY POINT ──────────────────────────────
async def main():
    config = load_config()
    bot = YoutubeChatBot(config)
    try:
        await bot.run()
    except KeyboardInterrupt:
        log.info("🛑 Bot parado pelo usuário.")


if __name__ == "__main__":
    asyncio.run(main())
