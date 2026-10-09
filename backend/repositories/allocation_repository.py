from sqlalchemy import select
from sqlalchemy.orm import Session

from models.allocation import Allocation
from models.allocation_log import AllocationLog


class AllocationRepository:

    @staticmethod
    def get_by_id(
        db: Session,
        allocation_id: int
    ) -> Allocation | None:
        """
        Find an allocation by its ID.
        """

        return db.get(Allocation, allocation_id)

    @staticmethod
    def get_active_by_evacuee(
        db: Session,
        evacuee_id: int
    ) -> Allocation | None:
        """
        Find the active allocation of an evacuee.
        """

        statement = select(Allocation).where(
            Allocation.evacuee_id == evacuee_id,
            Allocation.status == "ALLOCATED"
        )

        return db.scalar(statement)

    @staticmethod
    def create_allocation(
        db: Session,
        evacuee_id: int,
        shelter_id: int,
        priority_score: int,
        allocated_by: int | None = None
    ) -> Allocation:
        """
        Create a new allocation record.
        """

        allocation = Allocation(
            evacuee_id=evacuee_id,
            shelter_id=shelter_id,
            priority_score=priority_score,
            status="ALLOCATED",
            allocated_by=allocated_by
        )

        db.add(allocation)
        db.flush()

        return allocation

    @staticmethod
    def create_log(
        db: Session,
        allocation_id: int,
        evacuee_id: int,
        shelter_id: int,
        action: str,
        previous_occupancy: int | None = None,
        new_occupancy: int | None = None,
        performed_by: int | None = None,
        remarks: str | None = None
    ) -> AllocationLog:
        """
        Create an audit log for an allocation operation.
        """

        log = AllocationLog(
            allocation_id=allocation_id,
            evacuee_id=evacuee_id,
            shelter_id=shelter_id,
            action=action,
            previous_occupancy=previous_occupancy,
            new_occupancy=new_occupancy,
            performed_by=performed_by,
            remarks=remarks
        )

        db.add(log)
        db.flush()

        return log