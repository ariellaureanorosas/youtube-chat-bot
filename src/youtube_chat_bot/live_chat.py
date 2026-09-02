#!/usr/bin/env python3
"""
LiveChatClient — Camada de navegação/interação com o YouTube (Playwright).
==========================================================================
Encapsula todo o I/O com o navegador: navegar até a live, abrir o chat
pop-out, detectar o próprio canal, extrair mensagens brutas do DOM e
enviar respostas. Não contém lógica de negócio (decisão, rate-limit,
persistência) — isso fica a cargo do orquestrador (YoutubeChatBot).
"""

import asyncio
import logging
import re
from typing import Any

__all__ = ["LiveChatClient"]

from playwright.async_api import Page

log = logging.getLogger("youtube_chat_bot")


class LiveChatClient:
    """Encapsula a navegação e as operações de DOM no chat ao vivo."""

    MESSAGE_SELECTOR = "yt-live-chat-text-message-renderer"

    def __init__(self, channel: str) -> None:
        self.channel = channel.lstrip("@")

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    async def find_live(self, page: Page) -> str | None:
        """Navega até a página /live do canal e tenta extrair o video_id."""
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

    async def open_live_chat(self, page: Page, video_id: str) -> None:
        """Navega até o chat pop-out da live e aguarda os elementos surgirem."""
        chat_url = (
            f"https://www.youtube.com/live_chat"
            f"?is_popout=1&v={video_id}"
        )
        await page.goto(
            chat_url, wait_until="domcontentloaded", timeout=20_000
        )

        try:
            await page.wait_for_selector(
                self.MESSAGE_SELECTOR, timeout=15_000
            )
        except Exception:
            log.warning("Chat nao renderizou a tempo, continuando...")

    # ------------------------------------------------------------------
    # Leitura de mensagens
    # ------------------------------------------------------------------

    async def detect_own_channel(self, page: Page) -> str | None:
        """Descobre o nome do canal do próprio dono (para não responder a si)."""
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
                log.info(f"Nome do canal detectado: {own_name}")
            return own_name
        except Exception as e:
            log.debug(f"Detecao de canal: {e}")
            return None

    async def fetch_messages(self, page: Page) -> list[tuple[str, str]]:
        """Extrai pares (autor, texto) dos elementos de mensagem no DOM."""
        try:
            els = await page.query_selector_all(self.MESSAGE_SELECTOR)
        except Exception:
            return []

        mensagens: list[tuple[str, str]] = []
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
                mensagens.append((author, text))
            except Exception:
                continue
        return mensagens

    # ------------------------------------------------------------------
    # Envio de resposta
    # ------------------------------------------------------------------

    async def send(self, page: Page, text: str) -> None:
        """Digita e envia uma resposta no chat, com fallbacks visual/JS."""
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