import time

import pytest
from youtube_chat_bot.ai_responder import AIResponder


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
    # Ensure env var is NOT set so we control when it's available
    return AIResponder(cfg)


class TestAIResponderInit:
    def test_enabled_by_default(self):
        r = make_responder()
        assert r.enabled is True

    def test_disabled_when_no_api_key(self):
        r = make_responder()
        if r.api_key:
            pytest.skip("API key esta definida no ambiente")
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

    def test_api_key_from_config(self):
        r = make_responder(api_key="chave-do-config")
        assert r.api_key == "chave-do-config"

    def test_api_key_from_config_trumps_env(self):
        import os
        os.environ["NVIDIA_API_KEY"] = "chave-da-env"
        try:
            r = make_responder(api_key="chave-do-config")
            assert r.api_key == "chave-do-config"
        finally:
            os.environ.pop("NVIDIA_API_KEY", None)

    def test_api_url_defaults_to_nvidia(self):
        r = make_responder()
        assert r.api_url == "https://integrate.api.nvidia.com/v1/chat/completions"

    def test_api_url_from_config(self):
        r = make_responder(api_url="https://example.com/v1")
        assert r.api_url == "https://example.com/v1"

    def test_culto_horarios_from_config(self):
        r = make_responder(
            culto_horarios=["Quarta - 19:30", "Domingo (manha) - 10:00"]
        )
        assert r.culto_horarios == ["Quarta - 19:30", "Domingo (manha) - 10:00"]

    def test_culto_horarios_empty_default(self):
        r = make_responder()
        assert r.culto_horarios == []

    def test_culto_horarios_filters_blanks(self):
        r = make_responder(culto_horarios=["Quarta - 19:30", "", "  "])
        assert r.culto_horarios == ["Quarta - 19:30"]


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

    def test_injects_culto_horarios(self):
        r = make_responder(
            culto_horarios=["Quarta - 19:30", "Domingo (noite) - 18:00"]
        )
        prompt = r._build_prompt("Joao", "Qual o horario?", "horario")
        assert "OFICIAIS" in prompt
        assert "Quarta - 19:30" in prompt
        assert "Domingo (noite) - 18:00" in prompt

    def test_culto_horarios_absent_when_empty(self):
        r = make_responder()
        prompt = r._build_prompt("Maria", "Ola", "")
        assert "OFICIAIS" not in prompt


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


class TestCleanResponse:
    def test_removes_trailing_bracket_annotation(self):
        out = AIResponder._clean_response(
            "Bom dia, Maria! Que Deus abençoe. 🙏\n\n[Resposta apropriada]"
        )
        assert out == "Bom dia, Maria! Que Deus abençoe. 🙏"

    def test_removes_response_prefix(self):
        out = AIResponder._clean_response("responseBom dia, Maria!")
        assert out == "Bom dia, Maria!"

    def test_removes_annotation_and_duplicate(self):
        out = AIResponder._clean_response(
            "Bom dia, Maria! 🙏\n\n[Resposta apropriada - geral]\n"
            "responseBom dia, Maria! 🙏"
        )
        assert out == "Bom dia, Maria! 🙏"

    def test_keeps_normal_response(self):
        out = AIResponder._clean_response("Bom dia, Maria! 🙏")
        assert out == "Bom dia, Maria! 🙏"

    def test_empty(self):
        assert AIResponder._clean_response("") == ""

    def test_multiblock_picks_richest(self):
        out = AIResponder._clean_response(
            "[Bom dia! Nos da TV IEBT ]\n\n"
            "Marcia, que bom saber que a palavra de Deus esta tocando "
            "seu coracao. 🙏\n\n"
            "responseBom dia! Nos da TV IEBT acreditamos que a Palavra "
            "de Deus e viva e poderosa, e e uma bencao poder ouvi-la. "
            "Que o Senhor continue guiando cada um de voces! 🙏"
        )
        assert "acreditamos que a Palavra" in out
        assert "Nos da TV IEBT acreditamos" in out

    def test_residual_response_duplicate_removed(self):
        out = AIResponder._clean_response(
            "Que bom ter voce conosco. Que Deus o abencoe tambem por ai. 🙏\n"
            "responseQue bom ter voce conosco. Que Deus o abencoe tambem por ai. 🙏"
        )
        assert "\n response" not in out
        assert "Que bom ter voce conosco. Que Deus o abencoe tambem por ai" in out

    def test_residual_response_duplicate_same_line(self):
        out = AIResponder._clean_response(
            "Nosso culto comeca as 9h. Esperamos voce conosco! ✝️\n"
            "responseNosso culto comeca as 9h. Esperamos voce conosco! ✝️"
        )
        assert "\n response" not in out
        assert out == "Nosso culto comeca as 9h. Esperamos voce conosco! ✝️"


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


@pytest.mark.asyncio
class TestGenerateDisabled:
    async def test_returns_none_when_disabled(self):
        r = make_responder(enabled=False)
        res = await r.generate("Joao", "Bom dia")
        assert res is None

    async def test_returns_none_without_api_key(self):
        r = make_responder()
        if r.api_key:
            pytest.skip("API key esta definida no ambiente")
        res = await r.generate("Joao", "Bom dia")
        assert res is None