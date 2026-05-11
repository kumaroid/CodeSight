import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AnalysisRun(Base):
    """Запуск анализа для конкретного проекта."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", name="analysis_status_enum"),
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

    issues: Mapped[list["Issue"]] = relationship(
        "Issue", back_populates="run", cascade="all, delete-orphan"
    )


class Issue(Base):
    """Отдельная проблема, найденная при статическом анализе."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool: Mapped[str] = mapped_column(String(50), nullable=False)  # ruff, bandit, mypy
    severity: Mapped[str] = mapped_column(
        Enum("error", "warning", "info", name="issue_severity_enum"),
        nullable=False,
        default="warning",
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # E501, B101 ...
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped["AnalysisRun"] = relationship("AnalysisRun", back_populates="issues")
