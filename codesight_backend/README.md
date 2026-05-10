# CodeSight Backend — Инструкция по запуску

## Обзор архитектуры

Бэкенд представляет собой набор независимых микросервисов:

| Сервис | Порт | БД | Описание |
|---|---|---|---|
| `auth_service` | 8001 | PostgreSQL (5433) | Аутентификация и JWT |
| `loader_service` | 8002 | PostgreSQL (5434→?) | Загрузка и распаковка проектов |
| `analysis_service` | 8003 | PostgreSQL (5434) | Анализ кода |
| `security_service` | 8005 | PostgreSQL (5435) | Проверка безопасности |
| `arch_service` | 8006 | PostgreSQL (5436) | Анализ архитектуры |
| `orchestrator_service` | 8007 | PostgreSQL | Orchestration через Kafka Saga |

Инфраструктура: **PostgreSQL 16**, **Apache Kafka** (Confluent 7.6.1) + ZooKeeper, **Redis 7.2**, **Kafka UI**.

---

## Требования

- [Docker](https://docs.docker.com/get-docker/) >= 24
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.20
- Git

---

## Быстрый старт (Docker Compose)

### 1. Клонирование репозитория

```bash
git clone https://github.com/kumaroid/CodeSight.git
cd CodeSight
```

### 2. Создание файла переменных окружения

Скопируйте шаблон и заполните значения:

```bash
cp .env.example .env
```

Откройте `.env` и убедитесь, что заданы все переменные (подробнее — в разделе [Переменные окружения](#переменные-окружения)).

### 3. Запуск всей инфраструктуры и сервисов

```bash
docker compose up --build -d
```

Docker Compose автоматически:
- поднимет ZooKeeper и Kafka,
- создаст все базы данных PostgreSQL,
- запустит Redis,
- соберёт и запустит все микросервисы.

### 4. Проверка состояния

```bash
docker compose ps
```

Все контейнеры должны быть в статусе `Up` или `Up (healthy)`.

---

## Переменные окружения

Создайте файл `.env` в **корне репозитория** (рядом с `docker-compose.yml`). Ниже полный список переменных:

```dotenv
# ── JWT ──────────────────────────────────────────────────────────────
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Auth DB ──────────────────────────────────────────────────────────
AUTH_DB_USER=postgres
AUTH_DB_PASSWORD=postgres
AUTH_DB_NAME=auth_db
# DATABASE_URL строится автоматически в docker-compose; можно переопределить:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@auth_db:5432/auth_db

# ── Loader / Project DB ──────────────────────────────────────────────
PROJECT_DB_USER=postgres
PROJECT_DB_PASSWORD=postgres
PROJECT_DB_NAME=project_db
# PROJECT_DATABASE_URL=postgresql+asyncpg://postgres:postgres@loader_db:5432/project_db
PROJECT_STORAGE_DIR=/tmp/codesight_projects
PROJECT_MAX_ZIP_SIZE=52428800   # 50 MB

# ── Analysis DB ──────────────────────────────────────────────────────
ANALYSIS_DB_USER=postgres
ANALYSIS_DB_PASSWORD=postgres
ANALYSIS_DB_NAME=analysis_db
# ANALYSIS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@analysis_db:5432/analysis_db

# ── Security DB ──────────────────────────────────────────────────────
SECURITY_DB_USER=postgres
SECURITY_DB_PASSWORD=postgres
SECURITY_DB_NAME=security_db
# SECURITY_DATABASE_URL=postgresql+asyncpg://postgres:postgres@security_db:5432/security_db

# ── Architecture DB ──────────────────────────────────────────────────
ARCH_DB_USER=postgres
ARCH_DB_PASSWORD=postgres
ARCH_DB_NAME=arch_db
# ARCH_DATABASE_URL=postgresql+asyncpg://postgres:postgres@arch_db:5432/arch_db

# ── Orchestrator DB ──────────────────────────────────────────────────
# ORCHESTRATOR_DATABASE_URL=postgresql+asyncpg://postgres:postgres@orchestrator_db:5432/orchestrator_db

# ── Kafka ─────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

> **Важно:** Никогда не коммитьте `.env` с реальными секретами в репозиторий. Файл уже добавлен в `.gitignore`.

---

## Развёртывание инфраструктуры по шагам

Если нужно поднять только инфраструктуру (БД, Kafka, Redis), используйте отдельный файл:

```bash
docker compose -f docker-compose.infra.yml up -d
```

### Kafka (Confluent Platform 7.6.1)

| Компонент | Контейнер | Порт |
|---|---|---|
| ZooKeeper | `codesight_zookeeper` | 2181 |
| Kafka Broker | `codesight_kafka` | 9092 (внешний), 29092 (внутренний) |
| Kafka UI | `codesight_kafka_ui` | 8080 |

**Внутри Docker-сети** сервисы должны использовать адрес `kafka:29092`.  
**С хост-машины** брокер доступен по `localhost:9092`.

Kafka UI доступен по адресу [http://localhost:8080](http://localhost:8080) — удобный веб-интерфейс для просмотра топиков и сообщений.

#### Топики Kafka (создаются автоматически)

| Топик | Направление | Описание |
|---|---|---|
| `codesight.analysis.start` | Orchestrator → Analysis | Команда начала анализа кода |
| `codesight.security.start` | Orchestrator → Security | Команда начала проверки безопасности |
| `codesight.arch.start` | Orchestrator → Arch | Команда анализа архитектуры |
| `codesight.testing.start` | Orchestrator → Testing | Команда запуска тестирования |
| `codesight.analysis.result` | Analysis → Orchestrator | Результат анализа кода |
| `codesight.security.result` | Security → Orchestrator | Результат проверки безопасности |
| `codesight.arch.result` | Arch → Orchestrator | Результат анализа архитектуры |
| `codesight.testing.result` | Testing → Orchestrator | Результат тестирования |
| `codesight.saga.state` | Orchestrator → Frontend | Обновление состояния саги |

Топики создаются автоматически благодаря `KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"`. Если нужно создать их вручную:

```bash
docker exec -it codesight_kafka kafka-topics \
  --bootstrap-server localhost:29092 \
  --create --topic codesight.analysis.start \
  --partitions 1 --replication-factor 1
```

### PostgreSQL

Каждый сервис имеет **собственную базу данных**:

| БД | Контейнер | Хост-порт | Имя БД |
|---|---|---|---|
| Auth | `codesight_auth_db` | 5433 | `auth_db` |
| Analysis | `codesight_analysis_db` | 5434 | `analysis_db` |
| Security | `codesight_security_db` | 5435 | `security_db` |
| Arch | `codesight_arch_db` | 5436 | `arch_db` |

Подключение с хост-машины (пример для auth_db):

```bash
psql -h localhost -p 5433 -U postgres -d auth_db
```

Миграции применяются **автоматически при старте** каждого сервиса через SQLAlchemy (Alembic или `create_all`).

### Redis

Контейнер `codesight_redis` доступен на порту **6379**. Данные сохраняются в volume `redis_data`.

---

## Запуск отдельных сервисов

### Все сервисы разом

```bash
docker compose up --build -d
```

### Один конкретный сервис (с его зависимостями)

```bash
docker compose up --build -d auth_service
```

### Пересборка после изменений кода

```bash
docker compose up --build -d <service_name>
```

---

## Локальный запуск (без Docker)

Для разработки можно запустить сервисы напрямую, подняв только инфраструктуру в Docker.

### 1. Инфраструктура в Docker

```bash
docker compose -f docker-compose.infra.yml up -d
```

### 2. Установка зависимостей Python

Проект использует [uv](https://github.com/astral-sh/uv) для управления зависимостями:

```bash
pip install uv
```

Для каждого сервиса, например `auth_service`:

```bash
cd codesight_backend/auth_service
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Переменные окружения для локального запуска

При локальном запуске DATABASE_URL нужно указать с `localhost`:

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/auth_db"
export JWT_SECRET_KEY="your-dev-secret"
```

### 4. Запуск сервиса

```bash
python main.py
# или
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Порты по умолчанию для каждого сервиса:

| Сервис | Порт |
|---|---|
| auth_service | 8001 |
| loader_service | 8002 |
| analysis_service | 8003 |
| security_service | 8005 |
| arch_service | 8006 |
| orchestrator_service | 8007 |

---

## Проверка работоспособности

### Health-check через HTTP

Каждый сервис предоставляет документацию Swagger/OpenAPI:

- Auth Service: [http://localhost:8001/docs](http://localhost:8001/docs)
- Loader Service: [http://localhost:8002/docs](http://localhost:8002/docs)
- Analysis Service: [http://localhost:8003/docs](http://localhost:8003/docs)
- Security Service: [http://localhost:8005/docs](http://localhost:8005/docs)
- Arch Service: [http://localhost:8006/docs](http://localhost:8006/docs)
- Orchestrator Service: [http://localhost:8007/docs](http://localhost:8007/docs)

### Проверка Kafka

```bash
# Список топиков
docker exec -it codesight_kafka kafka-topics \
  --bootstrap-server localhost:29092 --list

# Просмотр сообщений в топике
docker exec -it codesight_kafka kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic codesight.saga.state \
  --from-beginning
```

### Логи сервисов

```bash
# Логи конкретного сервиса
docker compose logs -f auth_service

# Логи всех сервисов
docker compose logs -f
```

---

## Остановка

```bash
# Остановить все контейнеры (данные сохранятся в volumes)
docker compose down

# Остановить и удалить все данные (volumes)
docker compose down -v
```

---

## Структура директории

```
codesight_backend/
├── analysis_service/      # Сервис анализа кода (порт 8003)
├── arch_service/          # Сервис анализа архитектуры (порт 8006)
├── auth_service/          # Сервис аутентификации (порт 8001)
├── loader_service/        # Сервис загрузки проектов (порт 8002)
├── orchestrator_service/  # Оркестратор Kafka Saga (порт 8007)
├── security_service/      # Сервис проверки безопасности (порт 8005)
├── testing_service/       # Сервис тестирования
├── archer/                # Вспомогательный модуль arch_service
└── app.py                 # Точка входа общего приложения
```

---

## Возможные проблемы

### Kafka не запускается

ZooKeeper должен быть полностью запущен до Kafka. Docker Compose обрабатывает зависимости автоматически, но если Kafka падает — проверьте:

```bash
docker compose logs zookeeper
docker compose logs kafka
```

### Сервис не может подключиться к БД

Убедитесь, что healthcheck PostgreSQL пройден (`healthy`):

```bash
docker compose ps auth_db
```

Если БД ещё не готова, сервис будет перезапускаться автоматически благодаря `restart: unless-stopped`.

### Ошибка `address already in use`

Один из портов уже занят. Проверьте занятые порты:

```bash
# Linux/macOS
lsof -i :8001

# Windows
netstat -ano | findstr :8001
```

Остановите конфликтующий процесс или измените порт в `docker-compose.yml` и `.env`.

### Общий volume для проектов

Сервисы `loader_service`, `analysis_service` и `security_service` используют общий Docker volume `projects_storage`, смонтированный в `/tmp/codesight_projects`. Это позволяет сервисам видеть распакованные проекты без передачи файлов через сеть.
