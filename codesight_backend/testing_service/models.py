import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TestRun(Base):
    """Запуск тестирования для конкретного проекта."""

    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", name="test_run_status_enum"),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Метрики покрытия ---
    coverage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    lines_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lines_covered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lines_missing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branches_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branches_covered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_coverage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Метрики прогона тестов ---
    tests_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_error: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_skipped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    file_coverages: Mapped[list["FileCoverage"]] = relationship(
        "FileCoverage", back_populates="run", cascade="all, delete-orphan"
    )
    test_results: Mapped[list["TestResult"]] = relationship(
        "TestResult", back_populates="run", cascade="all, delete-orphan"
    )


class FileCoverage(Base):
    """Покрытие одного файла в рамках запуска."""

    __tablename__ = "file_coverages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    lines_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_covered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_missing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    missing_lines: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON-список номеров строк

    run: Mapped["TestRun"] = relationship("TestRun", back_populates="file_coverages")


class TestResult(Base):
    """Результат одного теста."""

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)  # pytest node id
    outcome: Mapped[str] = mapped_column(
        Enum("passed", "failed", "error", "skipped", name="test_outcome_enum"),
        nullable=False,
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Краткое сообщение об ошибке (если failed/error)
    longrepr: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["TestRun"] = relationship("TestRun", back_populates="test_results")
