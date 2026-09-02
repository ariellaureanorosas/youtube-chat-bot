import copy

import pytest
from youtube_chat_bot.bot import YoutubeChatBot


BASE_CONFIG = {
    "channel": {"name": "tviebt"},
    "ai": {
        "enabled": True,
        "mode": "off",
        "model": "deepseek-v4-flash-free",
        "temperature": 0.7,
        "max_tokens": 100,
        "system_prompt": "",
        "fallback_to_rules": True,
        "culto_horarios": [
            "Quarta-feira - 19:30",
            "Domingo (manha) - 10:00",
            "Domingo (noite) - 18:00",
        ],
        "resposta_pergunta_biblica": (
            "Essa e uma otima pergunta! Procure nossa equipe pastoral na igreja."
        ),
    },
    "response_rules": [
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
    ],
    "default_response": {
        "response": "Amem!",
        "cooldown": 60,
        "enabled": True,
    },
    "settings": {
        "check_interval": 5,
        "min_response_interval": 10,
        "max_responses_per_minute": 4,
        "headless": True,
        "language": "pt",
        "log_level": "INFO",
        "save_interval": 300,
    },
}


def make_bot(**overrides):
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg.update(overrides)
    return YoutubeChatBot(cfg)


@pytest.mark.asyncio
class TestDecideResponseOffMode:
    async def test_matched_rule_returns_response(self):
        bot = make_bot()
        resp = await bot._decide_response("Joao", "Amem")
        assert resp == "Amem! Gloria a Deus!"

    async def test_matched_rule_different_keyword(self):
        bot = make_bot()
        resp = await bot._decide_response("Maria", "Bom dia")
        assert resp == "Bem-vindo ao culto!"

    async def test_no_match_returns_default(self):
        bot = make_bot()
        resp = await bot._decide_response("Jose", "Qual o horario?")
        assert resp == "Amem!"

    async def test_empty_message_returns_none(self):
        bot = make_bot()
        resp = await bot._decide_response("Joao", "")
        assert resp is None

    async def test_default_disabled_returns_none(self):
        bot = make_bot()
        bot.default_resp["enabled"] = False
        resp = await bot._decide_response("Jose", "Qual o horario?")
        assert resp is None


class TestCooldown:
    def test_cooldown_blocks_repeat(self):
        bot = make_bot()
        resp1 = bot._apply_rule(0, BASE_CONFIG["response_rules"][0])
        assert resp1 is not None
        resp2 = bot._apply_rule(0, BASE_CONFIG["response_rules"][0])
        assert resp2 is None

    def test_cooldown_expires(self):
        import time
        bot = make_bot()
        rule = dict(BASE_CONFIG["response_rules"][0])
        rule["cooldown"] = 0.001
        resp1 = bot._apply_rule(0, rule)
        assert resp1 is not None
        time.sleep(0.002)
        resp2 = bot._apply_rule(0, rule)
        assert resp2 is not None

    def test_different_rules_independent(self):
        bot = make_bot()
        resp1 = bot._apply_rule(0, BASE_CONFIG["response_rules"][0])
        assert resp1 is not None
        resp2 = bot._apply_rule(1, BASE_CONFIG["response_rules"][1])
        assert resp2 is not None


