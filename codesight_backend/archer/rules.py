from typing import List, Dict
from .models import ArchitectureInput


def analyze_architecture(data: ArchitectureInput) -> List[Dict]:
    findings = []

    if len(data.services) == 1:
        findings.append(
            {
                "id": "single_service_core",
                "severity": "medium",
                "title": "Вся система описана как один сервис",
                "risk": "Это может указывать на скрытый монолит и затруднять масштабирование по нагрузке и командам.",
                "recommendation": "Выделить ключевые bounded contexts и разделить ответственность хотя бы на логические модули.",
            }
        )

    for svc in data.services:
        if len(svc.dependencies) >= 5:
            findings.append(
                {
                    "id": f"high_coupling_{svc.name}",
                    "severity": "high",
                    "title": f"Высокая связность сервиса {svc.name}",
                    "risk": "Сервис зависит от большого числа соседей, что повышает вероятность каскадных отказов и усложняет изменения.",
                    "recommendation": "Сократить количество синхронных зависимостей, выделить orchestration или перейти на событийное взаимодействие для части сценариев.",
                }
            )

        if svc.dependencies and not svc.protocols:
            findings.append(
                {
                    "id": f"missing_protocols_{svc.name}",
                    "severity": "medium",
                    "title": f"Не указаны протоколы взаимодействия у {svc.name}",
                    "risk": "Без явных протоколов и контрактов сложнее оценить latency, надежность и требования к совместимости.",
                    "recommendation": "Явно указать HTTP/gRPC/Kafka/RabbitMQ и формат контрактов между сервисами.",
                }
            )

        if not svc.technologies:
            findings.append(
                {
                    "id": f"missing_tech_{svc.name}",
                    "severity": "low",
                    "title": f"Не указаны технологии для {svc.name}",
                    "risk": "Сложнее оценить эксплуатационные ограничения, риски миграции и стоимость изменений.",
                    "recommendation": "Добавить стек сервиса: runtime, framework, БД, очередь, кэш.",
                }
            )

    if not data.known_issues:
        findings.append(
            {
                "id": "no_known_issues",
                "severity": "low",
                "title": "Не указаны известные проблемы",
                "risk": "Это снижает точность рекомендаций и затрудняет приоритизацию архитектурных изменений.",
                "recommendation": "Передавать observed symptoms: long latency, incidents, deploy pain, data inconsistency, scaling bottlenecks.",
            }
        )

    return findings
