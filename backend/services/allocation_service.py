from sqlalchemy.orm import Session

from core.synchronization import allocation_lock
from core.transaction_manager import transaction
from repositories.allocation_repository import AllocationRepository
from services.triage_service import TriageService


class AllocationService:
    """
    Handles the business logic for shelter allocation.

    Responsibilities:
    - Calculate evacuee priority
    - Validate existing allocations
    - Coordinate allocation transactions
    - Create allocation records
    - Create audit logs
    - Retrieve allocation information
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = AllocationRepository()

    def calculate_priority(
        self,
        medical_condition: str | None,
        vulnerability_status: str | None,
        age: int | None = None
    ) -> int:
        """
        Calculate the priority score of an evacuee.
        """

        return TriageService.calculate_priority(
            medical_condition=medical_condition,
            vulnerability_status=vulnerability_status,
            age=age
        )

    def allocate(
        self,
        evacuee_id: int,
        shelter_id: int,
        priority_score: int,
        allocated_by: int | None = None
    ):
        """
        Perform an allocation.

        Shelter capacity validation and row-level locking
        will be integrated after the shared shelters table
        is finalized.
        """

        with allocation_lock.acquire():

            with transaction(self.db):

                # Check whether the evacuee already
                # has an active allocation.
                existing = self.repository.get_active_by_evacuee(
                    self.db,
                    evacuee_id
                )

                if existing:
                    raise ValueError(
                        "Evacuee already has an active allocation."
                    )

                # Create allocation record.
                allocation = self.repository.create_allocation(
                    db=self.db,
                    evacuee_id=evacuee_id,
                    shelter_id=shelter_id,
                    priority_score=priority_score,
                    allocated_by=allocated_by
                )

                # Create audit log.
                self.repository.create_log(
                    db=self.db,
                    allocation_id=allocation.allocation_id,
                    evacuee_id=evacuee_id,
                    shelter_id=shelter_id,
                    action="ALLOCATED",
                    performed_by=allocated_by,
                    remarks="Allocation created successfully."
                )

                return allocation

    def get_allocation(
        self,
        allocation_id: int
    ):
        """
        Get an allocation by its ID.
        """

        return self.repository.get_by_id(
            self.db,
            allocation_id
        )