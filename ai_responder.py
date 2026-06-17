#!/usr/bin/env python3
"""
AI Responder — Gera respostas autênticas via Deepseek (OpenCode Zen API)
=========================================================================
Usa o mesmo modelo gratuito (deepseek-v4-flash-free) que roda o Hermes.
Lê a chave de API do .env do Hermes automaticamente.
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

PREFIX = "OPENCODE_ZEN_API"
SUFFIX = "_KEY="

log = logging.getLogger("youtube_chat_bot.ai")


class AIResponder:
    """Gera respostas contextualmente autênticas para o chat usando IA."""

    def __init__(self, ai_config: dict) -> None:
        self.enabled: bool = ai_config.get("enabled", True)
        self.mode: str = ai_config.get("mode", "hybrid")
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

        if not self.api_key:
            log.warning("⚠️  OPENCODE_ZEN_API_KEY não encontrada! IA desativada.")
            self.enabled = False

    # ── LOAD API KEY ──────────────────────────
    def _load_api_key(self) -> str | None:
        env_var = PREFIX + SUFFIX[:-1]
        key = os.environ.get(env_var)
        if key:
            return key

        hermes_envs = [
            Path.home() / "AppData/Local/hermes/.env",
            Path.home() / ".config/hermes/.env",
            Path.home() / ".hermes/.env",
        ]

        search = PREFIX + SUFFIX
        for env_path in hermes_envs:
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

    # ── GENERATE ──────────────────────────────
    async def generate(self, author: str, message: str, keyword_match: str = "") -> str | None:
        if not self.enabled:
            return None

        cache_key = f"{message}|{keyword_match}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and (now - cached[1]) < 30:
            return cached[0]

        try:
            response = await self._call_api(author, message, keyword_match)
            if response:
                if response.strip().upper() == "SKIP":
                    return None
                self._cache[cache_key] = (response, now)
                self._cache_access_count += 1
                if self._cache_access_count >= 50:
                    self._cleanup_cache()
                return response
        except Exception as e:
            log.warning(f"⚠️  Erro na IA: {e}")

        return None

    def _cleanup_cache(self) -> None:
        cutoff = time.time() - 120
        self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}
        self._cache_access_count = 0
        if len(self._cache) > 100:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1], reverse=True)
            self._cache = dict(sorted_items[:100])

    # ── API CALL ──────────────────────────────
    async def _call_api(self, author: str, message: str, keyword_match: str) -> str | None:
        prompts = [
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self._build_prompt(author, message, keyword_match)},
            ],
            [
                {"role": "user", "content": f"Responda em 1 linha e de forma natural para '{author}' que disse: {message}"}
            ],
        ]

        for attempt, messages in enumerate(prompts):
            if attempt > 0:
                await asyncio.sleep(2 ** attempt)

            payload = json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature if attempt == 0 else 0.5,
                "max_tokens": self.max_tokens,
            }).encode("utf-8")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }

            req = urllib.request.Request(
                self.api_url,
                data=payload,
                headers=headers,
                method="POST",
            )

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._do_request, req
                )
                if result:
                    return result
            except Exception as e:
                log.warning(f"Tentativa {attempt+1} falhou: {e}")

        return None

    def _do_request(self, req: urllib.request.Request) -> str | None:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                content = content.strip('"').strip("'")
                return content if content else None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.warning(f"HTTP {e.code}: {body[:200]}")
            if e.code in (429, 502, 503, 504):
                raise  # for retry in _call_api
            return None
        except Exception as e:
            log.warning(f"Request error: {type(e).__name__}: {e}")
            return None

    # ── BUILD PROMPT ──────────────────────────
    def _build_prompt(self, author: str, message: str, keyword_match: str) -> str:
        if keyword_match:
            return (
                f"O irmão(a) {author} acabou de comentar no chat ao vivo: \"{message}\"\n\n"
                f"(Contexto: a mensagem é sobre '{keyword_match}')\n\n"
                f"Responda em 1ª pessoa do plural (nós da TV IEBT), "
                f"de forma natural, acolhedora e variada. "
                f"Mencione o nome '{author}' na resposta se for uma mensagem individual. "
                f"Se for uma saudação geral para o chat, não precisa citar nome. "
                f"Se NÃO for apropriado responder, retorne apenas: SKIP"
            )
        return (
            f"O irmão(a) {author} escreveu no chat: \"{message}\"\n\n"
            f"Responda em 1ª pessoa do plural (nós da TV IEBT), "
            f"de forma natural e acolhedora. "
            f"Mencione o nome '{author}' na resposta se for uma mensagem individual. "
            f"Se for uma saudação geral para o chat, não precisa citar nome. "
            f"Se NÃO for apropriado responder, retorne apenas: SKIP"
        )


