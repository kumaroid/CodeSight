# CodeSight — Платформа анализа качества кода

**CodeSight** — веб-платформа для комплексного анализа программных проектов: статический анализ, проверка безопасности, оценка архитектурной связности и AI-рекомендации по улучшению кода — всё в одном окне.

---

## Проблема

Современная индустрия ПО накапливает технический долг быстрее, чем его успевают гасить. Разработчики используют разрозненные инструменты без единой картины качества: статические анализаторы, сканеры безопасности и метрики архитектуры живут отдельно и не позволяют оценить качество проекта. Итог — утечки памяти, уязвимости и архитектурная деградация.

CodeSight объединяет всё это в единую платформу с AI-агентом, который умеет не просто находить проблемы, но и рекомендовать, как их исправить.
Построен на **LangGraph** + **GigaChat**. Получает сводный контекст от всех микросервисов анализа и формирует:
- Приоритизированный список проблем
- Конкретные рекомендации по исправлению
- Оценку технического долга

---

## Стек технологий

| Слой | Технологии |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| **AI / LLM** | LangGraph, LangChain, GigaChat |
| **Очередь событий** | Apache Kafka |
| **Базы данных** | PostgreSQL (asyncpg), Redis |
| **Хранилище файлов** | Ceph |
| **Инфраструктура** | Docker, Docker Compose |
| **Анализаторы** | Ruff, Radon, Bandit, mypy |

---

## API

После запуска документация доступна по адресам:

| Сервис | Swagger UI |
|---|---|
| Auth Service | http://localhost:8001/docs |
| Loader Service | http://localhost:8002/docs |
| Analysis Service | http://localhost:8003/docs |
| Testing Service | http://localhost:8004/docs |
| Security Service | http://localhost:8005/docs |
| Arch Service | http://localhost:8006/docs |
| Orchestrator Service | http://localhost:8007/docs |
| DAST Service | http://localhost:8008/docs |


## Структура репозитория

```
CodeSight/
├── codesight_backend/
│   ├── auth_service/            # Аутентификация и авторизация (порт 8001)
│   ├── loader_service/          # Загрузка проектов (порт 8002)
│   ├── sast_service/            # Статический анализ (порт 8003)
│   ├── testing_service/         # Тестирование и покрытие (порт 8004)
│   ├── security_service/        # Безопасность (порт 8005)
│   ├── arch_service/            # Архитектурный анализ (порт 8006)
│   ├── orchestrator_service/    # Saga-оркестратор (порт 8007)
│   ├── dast_service/            # Dynamic analysis / Valgrind (порт 8008)
│   ├── archer/                  # AI-рекомендации
│   └── kafka_common/            # Общие Kafka-утилиты
├── codesight_frontend/          # Фронтенд
├── docker-compose.yml
├── docker-compose.infra.yml
├── pyproject.toml
└── .env.example
```
