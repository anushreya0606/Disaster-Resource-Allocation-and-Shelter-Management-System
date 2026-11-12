from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    shelter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    severity: Mapped[str] = mapped_column(
        Enum(
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL"
        ),
        nullable=False,
        default="MEDIUM"
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "ACTIVE",
            "RESOLVED"
        ),
        nullable=False,
        default="ACTIVE"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
