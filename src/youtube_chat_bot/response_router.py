#!/usr/bin/env python3
"""
Decisão de resposta — Decide o que o bot deve responder a cada mensagem.
==========================================================================
Centraliza toda a lógica de "o que responder": descarte de mensagens de baixo
valor, detecção de intenções (perguntas de horário / conteúdo bíblico) e o
roteamento pelos modos ai/hybrid/off. Fica desacoplado do Playwright e da
persistência, sendo testável de forma isolada.
"""

import logging
import re
import time

from youtube_chat_bot.ai_responder import AIResponder

log = logging.getLogger("youtube_chat_bot")


class ResponseRouter:
    """Roteia cada mensagem para a resposta adequada (ou nenhuma)."""

    BIBLE_KEYWORDS = (
        "versiculo", "versículo", "biblia", "bíblia", "salmo", "escritura",
        "proverbio", "provérbio", "genesis", "gênesis", "exodo", "êxodo",
        "evangelho", "apostolo", "apóstolo", "epistola", "epístola",
        "capitulo", "capítulo", "livro de",
        "o que a biblia", "o que deus", "jesus", "cristo", "deus diz",
        "qual versiculo", "que versiculo", "onde esta escrito",
        "estudar a biblia", "estudo biblico", "estudo bíblico",
        "interpretar", "significado de", "doutrina", "teologia",
    )

    HORARIO_KEYWORDS = (
        "que horas", "a que horas", "horario do culto", "horario dos cultos",
        "hora do culto", "que dia tem culto", "dias de culto",
        "quando comeca o culto", "que hora comeca", "qual o horario",
        "qual o dia", "quando tem culto", "que dias", "horario",
    )

    def __init__(
        self,
        ai: AIResponder,
        rules: list[dict],
        default_resp: dict,
        resposta_biblica: str,
        resposta_horario: str,
    ) -> None:
        self.ai = ai
        self.rules = rules
        self.default_resp = default_resp
        self.resposta_biblica = resposta_biblica
        self.resposta_horario = resposta_horario
        self._rule_cooldowns: dict[str | int, float] = {}

    # ------------------------------------------------------------------
    # Intenções / descarte
    # ------------------------------------------------------------------

    @staticmethod
    def should_discard(raw: str) -> bool:
        if not raw:
            return True
        text = raw.strip()
        # So pontuacao/emoji/espacos (ex: "!!!", "...", "🙏🙏") -> nao responde.
        if re.fullmatch(r"[\s!?.,~^*\-_=+<>()\[\]{}'\"`\\/|@#$%&;:]*", text):
            return True
        # Apenas risadas repetitivas (kkkk, kkkkkk, hahaha, rsrs, hehe).
        if re.fullmatch(
            r"(?:k+|h+[aeiou]+|r+s+|rs+|kk+|ehehe|hahaha|(?:rs)+)[\s!?.,]*",
            text,
        ):
            return True
        # So emojis/teclas repetidas (ex: "😂😂😂", "asdfasdfasdf").
        if re.fullmatch(r"(.)\1{2,}", text):
            return True
        return False

    def is_bible_question(self, raw: str) -> bool:
        for kw in self.BIBLE_KEYWORDS:
            if kw in raw:
                return True
        return False

    def is_horario_question(self, raw: str) -> bool:
        for kw in self.HORARIO_KEYWORDS:
            if kw in raw:
                return True
        return False

    # ------------------------------------------------------------------
    # Roteamento
    # ------------------------------------------------------------------

    async def decide(
        self, author: str, message: str, mode: str
    ) -> str | None:
        raw = message.lower().strip()
        if not raw:
            return None

        if self.should_discard(raw):
            log.debug(
                f"Descarte: mensagem de baixo valor: {author}: {message[:60]}"
            )
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

        if mode == "ai":
            if not self.ai.enabled:
                log.warning(
                    "Modo 'ai' sem IA ativa (chave de API ausente) — "
                    "modo 'ai' nao usa regras fixas, nada sera postado"
                )
                return None

            if self.is_horario_question(raw):
                log.info(
                    f"Pergunta de horário identificada — resposta oficial: "
                    f"{author}: {message[:60]}"
                )
                return self.resposta_horario

            if self.is_bible_question(raw):
                log.info(
                    f"Pergunta bíblica identificada — resposta institucional: "
                    f"{author}: {message[:60]}"
                )
                return self.resposta_biblica

            ai_resp = await self.ai.generate(author, message)
            if ai_resp:
                return ai_resp
            if self.ai._last_skipped:
                log.debug(
                    f"IA pulou intencionalmente (SKIP): "
                    f"{author}: {message[:60]}"
                )
            else:
                log.warning(
                    f"IA nao respondeu (sem fallback no modo 'ai'): "
                    f"{author}: {message[:60]}"
                )
            return None

        if mode == "hybrid":
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

    # ------------------------------------------------------------------
    # Regras fixas (modo off / fallback)
    # ------------------------------------------------------------------

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
