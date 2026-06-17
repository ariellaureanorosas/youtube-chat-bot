import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from youtube_chat_bot import YoutubeChatBot


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
    async def test_ai_disabled_falls_to_rules(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = False
        resp = await bot._decide_response("Joao", "Amem")
        assert resp == "Amem! Gloria a Deus!"

    async def test_ai_returns_none_no_keyword_and_no_fallback(self):
        bot = make_bot()
        bot.ai_mode = "ai"
        bot.ai.enabled = True
        bot._allow_fallback = False
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