@pytest.mark.asyncio
class TestDecideResponseAiMode:
    async def test_ai_disabled_returns_none_no_fallback(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = False
        resp = await bot._decide_response("Joao", "Amem")
        assert resp is None

    async def test_ai_disabled_no_keyword_returns_none(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = False
        resp = await bot._decide_response("Joao", "coisa aleatoria")
        assert resp is None

    async def test_ai_returns_none_no_keyword_and_no_fallback(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        resp = await bot._decide_response("Maria", "coisa aleatoria")
        assert resp is None


class TestDefaultResponse:
    def test_default_enabled(self):
        bot = make_bot()
        resp = bot._default_response()
        assert resp == "Amem!"

    def test_default_disabled(self):
        bot = make_bot()
        bot.default_resp["enabled"] = False
        resp = bot._default_response()
        assert resp is None


class TestShouldDiscard:
    def test_empty(self):
        assert YoutubeChatBot._should_discard("") is True

    def test_risada_kkk(self):
        assert YoutubeChatBot._should_discard("kkkkkkkkkkk") is True

    def test_risada_haha(self):
        assert YoutubeChatBot._should_discard("hahaha") is True

    def test_risada_rs(self):
        assert YoutubeChatBot._should_discard("rsrsrs") is True

    def test_apenas_pontuacao(self):
        assert YoutubeChatBot._should_discard("!!!") is True

    def test_apenas_emoji_repetido(self):
        assert YoutubeChatBot._should_discard("😂😂😂") is True

    def test_mensagem_normal(self):
        assert YoutubeChatBot._should_discard("gloria a deus") is False

    def test_pergunta_normal(self):
        assert YoutubeChatBot._should_discard("qual o horario?") is False


class TestIsBibleQuestion:
    def test_pergunta_versiculo(self):
        bot = make_bot()
        assert bot._is_bible_question("qual versiculo fala sobre amor?") is True

    def test_pergunta_salmo(self):
        bot = make_bot()
        assert bot._is_bible_question("me indique um salmo de esperanca") is True

    def test_pergunta_jesus(self):
        bot = make_bot()
        assert bot._is_bible_question("o que jesus disse sobre orar?") is True

    def test_pergunta_onde_esta_escrito(self):
        bot = make_bot()
        assert bot._is_bible_question("onde esta escrito que deus e amor?") is True

    def test_mencao_deus_sem_pergunta_biblica(self):
        bot = make_bot()
        assert bot._is_bible_question("gloria a deus") is False

    def test_horario_nao_confunde(self):
        bot = make_bot()
        assert bot._is_bible_question("qual o horario do culto?") is False

    def test_saudacao_nao_confunde(self):
        bot = make_bot()
        assert bot._is_bible_question("boa noite, como voces estao?") is False


@pytest.mark.asyncio
class TestBibleQuestionResponse:
    async def test_bible_question_returns_institutional_response(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        resp = await bot._decide_response(
            "Joao", "qual versiculo fala sobre perdao?"
        )
        assert resp == bot.resposta_biblica

    async def test_custom_bible_response(self):
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["ai"]["resposta_pergunta_biblica"] = "Texto personalizado"
        bot = YoutubeChatBot(cfg)
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        resp = await bot._decide_response("Joao", "qual salmo ler hoje?")
        assert resp == "Texto personalizado"


class TestIsHorarioQuestion:
    def test_pergunta_horario(self):
        bot = make_bot()
        assert bot._is_horario_question("qual o horario do culto?") is True

    def test_pergunta_que_horas(self):
        bot = make_bot()
        assert bot._is_horario_question("que horas comeca o culto?") is True

    def test_pergunta_que_dia_tem_culto(self):
        bot = make_bot()
        assert bot._is_horario_question("que dia tem culto na semana?") is True

    def test_horario_palavra_sola(self):
        bot = make_bot()
        assert bot._is_horario_question("me informa o horario") is True

    def test_saudacao_nao_confunde(self):
        bot = make_bot()
        assert bot._is_horario_question("boa noite, como voces estao?") is False

    def test_biblica_nao_confunde(self):
        bot = make_bot()
        assert bot._is_horario_question("qual versiculo fala sobre amor?") is False


@pytest.mark.asyncio
class TestHorarioQuestionResponse:
    async def test_horario_question_returns_official_response(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        resp = await bot._decide_response("Bia", "que horas comeca o culto?")
        assert "19:30" in resp
        assert "18:00" in resp
        assert "10:00" in resp

    async def test_horario_response_built_from_config(self):
        bot = make_bot()
        assert "Quarta-feira - 19:30" in bot.resposta_horario
        assert "Domingo (manha) - 10:00" in bot.resposta_horario
        assert "Domingo (noite) - 18:00" in bot.resposta_horario

    async def test_horario_question_does_not_hit_ai(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        called = False

        async def fake_generate(author, message, kw=""):
            nonlocal called
            called = True
            return "NAO DEVERIA SER CHAMADO"

        bot.ai.generate = fake_generate
        resp = await bot._decide_response("Bia", "que horas comeca o culto?")
        assert called is False
        assert resp == bot.resposta_horario