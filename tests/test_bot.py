import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from youtube_chat_bot import YoutubeChatBot


SAMPLE_CONFIG = {
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
    cfg = dict(SAMPLE_CONFIG)
    cfg.update(overrides)
    return YoutubeChatBot(cfg)


class TestDecideResponseOffMode:
    def test_matched_rule_returns_response(self):
        bot = make_bot()
        resp = bot._decide_response("Joao", "Amem")
        assert resp == "Amem! Gloria a Deus!"

    def test_matched_rule_different_keyword(self):
        bot = make_bot()
        resp = bot._decide_response("Maria", "Bom dia")
        assert resp == "Bem-vindo ao culto!"

    def test_no_match_returns_default(self):
        bot = make_bot()
        resp = bot._decide_response("Jose", "Qual o horario?")
        assert resp == "Amem!"

    def test_empty_message_returns_none(self):
        bot = make_bot()
        resp = bot._decide_response("Joao", "")
        assert resp is None

    def test_default_disabled_returns_none(self):
        cfg = dict(SAMPLE_CONFIG)
        cfg["default_response"]["enabled"] = False
        bot = YoutubeChatBot(cfg)
        resp = bot._decide_response("Jose", "Qual o horario?")
        assert resp is None


class TestCooldown:
    def test_cooldown_blocks_repeat(self):
        bot = make_bot()
        resp1 = bot._apply_rule(0, SAMPLE_CONFIG["response_rules"][0])
        assert resp1 is not None
        resp2 = bot._apply_rule(0, SAMPLE_CONFIG["response_rules"][0])
        assert resp2 is None

    def test_cooldown_expires(self):
        import time
        bot = make_bot()
        rule = dict(SAMPLE_CONFIG["response_rules"][0])
        rule["cooldown"] = 0.001
        resp1 = bot._apply_rule(0, rule)
        assert resp1 is not None
        time.sleep(0.002)
        resp2 = bot._apply_rule(0, rule)
        assert resp2 is not None

    def test_different_rules_independent(self):
        bot = make_bot()
        resp1 = bot._apply_rule(0, SAMPLE_CONFIG["response_rules"][0])
        assert resp1 is not None
        resp2 = bot._apply_rule(1, SAMPLE_CONFIG["response_rules"][1])
        assert resp2 is not None


class TestDecideResponseAiMode:
    def test_ai_returns_none_if_disabled(self):
        cfg = dict(SAMPLE_CONFIG)
        cfg["ai"]["enabled"] = False
        cfg["ai"]["mode"] = "ai"
        bot = YoutubeChatBot(cfg)
        resp = bot._decide_response("Joao", "Amem")
        assert resp is None


class TestDefaultResponse:
    def test_default_enabled(self):
        bot = make_bot()
        resp = bot._default_response()
        assert resp == "Amem!"

    def test_default_disabled(self):
        cfg = dict(SAMPLE_CONFIG)
        cfg["default_response"]["enabled"] = False
        bot = YoutubeChatBot(cfg)
        resp = bot._default_response()
        assert resp is None
