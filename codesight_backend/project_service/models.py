import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # «zip» | «git»
    source_type: Mapped[str] = mapped_column(
        Enum("zip", "git", name="source_type_enum"),
        nullable=False,
    )

    # URL репозитория (только для source_type='git')
    repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Путь к распакованным файлам на сервере
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # «pending» | «ready» | «error»
    status: Mapped[str] = mapped_column(
        Enum("pending", "ready", "error", name="project_status_enum"),
        nullable=False,
        default="pending",
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
