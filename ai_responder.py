#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import aiohttp

PREFIX = "OPENCODE_ZEN_API"
SUFFIX = "_KEY="

log = logging.getLogger("youtube_chat_bot.ai")


class AIResponder:
    def __init__(self, ai_config: dict) -> None:
        self.enabled: bool = ai_config.get("enabled", True)
        self.model: str = ai_config.get("model", "deepseek-v4-flash-free")
        self.temperature: float = ai_config.get("temperature", 0.9)
        self.max_tokens: int = ai_config.get("max_tokens", 1000)
        self.system_prompt: str = ai_config.get("system_prompt", "")

        self.api_key: str | None = self._load_api_key()
        self.api_url: str = ai_config.get(
            "api_url", "https://opencode.ai/zen/v1/chat/completions"
        )

        self._cache: dict[str, tuple[str, float]] = {}
        self._cache_access_count: int = 0
        self._pending_locks: dict[str, asyncio.Lock] = {}
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(5)
        self._last_skipped: bool = False

        if not self.api_key:
            log.warning("OPENCODE_ZEN_API_KEY nao encontrada! IA desativada.")
            self.enabled = False

    def __del__(self) -> None:
        if self._session is not None and not self._session.closed:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                pass

    def _load_api_key(self) -> str | None:
        env_var = PREFIX + SUFFIX[:-1]
        key = os.environ.get(env_var)
        if key:
            return key

        env_paths = [
            Path.home() / "AppData/Local/hermes/.env",
            Path.home() / ".config/hermes/.env",
            Path.home() / ".hermes/.env",
            Path(__file__).parent / ".env",
        ]

        search = PREFIX + SUFFIX
        for env_path in env_paths:
            try:
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line.startswith(search):
                            raw = line.split("=", 1)[1].strip()
                            raw = raw.strip('"').strip("'")
                            if raw:
                                return raw
            except Exception:
                continue

        return None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                }
            )
        return self._session

    async def generate(
        self, author: str, message: str, keyword_match: str = ""
    ) -> str | None:
        if not self.enabled:
            return None

        cache_key = f"{message}\x00{keyword_match}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and (now - cached[1]) < 30:
            return cached[0]

        if cache_key not in self._pending_locks:
            self._pending_locks[cache_key] = asyncio.Lock()

        async with self._pending_locks[cache_key]:
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[1]) < 30:
                return cached[0]

            try:
                response = await self._call_api(author, message, keyword_match)
                if response:
                    if self._is_skip(response):
                        self._last_skipped = True
                        return None
                    self._last_skipped = False
                    self._cache[cache_key] = (response, now)
                    self._cache_access_count += 1
                    if self._cache_access_count >= 50:
                        self._cleanup_cache()
                    return response
                self._last_skipped = False
            except Exception as e:
                self._last_skipped = False
                log.warning(f"Erro na IA: {e}")
            finally:
                self._pending_locks.pop(cache_key, None)

        return None

    @staticmethod
    def _is_skip(response: str) -> bool:
        return bool(re.search(r"\bSKIP\b", response.strip().upper()))

    def _cleanup_cache(self) -> None:
        cutoff = time.time() - 120
        self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}
        self._cache_access_count = 0
        if len(self._cache) > 100:
            sorted_items = sorted(
                self._cache.items(), key=lambda x: x[1][1], reverse=True
            )
            self._cache = dict(sorted_items[:100])

    async def _call_api(
        self, author: str, message: str, keyword_match: str
    ) -> str | None:
        prompts = [
            [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": self._build_prompt(author, message, keyword_match),
                },
            ],
            [
                {
                    "role": "user",
                    "content": (
                        f"Responda em 1 linha e de forma natural para "
                        f"'{author}' que disse: {message}"
                    ),
                }
            ],
        ]

        async with self._semaphore:
            for attempt, messages in enumerate(prompts):
                if attempt > 0:
                    await asyncio.sleep(2**attempt)

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature if attempt == 0 else 0.5,
                    "max_tokens": self.max_tokens,
                }

                try:
                    session = await self._get_session()
                    async with session.post(
                        self.api_url,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status in (429,) or resp.status >= 500:
                            log.warning(
                                f"HTTP {resp.status}, tentativa {attempt + 1}"
                            )
                            if attempt < len(prompts) - 1:
                                continue
                            return None

                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        content = content.strip('"').strip("'")
                        return content if content else None

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    log.warning(f"Tentativa {attempt + 1} falhou: {e}")

        return None

    def _build_prompt(
        self, author: str, message: str, keyword_match: str
    ) -> str:
        if keyword_match:
            return (
                f'O irmao(a) {author} acabou de comentar no chat ao vivo: '
                f'"{message}"\n\n'
                f"(Contexto: a mensagem e sobre '{keyword_match}')\n\n"
                f"Responda em 1 pessoa do plural (nos da TV IEBT), "
                f"de forma natural, acolhedora e variada. "
                f"Mencione o nome '{author}' na resposta se for uma "
                f"mensagem individual. "
                f"Se for uma saudacao geral para o chat, "
                f"nao precisa citar nome. "
                f"Se NAO for apropriado responder, retorne apenas: SKIP"
            )
        return (
            f'O irmao(a) {author} escreveu no chat: "{message}"\n\n'
            f"Responda em 1 pessoa do plural (nos da TV IEBT), "
            f"de forma natural e acolhedora. "
            f"Mencione o nome '{author}' na resposta se for uma "
            f"mensagem individual. "
            f"Se for uma saudacao geral para o chat, "
            f"nao precisa citar nome. "
            f"Se NAO for apropriado responder, retorne apenas: SKIP"
        )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
