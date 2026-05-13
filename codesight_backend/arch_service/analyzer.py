"""Парсер PlantUML и вычислитель метрик Coupling / Cohesion.

Поддерживаются два диалекта диаграмм компонентов:

1. Классический PlantUML компонентов (упрощённый):

    @startuml
    package "pkg" {
      [ComponentA]
      [ComponentB]
    }
    [ComponentA] --> [ComponentB]
    @enduml

2. Вывод утилиты `arch-blueprint`, которая строит граф импортов
   Python-проекта на базе grimp:

    @startuml
    !theme amiga
    class fastapi.routing <<(M, #2ECC71)>>
    class fastapi.params <<(M, #2ECC71)>>
    fastapi.routing ---> fastapi.params
    fastapi._compat <-[#E74C3C,bold]-> fastapi.openapi
    note on link
      ...
    end note
    @enduml

«Пакет» компонента в формате arch-blueprint выводится из его dotted-имени
(`fastapi.routing` → пакет `fastapi`, `taskiq.scheduler.scheduler` →
пакет `taskiq.scheduler`). Это даёт осмысленную метрику cohesion даже без
явных package-блоков.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ComponentData:
    name: str
    package: str = ""
    afferent: set[str] = field(default_factory=set)  # Ca: кто зависит ОТ меня
    efferent: set[str] = field(default_factory=set)  # Ce: от кого завишу Я


@dataclass
class Metrics:
    component: str
    ca: int
    ce: int
    instability: float  # Ce / (Ca + Ce)
    coupling_score: float  # (Ca + Ce) / (N - 1)
    cohesion_score: float  # доля соседей в том же пакете


@dataclass
class Recommendation:
    severity: str  # critical | warning | info
    component: str | None
    rule: str
    message: str


# Пороги
_COUPLING_HIGH = 0.6
_COUPLING_CRITICAL = 0.85
_INSTABILITY_WARNING = 0.75
_COHESION_LOW = 0.3

# Идентификатор модуля/компонента: допускаем dotted-имена (a.b.c), дефисы и :
_ID = r"[A-Za-z_][\w.\-:]*"

# Объявления компонента (PlantUML):
#   [Name]
#   component "Name" | component Name
#   rectangle / node / database / cloud (...)
#   class fully.qualified.Name <<(M, #color)>>     ← arch-blueprint
_DECL_RE = re.compile(
    rf"\[({_ID})\]"
    rf'|(?:component|rectangle|node|database|cloud|interface|class)\s+"?({_ID})"?'
)

# Стрелки зависимостей. arch-blueprint использует ---> и <-[#...,...]->,
# классический PlantUML — -->, ..>, ->. Группа `arrow` ловит саму стрелку,
# чтобы можно было отличить двунаправленные (циклические) от обычных.
_DEP_RE = re.compile(
    rf"\[?(?P<src>{_ID})\]?"
    rf"\s*"
    rf"(?P<arrow>(?:<-+\[[^\]]*\]-+>|<\.+\[[^\]]*\]\.+>|<-+>|-+>|\.+>|<\|--))"
    rf"\s*"
    rf"\[?(?P<dst>{_ID})\]?"
)

# Блок «note on link / end note» — содержит произвольную прозу с подстроками,
# похожими на стрелки; пропускаем как комментарий.
_NOTE_START_RE = re.compile(r"^\s*note\b", re.IGNORECASE)
_NOTE_END_RE = re.compile(r"^\s*end\s*note\b", re.IGNORECASE)

# Игнорируемые служебные ключевые слова PlantUML на старте строки.
_SKIP_PREFIXES = (
    "@startuml",
    "@enduml",
    "!theme",
    "!include",
    "!define",
    "skinparam",
    "title",
    "left to right",
    "top to bottom",
    "hide ",
    "show ",
    "scale",
    "header",
    "footer",
    "legend",
    "endlegend",
)


def _derive_package(name: str) -> str:
    """Для arch-blueprint dotted-имени пакет = всё кроме последнего сегмента."""
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[0]


def _is_bidirectional(arrow: str) -> bool:
    return arrow.startswith("<") and arrow.endswith(">")


def _extract_components(lines: list[str]) -> dict[str, ComponentData]:
    """Находит все компоненты/модули в PlantUML и их зависимости."""
    components: dict[str, ComponentData] = {}
    pkg_stack: list[str] = []
    in_note = False

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("'"):  # пустые/комментарии
            continue

        # Многострочные блоки note — пропускаем целиком
        if in_note:
            if _NOTE_END_RE.match(line):
                in_note = False
            continue
        if _NOTE_START_RE.match(line):
            # Inline-вариант `note ... end note` в одной строке тоже корректно ловится
            if not _NOTE_END_RE.search(line):
                in_note = True
            continue

        lower = line.lower()
        if any(lower.startswith(p) for p in _SKIP_PREFIXES):
            continue

        # Вход в package/namespace/folder { ... }
        pkg_match = re.match(
            rf'(?:package|namespace|folder)\s+["\']?({_ID}|[\w./\- ]+)["\']?\s*\{{',
            line,
        )
        if pkg_match:
            pkg_stack.append(pkg_match.group(1).strip())
            continue
        if line == "}" and pkg_stack:
            pkg_stack.pop()
            continue

        current_pkg = pkg_stack[-1] if pkg_stack else ""

        # Объявление компонента
        for m in _DECL_RE.finditer(line):
            name = (m.group(1) or m.group(2) or "").strip()
            if not name or name.lower() in ("note", "on"):
                continue
            pkg = current_pkg or _derive_package(name)
            existing = components.get(name)
            if existing is None:
                components[name] = ComponentData(name=name, package=pkg)
            elif not existing.package and pkg:
                existing.package = pkg

        # Зависимости (может быть несколько в одной строке).
        for dm in _DEP_RE.finditer(line):
            src = dm.group("src").strip()
            dst = dm.group("dst").strip()
            arrow = dm.group("arrow") or "-->"
            # Защита от ложных срабатываний на ключевых словах.
            if src.lower() in ("class", "package", "note") or dst.lower() in (
                "class",
                "package",
                "note",
            ):
                continue
            if not src or not dst or src == dst:
                continue

            for comp_name in (src, dst):
                if comp_name not in components:
                    components[comp_name] = ComponentData(
                        name=comp_name,
                        package=current_pkg or _derive_package(comp_name),
                    )

            components[src].efferent.add(dst)
            components[dst].afferent.add(src)

            if _is_bidirectional(arrow):
                # Двунаправленная стрелка = цикл: добавляем обратную дугу тоже.
                components[dst].efferent.add(src)
                components[src].afferent.add(dst)

    return components


def _compute_metrics(components: dict[str, ComponentData]) -> list[Metrics]:
    n = len(components)
    denominator = max(n - 1, 1)
    result = []

    for comp in components.values():
        ca = len(comp.afferent)
        ce = len(comp.efferent)
        total = ca + ce
        instability = ce / total if total > 0 else 0.0
        coupling_score = total / denominator

        neighbors = comp.afferent | comp.efferent
        if neighbors and comp.package:
            same_pkg = sum(
                1
                for nb in neighbors
                if components.get(nb, ComponentData(name=nb)).package == comp.package
            )
            cohesion_score = same_pkg / len(neighbors)
        elif not comp.package:
            # Без пакета (плоский corner case) — нейтральная оценка.
            cohesion_score = 0.5
        else:
            cohesion_score = 1.0

        result.append(
            Metrics(
                component=comp.name,
                ca=ca,
                ce=ce,
                instability=round(instability, 4),
                coupling_score=round(min(coupling_score, 1.0), 4),
                cohesion_score=round(cohesion_score, 4),
            )
        )

    return result


def _generate_recommendations(
    metrics: list[Metrics],
    components: dict[str, ComponentData],
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    n = len(components)

    for m in metrics:
        if m.coupling_score >= _COUPLING_CRITICAL:
            recs.append(
                Recommendation(
                    severity="critical",
                    component=m.component,
                    rule="GOD_COMPONENT",
                    message=(
                        f"Компонент '{m.component}' имеет coupling_score={m.coupling_score:.2f} "
                        f"(Ca={m.ca}, Ce={m.ce}). Рекомендуется разбить на более мелкие части."
                    ),
                )
            )
        elif m.coupling_score >= _COUPLING_HIGH:
            recs.append(
                Recommendation(
                    severity="warning",
                    component=m.component,
                    rule="HIGH_COUPLING",
                    message=(
                        f"Компонент '{m.component}' имеет высокую связанность: "
                        f"coupling_score={m.coupling_score:.2f} (Ca={m.ca}, Ce={m.ce})."
                    ),
                )
            )

    for m in metrics:
        if m.instability >= _INSTABILITY_WARNING and m.ca > 0:
            recs.append(
                Recommendation(
                    severity="warning",
                    component=m.component,
                    rule="UNSTABLE_DEPENDENCY",
                    message=(
                        f"Компонент '{m.component}' нестабилен (I={m.instability:.2f}), "
                        f"но на него зависят {m.ca} других компонент(а). "
                        "Стабильные компоненты не должны зависеть от нестабильных."
                    ),
                )
            )

    for m in metrics:
        if m.cohesion_score < _COHESION_LOW and (m.ca + m.ce) > 1:
            recs.append(
                Recommendation(
                    severity="warning",
                    component=m.component,
                    rule="LOW_COHESION",
                    message=(
                        f"Компонент '{m.component}' имеет низкую когезию: "
                        f"cohesion_score={m.cohesion_score:.2f}. "
                        "Большинство зависимостей выходят за пределы пакета."
                    ),
                )
            )

    comp_map = {c.name: c for c in components.values()}
    visited_pairs: set[frozenset[str]] = set()
    for comp in components.values():
        for dep in comp.efferent:
            pair = frozenset([comp.name, dep])
            if pair in visited_pairs:
                continue
            dep_data = comp_map.get(dep)
            if dep_data and comp.name in dep_data.efferent:
                visited_pairs.add(pair)
                recs.append(
                    Recommendation(
                        severity="critical",
                        component=comp.name,
                        rule="CIRCULAR_DEPENDENCY",
                        message=(
                            f"Обнаружена циклическая зависимость между "
                            f"'{comp.name}' и '{dep}'. Циклы нарушают принцип "
                            "ацикличности зависимостей."
                        ),
                    )
                )

    if n > 1:
        avg_coupling = sum(m.coupling_score for m in metrics) / n
        if avg_coupling > _COUPLING_HIGH:
            recs.append(
                Recommendation(
                    severity="critical",
                    component=None,
                    rule="GLOBAL_HIGH_COUPLING",
                    message=(
                        f"Средний coupling по всему проекту: {avg_coupling:.2f}. "
                        "Архитектура сильно связана — рассмотрите введение слоёв "
                        "абстракций или паттернов (Mediator, Façade, Dependency Inversion)."
                    ),
                )
            )

    if not recs:
        recs.append(
            Recommendation(
                severity="info",
                component=None,
                rule="ARCHITECTURE_OK",
                message="Метрики в норме. Явных архитектурных нарушений не обнаружено.",
            )
        )

    return recs


def analyze_plantuml(
    plantuml_text: str,
) -> tuple[list[Metrics], list[Recommendation], dict]:
    """Основная точка входа. Возвращает (metrics, recommendations, summary)."""
    lines = plantuml_text.splitlines()
    components = _extract_components(lines)

    if not components:
        return [], [], {"error": "Компоненты в диаграмме не найдены"}

    metrics = _compute_metrics(components)
    recommendations = _generate_recommendations(metrics, components)

    n = len(components)
    avg_coupling = sum(m.coupling_score for m in metrics) / n if n else 0
    avg_cohesion = sum(m.cohesion_score for m in metrics) / n if n else 0
    avg_instability = sum(m.instability for m in metrics) / n if n else 0

    critical_count = sum(1 for r in recommendations if r.severity == "critical")
    warning_count = sum(1 for r in recommendations if r.severity == "warning")

    health = max(0, 100 - critical_count * 20 - warning_count * 5)

    summary = {
        "components_count": n,
        "avg_coupling": round(avg_coupling, 4),
        "avg_cohesion": round(avg_cohesion, 4),
        "avg_instability": round(avg_instability, 4),
        "critical_issues": critical_count,
        "warning_issues": warning_count,
        "architecture_health_score": health,
    }

    return metrics, recommendations, summary
