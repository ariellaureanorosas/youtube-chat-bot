#!/usr/bin/env python3
import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import aiohttp

ENV_VAR_NAMES = ["NVIDIA_API_KEY", "OPENCODE_ZEN_API_KEY"]
ENV_FILE_SEARCH = "API_KEY="

log = logging.getLogger("youtube_chat_bot.ai")


class AIResponder:
    def __init__(self, ai_config: dict) -> None:
        self.enabled: bool = ai_config.get("enabled", True)
        self.model: str = ai_config.get("model", "deepseek-v4-flash-free")
        self.temperature: float = ai_config.get("temperature", 0.9)
        self.max_tokens: int = ai_config.get("max_tokens", 1000)
        self.system_prompt: str = ai_config.get("system_prompt", "")

        horarios = ai_config.get("culto_horarios") or []
        self.culto_horarios: list[str] = [str(h) for h in horarios if str(h).strip()]

        self.api_key: str | None = self._load_api_key(
            ai_config.get("api_key") or ""
        )
        self.api_url: str = ai_config.get(
            "api_url",
            "https://integrate.api.nvidia.com/v1/chat/completions",
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
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                pass

    def _load_api_key(self, config_key: str = "") -> str | None:
        config_key = config_key.strip().strip('"').strip("'")
        if config_key:
            return config_key

        for env_var in ENV_VAR_NAMES:
            key = os.environ.get(env_var)
            if key and key.strip():
                return key.strip()

        env_paths = [
            Path.home() / "AppData/Local/hermes/.env",
            Path.home() / ".config/hermes/.env",
            Path.home() / ".hermes/.env",
            Path(__file__).parent.parent.parent / ".env",
        ]

        for env_path in env_paths:
            try:
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        name, _, value = line.partition("=")
                        if name.strip() not in ENV_VAR_NAMES:
                            continue
                        raw = value.strip().strip('"').strip("'")
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
        # Usa o prompt COMPLETO (system + contexto) como primeira opcao e
        # repete com backoff crescente para tolerar 503/limitacao do provedor.
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
        # Tenta o prompt completo ate 3x, depois cai para o prompt generico.
        backoff = [2, 5, 12]

        async with self._semaphore:
            for attempt in range(3):
                messages = prompts[0]
                temperature = self.temperature
                if attempt > 0:
                    await asyncio.sleep(backoff[attempt - 1])
                resp = await self._post(messages, temperature)
                if resp is not None:
                    return resp
                log.warning(
                    f"IA nao respondeu no prompt completo, "
                    f"tentativa {attempt + 1}"
                )

            # Ultimo recurso: prompt generico sem system prompt.
            await asyncio.sleep(2)
            return await self._post(prompts[1], 0.5)

    async def _post(
        self, messages: list, temperature: float
    ) -> str | None:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            session = await self._get_session()
            async with session.post(
                self.api_url,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status in (429,) or resp.status >= 500:
                    log.warning(f"HTTP {resp.status} do provedor de IA")
                    return None
                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                content = self._clean_response(content)
                return content if content else None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning(f"Falha no provedor de IA: {e}")
            return None

    @staticmethod
    def _clean_response(content: str) -> str:
        if not content:
            return content
        # O poolside/laguna costuma despejar VARIAS versoes de resposta
        # empilhadas, separadas por linhas em branco, com cabecalhos entre
        # colchetes e prefixos como "response". Trocamos o conteudo por
        # blocos e escolhemos o bloco de resposta mais rico.
        blocks = re.split(
            r"\n\s*\n+|\s+response(?=\S)",
            content.strip(),
        )
        cleaned_blocks = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # Remove prefixo "response" grudado no inicio (ex: "responseBom dia").
            block = re.sub(r"^response(?=\S)", "", block, flags=re.IGNORECASE)
            # Descarta/remove anotacoes entre colchetes no inicio
            # (ex: "[Bom dia! Nos da TV IEBT ]", "[RESPOSTA DADA]").
            block = re.sub(r"^\[[^\]]*\]\s*", "", block).strip()
            if not block:
                continue
            cleaned_blocks.append(block)
        if not cleaned_blocks:
            return ""
        # Prefere o bloco mais longo (resposta mais completa/coesa).
        best = max(cleaned_blocks, key=lambda b: len(b))
        # Limpeza final contra duplicacoes residuais do tipo
        # "resposta.\n responseMesma resposta" que escapam do split.
        best = re.split(r"\s+response(?=\S)", best)[0]
        return best.strip().strip('"').strip("'").strip()

    def _build_prompt(
        self, author: str, message: str, keyword_match: str
    ) -> str:
        now = datetime.now()
        hora = now.hour
        if 5 <= hora < 12:
            periodo = "manha"
        elif 12 <= hora < 18:
            periodo = "tarde"
        else:
            periodo = "noite"
        time_info = (
            f"[HORARIO ATUAL DO SISTEMA: {now.strftime('%H:%M')} — "
            f"periodo: {periodo}]"
        )
        culto_info = ""
        if self.culto_horarios:
            culto_info = (
                "\nHORÁRIOS OFICIAIS DOS CULTOS DA TV IEBT: "
                + "; ".join(self.culto_horarios)
                + ".\n"
                "NUNCA informe um horário que não esteja nesta lista. "
                "Se o dia tiver mais de um culto, cite todos. "
                "Se nao der para saber o dia, liste todos oficialmente."
            )

        prompt_sufixo = (
            "Responda em 1 pessoa do plural (nos da TV IEBT), "
            "de forma natural, acolhedora e variada. "
            f"Mencione o nome '{author}' na resposta se for uma "
            "mensagem individual. "
            "Se for uma saudacao geral para o chat, "
            "nao precisa citar nome. "
            "Se NAO for apropriado responder, retorne apenas: SKIP"
        )

        if keyword_match:
            return (
                f'{time_info}{culto_info}\n'
                f'O irmao(a) {author} acabou de comentar no chat ao vivo: '
                f'"{message}"\n\n'
                f"(Contexto: a mensagem e sobre '{keyword_match}')\n\n"
                f"{prompt_sufixo}"
            )
        return (
            f'{time_info}{culto_info}\n'
            f'O irmao(a) {author} escreveu no chat: "{message}"\n\n'
            f"{prompt_sufixo}"
        )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()