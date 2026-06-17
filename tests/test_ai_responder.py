import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_responder import AIResponder


def make_responder(**overrides):
    cfg = {
        "enabled": True,
        "mode": "ai",
        "model": "deepseek-v4-flash-free",
        "temperature": 0.7,
        "max_tokens": 100,
        "system_prompt": "Voce e um assistente util.",
    }
    cfg.update(overrides)
    return AIResponder(cfg)


class TestAIResponderInit:
    def test_enabled_by_default(self):
        r = make_responder()
        assert r.enabled is True

    def test_disabled_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        r = make_responder()
        assert r.enabled is False

    def test_disabled_explicitly(self):
        r = make_responder(enabled=False)
        assert r.enabled is False

    def test_model_from_config(self):
        r = make_responder(model="gpt-4")
        assert r.model == "gpt-4"

    def test_temperature_from_config(self):
        r = make_responder(temperature=0.5)
        assert r.temperature == 0.5


class TestBuildPrompt:
    def test_with_keyword(self):
        r = make_responder()
        prompt = r._build_prompt("Joao", "Bom dia", "saudacao")
        assert "Joao" in prompt
        assert "Bom dia" in prompt
        assert "saudacao" in prompt
        assert "SKIP" in prompt

    def test_without_keyword(self):
        r = make_responder()
        prompt = r._build_prompt("Maria", "Amem", "")
        assert "Maria" in prompt
        assert "Amem" in prompt
        assert "SKIP" in prompt

    def test_empty_author(self):
        r = make_responder()
        prompt = r._build_prompt("", "Ola", "")
        assert "SKIP" in prompt


class TestIsSkip:
    def test_exact_skip(self):
        assert AIResponder._is_skip("SKIP") is True

    def test_skip_lowercase(self):
        assert AIResponder._is_skip("skip") is True

    def test_skip_with_dot(self):
        assert AIResponder._is_skip("SKIP.") is True

    def test_skip_with_newline(self):
        assert AIResponder._is_skip("SKIP\n") is True

    def test_skip_in_sentence(self):
        assert AIResponder._is_skip("I should SKIP this") is True

    def test_not_skip(self):
        assert AIResponder._is_skip("Amem! Gloria a Deus") is False

    def test_empty_string(self):
        assert AIResponder._is_skip("") is False

    def test_skip_with_punctuation(self):
        assert AIResponder._is_skip("SKIP!") is True

    def test_skip_with_spaces(self):
        assert AIResponder._is_skip("  SKIP  ") is True


class TestCleanupCache:
    def test_removes_old_entries(self):
        r = make_responder()
        old = time.time() - 300
        r._cache = {"a": ("resposta", old)}
        r._cache_access_count = 50
        r._cleanup_cache()
        assert len(r._cache) == 0

    def test_keeps_recent_entries(self):
        r = make_responder()
        r._cache = {"a": ("resposta", time.time())}
        r._cache_access_count = 50
        r._cleanup_cache()
        assert len(r._cache) == 1

    def test_resets_access_count(self):
        r = make_responder()
        r._cache = {"a": ("resposta", time.time())}
        r._cache_access_count = 50
        r._cleanup_cache()
        assert r._cache_access_count == 0

    def test_caps_at_100_items(self):
        r = make_responder()
        now = time.time()
        for i in range(150):
            r._cache[f"k{i}"] = (f"v{i}", now - i * 0.1)
        r._cache_access_count = 50
        r._cleanup_cache()
        assert len(r._cache) <= 100


class TestGenerateDisabled:
    def test_returns_none_when_disabled(self):
        r = make_responder(enabled=False)
        result = r.generate("Joao", "Bom dia")
        # Must await to call, but we can test via event loop
        import asyncio
        res = asyncio.run(r.generate("Joao", "Bom dia"))
        assert res is None

    def test_returns_none_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
        r = make_responder()
        import asyncio
        res = asyncio.run(r.generate("Joao", "Bom dia"))
        assert res is None


import time
