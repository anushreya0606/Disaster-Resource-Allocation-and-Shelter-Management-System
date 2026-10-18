from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Evacuee(Base):
    __tablename__ = "evacuees"

    evacuee_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    age: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    gender: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    medical_condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    vulnerability_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    priority_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "WAITING",
            "ALLOCATED",
            "SAFE",
            "RELEASED"
        ),
        nullable=False,
        default="WAITING"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )