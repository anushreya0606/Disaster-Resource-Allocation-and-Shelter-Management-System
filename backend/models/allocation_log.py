from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AllocationLog(Base):
    __tablename__ = "allocation_logs"

    log_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    allocation_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    evacuee_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    shelter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        Enum(
            "ALLOCATED",
            "FAILED",
            "RELEASED",
            "CANCELLED"
        ),
        nullable=False
    )

    previous_occupancy: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    new_occupancy: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    performed_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    remarks: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )