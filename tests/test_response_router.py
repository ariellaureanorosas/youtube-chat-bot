import time

import pytest
from youtube_chat_bot.response_router import ResponseRouter


class FakeAI:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._last_skipped = False

    async def generate(self, author, message, keyword_match=""):
        return None


BIBLICA_MSG = "Essa e uma otima pergunta! Procure nossa equipe pastoral."
HORARIO_MSG = "Nossos cultos as 19:30, 10:00 e 18:00."

RULES = [
    {
        "keywords": ["amem", "gloria"],
        "response": "Amem! Gloria a Deus!",
        "cooldown": 10,
        "enabled": True,
    },
    {
        "keywords": ["bom dia", "boa noite"],
        "response": "Bem-vindo ao culto!",
        "cooldown": 20,
        "enabled": True,
    },
]

DEFAULT = {"response": "Amem!", "cooldown": 60, "enabled": True}


def make_router(ai=None, rules=None, default=None, **kw):
    return ResponseRouter(
        ai=ai or FakeAI(enabled=True),
        rules=rules if rules is not None else RULES,
        default_resp=default if default is not None else DEFAULT,
        resposta_biblica=kw.get("biblica", BIBLICA_MSG),
        resposta_horario=kw.get("horario", HORARIO_MSG),
    )


@pytest.mark.asyncio
class TestRouterModeOff:
    async def test_matched_rule(self):
        r = make_router()
        resp = await r.decide("Joao", "Amem", mode="off")
        assert resp == "Amem! Gloria a Deus!"

    async def test_no_match_uses_default(self):
        r = make_router()
        resp = await r.decide("Jose", "Qual o horario?", mode="off")
        assert resp == "Amem!"

    async def test_empty_message_none(self):
        r = make_router()
        assert await r.decide("Joao", "", mode="off") is None


@pytest.mark.asyncio
class TestRouterModeAi:
    async def test_ai_disabled_returns_none(self):
        r = make_router(ai=FakeAI(enabled=False))
        resp = await r.decide("Joao", "Amem", mode="ai")
        assert resp is None

    async def test_bible_question_institutional(self):
        r = make_router()
        resp = await r.decide("Joao", "qual versiculo fala sobre perdao?", mode="ai")
        assert resp == BIBLICA_MSG

    async def test_horario_question_official(self):
        r = make_router()
        resp = await r.decide("Bia", "que horas comeca o culto?", mode="ai")
        assert resp == HORARIO_MSG

    async def test_discard_before_ai(self):
        calls = []

        class SpyAI(FakeAI):
            async def generate(self, author, message, keyword_match=""):
                calls.append(message)
                return None

        r = make_router(ai=SpyAI())
        assert await r.decide("Joao", "kkkkkk", mode="ai") is None
        assert calls == []


class TestRouterIntentions:
    def test_should_discard_empty(self):
        assert ResponseRouter.should_discard("") is True

    def test_should_discard_risada(self):
        assert ResponseRouter.should_discard("kkkkkkk") is True

    def test_should_discard_pontuacao(self):
        assert ResponseRouter.should_discard("!!!") is True

    def test_should_not_discard_normal(self):
        assert ResponseRouter.should_discard("gloria a deus") is False

    def test_is_bible(self):
        r = make_router()
        assert r.is_bible_question("qual salmo ler?") is True
        assert r.is_bible_question("boa noite") is False

    def test_is_horario(self):
        r = make_router()
        assert r.is_horario_question("qual o horario?") is True
        assert r.is_horario_question("gloria a deus") is False


class TestRouterCooldown:
    def test_different_modes_share_cooldown_state(self):
        r = make_router()
        resp1 = r._apply_rule(0, RULES[0])
        assert resp1 is not None
        resp2 = r._apply_rule(0, RULES[0])
        assert resp2 is None
