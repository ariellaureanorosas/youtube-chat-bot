#!/usr/bin/env python3
"""
Persistência de estado — Armazena o histórico de mensagens processadas.
=========================================================================
Encapsula a leitura/escrita de `responded_messages.json` (o conjunto de
mensagens já vistas, para não responder duas vezes à mesma) e de outros
estados auxiliares de sessão. Mantém o bot desacoplado de I/O em disco.
"""

import json
import logging
import time
from pathlib import Path

log = logging.getLogger("youtube_chat_bot")


class MessageStore:
    """Persiste e rastreia as mensagens já processadas."""

    def __init__(self, path: Path, max_entries: int = 2000) -> None:
        self.path = path
        self.max_entries = max_entries
        self.seen: set[str] = set()
        self.last_save: float = 0.0

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.seen = set(data)
                    log.info(
                        f"Carregadas {len(self.seen)} mensagens ja processadas"
                    )
        except Exception as e:
            log.warning(f"Erro ao carregar {self.path.name}: {e}")

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(list(self.seen), ensure_ascii=False),
                encoding="utf-8",
            )
            self.last_save = time.time()
        except Exception as e:
            log.warning(f"Erro ao salvar {self.path.name}: {e}")

    def add(self, key: str) -> None:
        self.seen.add(key)
        if len(self.seen) > self.max_entries:
            self.seen = set(list(self.seen)[-self.max_entries // 2:])

    def clear(self) -> None:
        self.seen.clear()
