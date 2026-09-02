import json
from pathlib import Path

from youtube_chat_bot.storage import MessageStore


def make_store(tmp_path):
    path = Path(tmp_path) / "responded.json"
    return MessageStore(path), path


class TestMessageStore:
    def test_load_empty_returns_empty_set(self, tmp_path):
        store, path = make_store(tmp_path)
        assert not path.exists()
        store.load()
        assert store.seen == set()

    def test_add_keys(self, tmp_path):
        store, _ = make_store(tmp_path)
        store.add("a|ola")
        store.add("b|amem")
        assert store.seen == {"a|ola", "b|amem"}

    def test_save_then_load_roundtrip(self, tmp_path):
        store, path = make_store(tmp_path)
        store.add("joao|bom dia")
        store.save()
        assert path.exists()
        store2, _ = make_store(tmp_path)
        store2.load()
        assert store2.seen == {"joao|bom dia"}

    def test_persists_with_invalid_json_adds_nothing(self, tmp_path):
        store, path = make_store(tmp_path)
        path.write_text("isso nao e json {", encoding="utf-8")
        store.load()
        assert store.seen == set()

    def test_persists_only_list(self, tmp_path):
        store, path = make_store(tmp_path)
        path.write_text(json.dumps({"nao": "lista"}), encoding="utf-8")
        store.load()
        assert store.seen == set()

    def test_caps_entries(self, tmp_path):
        store, _ = make_store(tmp_path)
        store.max_entries = 10
        for i in range(20):
            store.add(f"msg-{i}")
        assert len(store.seen) <= 10

    def test_clear(self, tmp_path):
        store, _ = make_store(tmp_path)
        store.add("x")
        store.clear()
        assert store.seen == set()