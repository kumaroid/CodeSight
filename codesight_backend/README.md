Бэкенд представляет собой набор независимых микросервисов:

| Сервис | Порт | БД | Описание |
|---|---|---|---|
| `auth_service` | 8001 | PostgreSQL (5433) | Аутентификация и JWT |
| `loader_service` | 8002 | PostgreSQL (5440) | Загрузка и распаковка проектов |
| `analysis_service` | 8003 | PostgreSQL (5434) | Анализ кода |
| `security_service` | 8005 | PostgreSQL (5435) | Проверка безопасности |
| `arch_service` | 8006 | PostgreSQL (5436) | Анализ архитектуры |
| `testing_service` | 8004 | PostgreSQL (5437) | pytest, coverage, полнота тестов |
| `dast_service` | 8008 | PostgreSQL (5438) | Valgrind + динамическая проверка |
| `orchestrator_service` | 8007 | PostgreSQL (5439) | Orchestration через Kafka Saga |

Инфраструктура: **PostgreSQL 16**, **Apache Kafka** && **Kafka UI**.

Kafka UI живет тут [http://localhost:8080](http://localhost:8080)

#### Топики Kafka

| Топик | Направление | Описание |
|---|---|---|
| `codesight.analysis.start` | Orchestrator → Analysis | Команда начала анализа кода |
| `codesight.security.start` | Orchestrator → Security | Команда начала проверки безопасности |
| `codesight.arch.start` | Orchestrator → Arch | Команда анализа архитектуры |
| `codesight.testing.start` | Orchestrator → Testing | Команда запуска тестирования |
| `codesight.dast.start` | Orchestrator → DAST | Команда динамического анализа (Valgrind) |
| `codesight.analysis.result` | Analysis → Orchestrator | Результат анализа кода |
| `codesight.security.result` | Security → Orchestrator | Результат проверки безопасности |
| `codesight.arch.result` | Arch → Orchestrator | Результат анализа архитектуры |
| `codesight.testing.result` | Testing → Orchestrator | Результат тестирования |
| `codesight.dast.result` | DAST → Orchestrator | Результат динамического анализа |
| `codesight.saga.state` | Orchestrator → Frontend | Обновление состояния саги |


### PostgreSQL

Каждый сервис имеет **собственную базу данных**:

| БД | Контейнер | Хост-порт | Имя БД |
|---|---|---|---|
| Auth | `codesight_auth_db` | 5433 | `auth_db` |
| Loader | `codesight_loader_db` | 5440 | `project_db` |
| Analysis | `codesight_analysis_db` | 5434 | `analysis_db` |
| Security | `codesight_security_db` | 5435 | `security_db` |
| Arch | `codesight_arch_db` | 5436 | `arch_db` |
| Testing | `codesight_testing_db` | 5437 | `testing_db` |
| DAST | `codesight_dast_db` | 5438 | `dast_db` |
| Orchestrator | `codesight_orchestrator_db` | 5439 | `orchestrator_db` |

Миграции применяются **автоматически при старте** каждого сервиса

### Микросервисы

Health-check через HTTP
Каждый сервис предоставляет документацию Swagger/OpenAPI:

- Auth Service: [http://localhost:8001/docs](http://localhost:8001/docs)
- Loader Service: [http://localhost:8002/docs](http://localhost:8002/docs)
- Analysis Service: [http://localhost:8003/docs](http://localhost:8003/docs)
- Security Service: [http://localhost:8005/docs](http://localhost:8005/docs)
- Arch Service: [http://localhost:8006/docs](http://localhost:8006/docs)
- Orchestrator Service: [http://localhost:8007/docs](http://localhost:8007/docs)


## Структура

```
codesight_backend/
├── analysis_service/      # Сервис анализа кода (порт 8003)
├── arch_service/          # Сервис анализа архитектуры (порт 8006)
├── auth_service/          # Сервис аутентификации (порт 8001)
├── loader_service/        # Сервис загрузки проектов (порт 8002)
├── orchestrator_service/  # Оркестратор Kafka Saga (порт 8007)
├── security_service/      # Сервис проверки безопасности (порт 8005)
├── testing_service/       # Сервис тестирования
├── dast_service/          # Динамический анализ (Valgrind), порт 8008
├── archer/                # Вспомогательный модуль arch_service
└── app.py                 # Точка входа общего приложения
```

---

