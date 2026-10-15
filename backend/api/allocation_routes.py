from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.allocation_service import AllocationService


router = APIRouter(
    prefix="/api/allocations",
    tags=["Allocations"]
)


class AllocationRequest(BaseModel):
    evacuee_id: int
    shelter_id: int
    priority_score: int
    allocated_by: int | None = None


@router.post("")
def create_allocation(
    request: AllocationRequest,
    db: Session = Depends(get_db)
):
    """
    Create a shelter allocation for an evacuee.
    """

    service = AllocationService(db)

    try:
        allocation = service.allocate(
            evacuee_id=request.evacuee_id,
            shelter_id=request.shelter_id,
            priority_score=request.priority_score,
            allocated_by=request.allocated_by
        )

        return {
            "message": "Allocation created successfully",
            "allocation_id": allocation.allocation_id,
            "evacuee_id": allocation.evacuee_id,
            "shelter_id": allocation.shelter_id,
            "priority_score": allocation.priority_score,
            "status": allocation.status
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Allocation failed"
        )


@router.get("/{allocation_id}")
def get_allocation(
    allocation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get an allocation by its ID.
    """

    service = AllocationService(db)

    allocation = service.get_allocation(
        allocation_id
    )

    if allocation is None:
        raise HTTPException(
            status_code=404,
            detail="Allocation not found"
        )

    return {
        "allocation_id": allocation.allocation_id,
        "evacuee_id": allocation.evacuee_id,
        "shelter_id": allocation.shelter_id,
        "priority_score": allocation.priority_score,
        "status": allocation.status,
        "allocated_at": allocation.allocated_at,
        "released_at": allocation.released_at,
        "allocated_by": allocation.allocated_by
    }