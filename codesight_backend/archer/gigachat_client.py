"""Тонкая обёртка над GigaChat SDK с устойчивостью к сбоям.

Если ключ не задан или клиент не смог установить соединение — клиент
возвращает `None` вместо генерации, чтобы вызывающий код мог переключиться
на rule-based fallback.
"""

from __future__ import annotations

import logging
import os

from .promts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GigaChatArchitectureAdvisor:
    """Lazy-инициализируемый клиент GigaChat.

    Создание реального `GigaChat` объекта откладывается до первого вызова
    `recommend()` — это нужно, чтобы импорт модуля не падал, если SDK
    не установлен или сертификаты не настроены.
    """

    def __init__(self) -> None:
        self._client = None
        self._init_failed = False

    def _ensure_client(self) -> None:
        if self._client is not None or self._init_failed:
            return
        creds = os.getenv("AUTH_GC_KEY")
        if not creds:
            logger.info("AUTH_GC_KEY не задан — GigaChat недоступен.")
            self._init_failed = True
            return
        try:
            from gigachat import (
                GigaChat,
            )  # импорт тут чтобы не падать при отсутствии SDK
        except ImportError as exc:
            logger.warning("gigachat SDK не установлен: %s", exc)
            self._init_failed = True
            return
        try:
            self._client = GigaChat(
                credentials=creds,
                verify_ssl_certs=False,
                model=os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось инициализировать GigaChat: %s", exc)
            self._init_failed = True

    def is_available(self) -> bool:
        self._ensure_client()
        return self._client is not None

    def recommend(self, user_prompt: str) -> str | None:
        """Возвращает текст рекомендаций или `None` при ошибке."""
        self._ensure_client()
        if self._client is None:
            return None
        try:
            response = self._client.chat(
                {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                }
            )
            return response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ошибка вызова GigaChat: %s", exc)
            return None
