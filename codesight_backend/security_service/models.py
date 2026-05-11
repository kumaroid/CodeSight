import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class SecurityScan(Base):
    """Запуск проверки безопасности для конкретного проекта."""

    __tablename__ = "security_scans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", name="security_status_enum"),
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

    findings: Mapped[list["SecurityFinding"]] = relationship(
        "SecurityFinding", back_populates="scan", cascade="all, delete-orphan"
    )


class SecurityFinding(Base):
    """Уязвимость, найденная при проверке безопасности."""

    __tablename__ = "security_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # OWASP категория (A01..A10)
    owasp_category: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    owasp_title: Mapped[str] = mapped_column(String(200), nullable=False)

    checker: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # bandit, semgrep, regex
    severity: Mapped[str] = mapped_column(
        Enum("critical", "high", "medium", "low", "info", name="finding_severity_enum"),
        nullable=False,
        default="medium",
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    cwe: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # CWE-89, CWE-78 ...

    scan: Mapped["SecurityScan"] = relationship(
        "SecurityScan", back_populates="findings"
    )
