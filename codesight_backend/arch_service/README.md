# Architecture Service — `arch_service`

Микросервис статического анализа архитектуры проекта на основе PlantUML-диаграммы зависимостей.
Диаграмма генерируется инструментом [arch-blueprint](https://github.com/nkhitrov/arch-blueprint),
после чего передаётся в этот сервис для расчёта метрик **Coupling** и **Cohesion** и получения
рекомендаций по улучшению архитектуры.

---

## Быстрый старт

```bash
# Запустить только arch_service + его базу данных
docker compose up arch_db arch_service

# Swagger UI
open http://localhost:8006/docs
```

---

## API

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/arch/analyze` | Принять PlantUML, рассчитать метрики |
| `GET` | `/arch/runs/{run_id}` | Результаты конкретного прогона |
| `GET` | `/arch/projects/{project_id}/runs` | История прогонов проекта |
| `DELETE` | `/arch/runs/{run_id}` | Удалить прогон |
| `GET` | `/health` | Проверка работоспособности |

### Пример запроса

```http
POST /arch/analyze
Content-Type: application/json

{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "plantuml": "@startuml\npackage \"auth\" {\n  [AuthService]\n  [TokenStore]\n}\npackage \"api\" {\n  [Gateway]\n}\n[Gateway] --> [AuthService]\n[AuthService] --> [TokenStore]\n@enduml"
}
```

### Пример ответа

```json
{
  "id": "...",
  "project_id": "...",
  "status": "completed",
  "metrics": [
    {
      "component": "Gateway",
      "ca": 0, "ce": 1,
      "instability": 1.0,
      "coupling_score": 0.33,
      "cohesion_score": 0.0
    }
  ],
  "recommendations": [
    {
      "severity": "info",
      "rule": "ARCHITECTURE_OK",
      "message": "Метрики в норме. Явных архитектурных нарушений не обнаружено."
    }
  ],
  "summary": {
    "components_count": 3,
    "avg_coupling": 0.22,
    "avg_cohesion": 0.58,
    "avg_instability": 0.5,
    "critical_issues": 0,
    "warning_issues": 0,
    "architecture_health_score": 100
  }
}
```

---

## Метрики

### Исходные данные

Парсер обходит PlantUML-диаграмму и строит граф зависимостей:
- **Компонент** — любой узел вида `[Name]`, `component Name`, `rectangle Name`, `node Name` и т.п.
- **Зависимость** — стрелка вида `-->`, `..>`, `->`, `--`

Для каждого компонента определяется:
- **Ca** (*afferent coupling*) — количество других компонентов, которые зависят **от** данного.
- **Ce** (*efferent coupling*) — количество компонентов, **от которых зависит** данный.
- **package** — имя блока `package {}` / `namespace {}`, в котором объявлен компонент (используется для Cohesion).

---

### Coupling (Связанность)

#### Instability — нестабильность компонента

$$I = \frac{C_e}{C_a + C_e}$$

| Значение | Смысл |
|----------|-------|
| `I = 0` | Полностью стабильный: никто от него не зависит |
| `I = 1` | Полностью нестабильный: ни на него никто не полагается |

Компонент с высоким `I` можно безболезненно изменять; компонент с низким `I` — трудно (изменение затронет много зависимых).

#### Coupling Score — нормализованная связанность

Позволяет сравнивать компоненты в проектах разного размера:

$$\text{CouplingScore} = \frac{C_a + C_e}{N - 1}$$

где `N` — общее число компонентов в диаграмме. Значение принадлежит диапазону `[0, 1]`.

| Диапазон | Интерпретация |
|----------|---------------|
| `0.00 – 0.39` | Низкая связанность — норма |
| `0.40 – 0.59` | Умеренная — стоит следить |
| `0.60 – 0.84` | Высокая — предупреждение (`HIGH_COUPLING`) |
| `0.85 – 1.00` | Критическая — компонент "всё знает" (`GOD_COMPONENT`) |

#### Среднее по проекту

$$\overline{\text{CouplingScore}} = \frac{1}{N} \sum_{i=1}^{N} \text{CouplingScore}_i$$

Если `> 0.60` — выдаётся рекомендация `GLOBAL_HIGH_COUPLING`.

---

### Cohesion (Сплочённость)

Cohesion оценивает, насколько «тесно» компонент связан со своими соседями внутри **одного пакета**. В PlantUML пакет задаётся блоком `package "name" { ... }`.

#### Cohesion Score — прокси-метрика сплочённости

$$\text{CohesionScore} = \frac{|\{d \in \text{deps}(c) \mid \text{pkg}(d) = \text{pkg}(c)\}|}{|\text{deps}(c)|}$$

где `deps(c)` — множество всех компонентов, связанных с `c` (входящие + исходящие рёбра), `pkg(x)` — пакет компонента `x`.

| Значение | Смысл |
|----------|-------|
| `1.0` | Все соседи в том же пакете — высокая сплочённость |
| `0.0` | Все зависимости пересекают границы пакетов — изоляция нарушена |
| `0.5` | Компонент без пакета (нейтральное значение по умолчанию) |

Если `CohesionScore < 0.30` при наличии двух и более зависимостей — выдаётся рекомендация `LOW_COHESION`.

#### Среднее по проекту

$$\overline{\text{CohesionScore}} = \frac{1}{N} \sum_{i=1}^{N} \text{CohesionScore}_i$$

---

### Architecture Health Score

Итоговый балл состояния архитектуры в диапазоне `[0, 100]`:

$$\text{HealthScore} = \max\bigl(0,\ 100 - 20 \cdot n_{\text{critical}} - 5 \cdot n_{\text{warning}}\bigr)$$

где `n_critical` и `n_warning` — количество рекомендаций соответствующего уровня.

---

## Правила и рекомендации

| Код правила | Уровень | Условие | Суть |
|---|---|---|---|
| `GOD_COMPONENT` | 🔴 critical | `CouplingScore ≥ 0.85` | Компонент знает обо всей системе — необходимо декомпозировать |
| `CIRCULAR_DEPENDENCY` | 🔴 critical | A→B и B→A | Циклические зависимости — нарушение принципа ацикличности (ADP) |
| `GLOBAL_HIGH_COUPLING` | 🔴 critical | `avg(CouplingScore) > 0.60` | Вся архитектура сильно связана — рассмотреть Mediator/Façade |
| `HIGH_COUPLING` | 🟡 warning | `0.60 ≤ CouplingScore < 0.85` | Высокая связанность компонента |
| `UNSTABLE_DEPENDENCY` | 🟡 warning | `I ≥ 0.75` и `Ca > 0` | Нарушение SDP: стабильные компоненты зависят от нестабильных |
| `LOW_COHESION` | 🟡 warning | `CohesionScore < 0.30` | Компонент тесно связан с чужими пакетами — нарушение SRP |
| `ARCHITECTURE_OK` | 🟢 info | Нарушений нет | Метрики в пределах нормы |

### Принципы проектирования (справка)

- **ADP** *(Acyclic Dependencies Principle)* — граф зависимостей не должен содержать циклов.
- **SDP** *(Stable Dependencies Principle)* — компоненты должны зависеть от **более стабильных**, а не от менее.
- **SRP** *(Single Responsibility Principle)* — компонент должен иметь одну причину для изменения; низкая cohesion сигнализирует о возможном нарушении.

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `ARCH_DATABASE_URL` | `sqlite+aiosqlite:///./arch.db` | URL базы данных (asyncpg/aiosqlite) |
| `ARCH_DB_USER` | `postgres` | Пользователь PostgreSQL |
| `ARCH_DB_PASSWORD` | `postgres` | Пароль PostgreSQL |
| `ARCH_DB_NAME` | `arch_db` | Имя базы данных |

---

## Интеграция с arch-blueprint

[arch-blueprint](https://github.com/nkhitrov/arch-blueprint) генерирует PlantUML-диаграмму
зависимостей Python-проекта. Сгенерированный текст передаётся в поле `plantuml` запроса `POST /arch/analyze`.

```bash
# 1. Генерация диаграммы (arch-blueprint)
arch-blueprint --output diagram.puml ./my_project

# 2. Передача в arch_service
curl -X POST http://localhost:8006/arch/analyze \
  -H "Content-Type: application/json" \
  -d "{\"project_id\": \"my-project-id\", \"plantuml\": $(cat diagram.puml | jq -Rs .)}"
```
