"""Парсер PlantUML и вычислитель метрик Coupling / Cohesion.

Ожидаемый формат — диаграмма компонентов/пакетов, сгенерированная arch-blueprint:

  @startuml
  [ComponentA] --> [ComponentB]
  [ComponentA] --> [ComponentC]
  package "pkg" {
    [ComponentB]
    [ComponentC]
  }
  @enduml

Поддерживаются стрелки: -->, .>, <|--
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


def _extract_components(lines: list[str]) -> dict[str, ComponentData]:
    """Находит все компоненты/модули в PlantUML."""
    components: dict[str, ComponentData] = {}

    # Паттерны объявления: [Name], component Name, rectangle Name
    decl_re = re.compile(
        r"(?:^|\s)\[([\w.\-/: ]+)\]"
        r'|(?:^|\s)(?:component|rectangle|node|database|cloud)\s+"?([\w.\-/: ]+)"?'
    )
    # Паттерны зависимостей: --> , ..> , .> , <|--, -->
    dep_re = re.compile(
        r"\[([\w.\-/: ]+)\]\s*(?:-->|\.\.>|\->|\.<|--|<\|--|-\|>)\s*\[([\w.\-/: ]+)\]"
        r"|([\w.\-/: ]+)\s*(?:-->|\.\.>|\->|--)\s*([\w.\-/: ]+)"
    )

    current_pkg = ""
    pkg_stack: list[str] = []

    for raw in lines:
        line = raw.strip()

        # Вход в package/namespace
        pkg_match = re.match(
            r'(?:package|namespace|folder)\s+["\']?([\w.\-/ ]+)["\']?\s*\{', line
        )
        if pkg_match:
            pkg_name = pkg_match.group(1).strip()
            pkg_stack.append(pkg_name)
            current_pkg = pkg_name
            continue

        # Выход из блока
        if line == "}" and pkg_stack:
            pkg_stack.pop()
            current_pkg = pkg_stack[-1] if pkg_stack else ""
            continue

        # Объявление компонента
        for m in decl_re.finditer(line):
            name = (m.group(1) or m.group(2) or "").strip()
            if name and name not in ("@startuml", "@enduml"):
                if name not in components:
                    components[name] = ComponentData(name=name, package=current_pkg)
                elif not components[name].package:
                    components[name].package = current_pkg

        # Зависимости
        dm = dep_re.search(line)
        if dm:
            src = (dm.group(1) or dm.group(3) or "").strip()
            dst = (dm.group(2) or dm.group(4) or "").strip()
            if src and dst and src != dst:
                if src not in components:
                    components[src] = ComponentData(name=src, package=current_pkg)
                if dst not in components:
                    components[dst] = ComponentData(name=dst, package=current_pkg)
                components[src].efferent.add(dst)
                components[dst].afferent.add(src)

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

        # Cohesion: доля зависимостей внутри того же пакета
        neighbors = comp.afferent | comp.efferent
        if neighbors and comp.package:
            same_pkg = sum(
                1
                for nb in neighbors
                if components.get(nb, ComponentData(name=nb)).package == comp.package
            )
            cohesion_score = same_pkg / len(neighbors)
        elif not comp.package:
            # Без пакета — когезия не определена, считаем нейтральной (0.5)
            cohesion_score = 0.5
        else:
            cohesion_score = 1.0  # нет зависимостей — изолирован (хорошая когезия)

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

    # 1. God-компонент: очень высокий coupling
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

    # 2. Нестабильные абстрактные зависимости (принцип стабильных зависимостей)
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

    # 3. Низкая когезия
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

    # 4. Циклические зависимости (простая попарная проверка)
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
                            f"'{comp.name}' и '{dep}'. Циклы нарушают принцип ацикличности зависимостей."
                        ),
                    )
                )

    # 5. Общий балл: если средний coupling слишком высок
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
                        "Архитектура сильно связана — рассмотрите введение слоёв абстракций "
                        "или паттернов (Mediator, Façade, Dependency Inversion)."
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

    # Итоговый балл здоровья архитектуры [0..100]
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
