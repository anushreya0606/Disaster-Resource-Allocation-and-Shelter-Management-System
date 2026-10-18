from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
class Resource(Base):
    __tablename__ = "resources"

    resource_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    shelter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    minimum_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
