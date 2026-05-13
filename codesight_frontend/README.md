# CodeSight Frontend

React-приложение для анализа качества Python-проектов через CodeSight backend.

## Возможности

- Регистрация и вход (JWT)
- Загрузка проекта по URL Git-репозитория или ZIP-архивом
- Запуск Saga-оркестратора со всеми пятью шагами анализа: SAST, security, архитектура, тесты, DAST
- Реальное-время полинг состояния Saga с обновлением статуса каждого шага
- Сводный отчёт с интегральным quality-score, агрегирующий метрики из всех сервисов анализа
- Детальные страницы безопасности (OWASP / CWE) и архитектуры (Coupling / Cohesion)
- История запусков по проекту

## Стек

- React 18 + react-router 6
- axios
- lucide-react (иконки)
- Build: `react-scripts` (Create React App)
- Production deploy: nginx (Docker)

## Структура

```
src/
├── api/                  HTTP-клиенты по каждому микросервису backend
├── components/layout/    Сайдбар и общий layout
├── context/              AuthContext (JWT, /auth/me)
├── hooks/                useProjectAnalysis — комплексный полинг по саге
├── pages/                Login / Register / Projects / AddProject / BuildStatus / Report / Security / Arch / Detail
├── utils/                status.js — маппинги статусов
├── App.js                роуты
├── index.css             темa
└── index.js              entry point
```

## Локальный запуск (dev)

Перед стартом подними backend через `docker compose up --build -d` в корне репозитория (см. главный README).

```bash
cd codesight_frontend
cp .env.example .env
npm install --legacy-peer-deps
npm start
```

Откроется на [http://localhost:3000](http://localhost:3000).

`react-scripts` 5 конфликтует с npm 9+ по peer-deps, поэтому ставится с `--legacy-peer-deps`.

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `REACT_APP_AUTH_URL` | Auth service | `http://localhost:8001` |
| `REACT_APP_LOADER_URL` | Loader service | `http://localhost:8002` |
| `REACT_APP_SAST_URL` | SAST / статический анализ | `http://localhost:8003` |
| `REACT_APP_TESTING_URL` | Testing service | `http://localhost:8004` |
| `REACT_APP_SECURITY_URL` | Security scanner | `http://localhost:8005` |
| `REACT_APP_ARCH_URL` | Arch service | `http://localhost:8006` |
| `REACT_APP_ORCHESTRATOR_URL` | Orchestrator (Saga) | `http://localhost:8007` |
| `REACT_APP_DAST_URL` | DAST service | `http://localhost:8008` |

## Запуск в Docker

В `docker-compose.yml` есть сервис `frontend` (nginx + production-сборка React) на порту `3000`. Сборка выполнится автоматически:

```bash
docker compose up --build -d
```

После запуска интерфейс доступен на [http://localhost:3000](http://localhost:3000), а API сервисов — на портах 8001–8008.

При сборке Docker подставляет URL-ы из переменных `REACT_APP_*` корневого `.env` (или дефолтные значения `http://localhost:<port>`).

## Поток работы пользователя

1. **Регистрация** → автоматический логин.
2. **Список проектов** → кнопка «Добавить проект».
3. **Добавление проекта** — Git URL или ZIP, выбор шагов анализа.
4. После загрузки автоматически создаётся Saga и пользователя перебрасывает на страницу статуса. Frontend опрашивает `GET /orchestrator/sagas/{saga_id}` каждые ~3.5 с.
5. Когда Saga завершена — переход к отчёту. Отчёт подтягивает результаты SAST, security, arch и testing (по их `run_id` из `saga.steps_run_ids`).
6. Со страницы отчёта можно открыть детальные экраны security и архитектуры.

## Карта эндпоинтов backend

| Backend endpoint | Frontend модуль |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/me` | `src/api/auth.js`, `src/context/AuthContext.js` |
| `POST /projects/upload/{zip,repo}`, `GET /projects/`, `/{id}`, `DELETE /{id}` | `src/api/projects.js`, `ProjectsPage`, `AddProjectPage` |
| `POST /orchestrator/sagas`, `GET /orchestrator/sagas/{id}`, `GET /orchestrator/sagas?project_id=...` | `src/api/orchestrator.js`, `BuildStatusPage`, `DetailPage` |
| `GET /analysis/runs/{run_id}` | `src/api/analysis.js`, `ReportPage` |
| `GET /security/scans/{scan_id}` | `src/api/analysis.js`, `SecurityPage` |
| `GET /arch/runs/{run_id}` | `src/api/analysis.js`, `ArchPage` |
| `GET /testing/runs/{run_id}` | `src/api/analysis.js`, `ReportPage` |
