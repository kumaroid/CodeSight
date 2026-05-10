import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ArchRun(Base):
    """Запуск архитектурного анализа PlantUML-диаграммы."""

    __tablename__ = "arch_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", name="arch_status_enum"),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    metrics: Mapped[list["ComponentMetric"]] = relationship(
        "ComponentMetric", back_populates="run", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["ArchRecommendation"]] = relationship(
        "ArchRecommendation", back_populates="run", cascade="all, delete-orphan"
    )


class ComponentMetric(Base):
    """Метрики Coupling/Cohesion для одного компонента."""

    __tablename__ = "component_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    component: Mapped[str] = mapped_column(String(255), nullable=False)

    # Coupling: Ca (afferent) — сколько компонентов зависят от этого
    ca: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Coupling: Ce (efferent) — от скольких зависит этот компонент
    ce: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Instability I = Ce / (Ca + Ce), диапазон [0, 1]
    instability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Coupling score (нормализованный): (Ca + Ce) / (N - 1), N = кол-во компонентов
    coupling_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Cohesion proxy: доля компонентов в той же «группе» (package/namespace)
    cohesion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    run: Mapped["ArchRun"] = relationship("ArchRun", back_populates="metrics")


class ArchRecommendation(Base):
    """Рекомендация по улучшению архитектуры."""

    __tablename__ = "arch_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        Enum("critical", "warning", "info", name="arch_severity_enum"),
        nullable=False,
        default="warning",
    )
    component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped["ArchRun"] = relationship("ArchRun", back_populates="recommendations")
