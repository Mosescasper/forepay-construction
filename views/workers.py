"""
views/workers.py

Worker management endpoints for the Forepay Construction Payroll App.

Endpoints:
  POST   /workers/              – add a new worker (foreman only)
  GET    /workers/              – list all workers for the logged-in foreman
  GET    /workers/{worker_id}   – get a single worker's details
  PUT    /workers/{worker_id}   – update worker info
  DELETE /workers/{worker_id}   – remove a worker
  GET    /workers/{worker_id}/summary – wage & attendance summary for a worker
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import get_db
from models import Worker, Attendance
from views.auth import get_current_foreman

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/workers", tags=["Workers"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class WorkerCreate(BaseModel):
    full_name: str
    phone: str
    role: str                        # Mason, Carpenter, Electrician, Plumber, General Laborer
    wage_type: str                   # "daily" or "hourly"
    wage_amount: float               # amount per day or per hour
    status: Optional[str] = "active" # active / inactive

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Peter Mwangi",
                "phone": "0723456789",
                "role": "Mason",
                "wage_type": "daily",
                "wage_amount": 800.0,
                "status": "active"
            }
        }


class WorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    wage_type: Optional[str] = None
    wage_amount: Optional[float] = None
    status: Optional[str] = None


class WorkerResponse(BaseModel):
    id: int
    full_name: str
    phone: str
    role: str
    wage_type: str
    wage_amount: float
    status: str
    foreman_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

VALID_ROLES = {"Mason", "Carpenter", "Electrician", "Plumber", "General Laborer"}
VALID_WAGE_TYPES = {"daily", "hourly"}
VALID_STATUSES = {"active", "inactive"}


def validate_worker_fields(role: str = None, wage_type: str = None, status: str = None):
    if role and role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Choose from: {', '.join(VALID_ROLES)}"
        )
    if wage_type and wage_type not in VALID_WAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="wage_type must be 'daily' or 'hourly'."
        )
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status must be 'active' or 'inactive'."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=WorkerResponse)
def add_worker(
    payload: WorkerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Add a new worker under the logged-in foreman.

    - Validates role, wage_type, and status.
    - Prevents duplicate phone numbers per foreman.
    - Returns the created worker object.
    """
    validate_worker_fields(payload.role, payload.wage_type, payload.status)

    # Prevent duplicate phone under same foreman
    existing = db.query(Worker).filter(
        Worker.phone == payload.phone,
        Worker.foreman_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A worker with this phone number already exists under your account."
        )

    if payload.wage_amount <= 0:
        raise HTTPException(status_code=400, detail="wage_amount must be greater than 0.")

    worker = Worker(
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        wage_type=payload.wage_type,
        wage_amount=payload.wage_amount,
        status=payload.status,
        foreman_id=current_user.id,
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


@router.get("/", response_model=list[WorkerResponse])
def list_workers(
    status_filter: Optional[str] = None,
    role_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    List all workers belonging to the logged-in foreman.

    Optional query params:
      - ?status_filter=active  → filter by active/inactive
      - ?role_filter=Mason     → filter by job role
    """
    query = db.query(Worker).filter(Worker.foreman_id == current_user.id)

    if status_filter:
        query = query.filter(Worker.status == status_filter)
    if role_filter:
        query = query.filter(Worker.role == role_filter)

    return query.order_by(Worker.full_name).all()


@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Get details of a single worker by ID.
    Only the foreman who added the worker can view them.
    """
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.foreman_id == current_user.id,
    ).first()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")
    return worker


@router.put("/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Update a worker's details (partial update — only send fields to change).

    Example: change wage_amount or mark worker as inactive.
    """
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.foreman_id == current_user.id,
    ).first()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")

    validate_worker_fields(payload.role, payload.wage_type, payload.status)

    if payload.full_name is not None:
        worker.full_name = payload.full_name
    if payload.phone is not None:
        worker.phone = payload.phone
    if payload.role is not None:
        worker.role = payload.role
    if payload.wage_type is not None:
        worker.wage_type = payload.wage_type
    if payload.wage_amount is not None:
        if payload.wage_amount <= 0:
            raise HTTPException(status_code=400, detail="wage_amount must be greater than 0.")
        worker.wage_amount = payload.wage_amount
    if payload.status is not None:
        worker.status = payload.status

    db.commit()
    db.refresh(worker)
    return worker


@router.delete("/{worker_id}", status_code=status.HTTP_200_OK)
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Remove a worker from the system.

    Note: This also deletes all attendance records for this worker.
    Consider using status='inactive' instead of deleting to preserve history.
    """
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.foreman_id == current_user.id,
    ).first()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")

    db.delete(worker)
    db.commit()
    return {"message": f"Worker '{worker.full_name}' has been removed."}


@router.get("/{worker_id}/summary")
def worker_summary(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Return a wage and attendance summary for a single worker.

    Calculates:
      - Total days present / half days / absent
      - Total overtime hours
      - Total wages owed based on attendance and wage_type
    """
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.foreman_id == current_user.id,
    ).first()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")

    records = db.query(Attendance).filter(Attendance.worker_id == worker_id).all()

    days_present = sum(1 for r in records if r.status == "present")
    days_half = sum(1 for r in records if r.status == "half")
    days_absent = sum(1 for r in records if r.status == "absent")
    total_overtime_hours = sum(r.overtime_hours or 0 for r in records)

    # Wage calculation
    if worker.wage_type == "daily":
        base_wages = (days_present * worker.wage_amount) + (days_half * worker.wage_amount * 0.5)
    else:
        # hourly: assume 8 working hours per full day, 4 per half day
        base_wages = (days_present * 8 + days_half * 4) * worker.wage_amount

    overtime_pay = total_overtime_hours * (worker.wage_amount / 8) * 1.5
    total_wages = base_wages + overtime_pay

    return {
        "worker": {
            "id": worker.id,
            "full_name": worker.full_name,
            "role": worker.role,
            "wage_type": worker.wage_type,
            "wage_amount": worker.wage_amount,
        },
        "attendance": {
            "days_present": days_present,
            "days_half": days_half,
            "days_absent": days_absent,
            "total_overtime_hours": total_overtime_hours,
        },
        "wages": {
            "base_wages": round(base_wages, 2),
            "overtime_pay": round(overtime_pay, 2),
            "total_wages_owed": round(total_wages, 2),
            "currency": "KES",
        },
    }