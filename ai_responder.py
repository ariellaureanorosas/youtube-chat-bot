#!/usr/bin/env python3
"""
AI Responder — Gera respostas autênticas via Deepseek (OpenCode Zen API)
=========================================================================
Usa o mesmo modelo gratuito (deepseek-v4-flash-free) que roda o Hermes.
Lê a chave de API do .env do Hermes automaticamente.
"""

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

    def __init__(self, ai_config: dict):
        self.enabled = ai_config.get("enabled", True)
        self.mode = ai_config.get("mode", "hybrid")  # ai | hybrid | off
        self.model = ai_config.get("model", "deepseek-v4-flash-free")
        self.temperature = ai_config.get("temperature", 0.9)
        self.max_tokens = ai_config.get("max_tokens", 1000)
        self.system_prompt = ai_config.get("system_prompt", "")

        self.api_key = self._load_api_key()
        self.api_url = ai_config.get(
            "api_url", "https://opencode.ai/zen/v1/chat/completions"
        )

        # Cache pra não repetir respostas idênticas
        self._cache: dict[str, tuple[str, float]] = {}  # msg_hash -> (response, timestamp)

        if not self.api_key:
            log.warning("⚠️  OPENCODE_ZEN_API_KEY não encontrada! IA desativada.")
            self.enabled = False

    # ── LOAD API KEY ──────────────────────────
    def _load_api_key(self) -> str | None:
        # 1. Tenta variável de ambiente
        key = os.environ.get(PREFIX + SUFFIX[:-1])
        if key:
            return key

        # 2. Tenta o .env do Hermes
        try:
            env_path = Path.home() / "AppData/Local/hermes/.env"
            if env_path.exists():
                search = PREFIX + SUFFIX
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith(search):
                        raw = line.split("=", 1)[1].strip()
                        raw = raw.strip('"').strip("'")
                        if raw:
                            return raw
        except Exception:
            pass

        return None

    # ── GENERATE ──────────────────────────────
    async def generate(self, author: str, message: str, keyword_match: str = "") -> str | None:
        """Gera uma resposta via IA. Retorna None em caso de erro ou se a IA decidir não responder (SKIP)."""
        if not self.enabled:
            return None

        # Cache simples: mesma mensagem + keyword = reusa por 30s
        cache_key = f"{message}|{keyword_match}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and (now - cached[1]) < 30:
            return cached[0]

        try:
            response = await self._call_api(author, message, keyword_match)
            if response:
                # Se a IA decidiu não responder, retorna None (sem cache)
                if response.strip().upper() == "SKIP":
                    return None
                # Atualiza cache (máx 100 itens)
                self._cache[cache_key] = (response, now)
                if len(self._cache) > 100:
                    # Limpa cache velho
                    cutoff = now - 60
                    self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}
                return response
        except Exception as e:
            log.warning(f"⚠️  Erro na IA: {e}")

        return None

    # ── API CALL ──────────────────────────────
    async def _call_api(self, author: str, message: str, keyword_match: str) -> str | None:
        """Chama a API do OpenCode Zen (compatível com OpenAI). Tenta 2x se falhar."""
        prompts = [
            # Tentativa 1: com system prompt completo
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self._build_prompt(author, message, keyword_match)},
            ],
            # Tentativa 2: mais curto, sem system prompt
            [
                {"role": "user", "content": f"Responda em 1 linha e de forma natural para '{author}' que disse: {message}"}
            ],
        ]

        for attempt, messages in enumerate(prompts):
            if attempt > 0:
                await asyncio.sleep(1)  # pausa curta entre tentativas

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
                log.debug(f"Tentativa {attempt+1} retornou vazio, tentando novamente...")
            except Exception as e:
                log.warning(f"Tentativa {attempt+1} falhou: {e}")

        return None

    def _do_request(self, req: urllib.request.Request) -> str | None:
        """Executa a requisição HTTP (síncrona, roda em thread)."""
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                content = content.strip('"').strip("'")
                return content if content else None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.warning(f"HTTP {e.code}: {body[:200]}")
            return None
        except Exception as e:
            log.warning(f"Request error: {type(e).__name__}: {e}")
            return None

    # ── BUILD PROMPT ──────────────────────────
    def _build_prompt(self, author: str, message: str, keyword_match: str) -> str:
        """Monta o prompt do usuário com a mensagem do chat."""
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


# Import asyncio aqui (evita circular import)
import asyncio
