from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Allocation(Base):
    __tablename__ = "allocations"

    allocation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    evacuee_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    shelter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    priority_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "ALLOCATED",
            "RELEASED",
            "CANCELLED"
        ),
        nullable=False,
        default="ALLOCATED"
    )

    allocated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    allocated_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )