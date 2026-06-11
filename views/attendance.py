"""
views/attendance.py

Attendance tracking endpoints for the Forepay Construction Payroll App.

Endpoints:
  POST  /attendance/                        – mark attendance for a worker
  GET   /attendance/                        – list all attendance records (foreman's workers)
  GET   /attendance/today                   – today's attendance summary
  GET   /attendance/worker/{worker_id}      – all attendance for a specific worker
  PUT   /attendance/{record_id}             – correct an attendance record
  DELETE /attendance/{record_id}            – delete an attendance record
  GET   /attendance/report/daily            – daily attendance report
  GET   /attendance/report/summary          – overall wage summary for all workers
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from database import get_db
from models import Attendance, Worker
from views.auth import get_current_foreman

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceCreate(BaseModel):
    worker_id: int
    date: date
    status: str                          # present / half / absent
    overtime_hours: Optional[float] = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "worker_id": 1,
                "date": "2025-06-08",
                "status": "present",
                "overtime_hours": 2.0
            }
        }


class AttendanceBulkCreate(BaseModel):
    """Mark attendance for multiple workers at once (same date)."""
    date: date
    records: list[dict]   # [{"worker_id": 1, "status": "present", "overtime_hours": 0}, ...]


class AttendanceUpdate(BaseModel):
    status: Optional[str] = None
    overtime_hours: Optional[float] = None


class AttendanceResponse(BaseModel):
    id: int
    worker_id: int
    worker_name: str
    date: date
    status: str
    overtime_hours: float
    amount_earned: float

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

VALID_STATUSES = {"present", "half", "absent"}


def calculate_daily_earning(worker: Worker, att_status: str, overtime_hours: float) -> float:
    """
    Calculate how much a worker earned for a single day.

    - present  → full wage
    - half     → 50% wage
    - absent   → 0
    - overtime → 1.5x hourly rate for extra hours
    """
    if att_status == "absent":
        return 0.0

    if worker.wage_type == "daily":
        base = worker.wage_amount if att_status == "present" else worker.wage_amount * 0.5
        hourly_rate = worker.wage_amount / 8
    else:
        # hourly
        hours = 8 if att_status == "present" else 4
        base = hours * worker.wage_amount
        hourly_rate = worker.wage_amount

    overtime_pay = overtime_hours * hourly_rate * 1.5
    return round(base + overtime_pay, 2)


def get_worker_or_404(worker_id: int, foreman_id: int, db: Session) -> Worker:
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.foreman_id == foreman_id,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found.")
    return worker


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def mark_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Mark attendance for a single worker on a specific date.

    - Prevents duplicate records for the same worker + date.
    - Auto-calculates amount_earned based on wage_type and overtime.
    """
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status must be 'present', 'half', or 'absent'."
        )
    if payload.overtime_hours < 0:
        raise HTTPException(status_code=400, detail="overtime_hours cannot be negative.")

    worker = get_worker_or_404(payload.worker_id, current_user.id, db)

    # Prevent duplicate entry
    existing = db.query(Attendance).filter(
        Attendance.worker_id == payload.worker_id,
        Attendance.date == payload.date,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Attendance for {worker.full_name} on {payload.date} already recorded. Use PUT to update."
        )

    amount_earned = calculate_daily_earning(worker, payload.status, payload.overtime_hours)

    record = Attendance(
        worker_id=payload.worker_id,
        date=payload.date,
        status=payload.status,
        overtime_hours=payload.overtime_hours,
        amount_earned=amount_earned,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": f"Attendance recorded for {worker.full_name}.",
        "record": {
            "id": record.id,
            "worker_id": record.worker_id,
            "worker_name": worker.full_name,
            "date": str(record.date),
            "status": record.status,
            "overtime_hours": record.overtime_hours,
            "amount_earned": record.amount_earned,
        },
    }


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def mark_attendance_bulk(
    payload: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Mark attendance for multiple workers on the same date in one request.

    Body example:
    {
      "date": "2025-06-08",
      "records": [
        {"worker_id": 1, "status": "present", "overtime_hours": 0},
        {"worker_id": 2, "status": "half",    "overtime_hours": 0},
        {"worker_id": 3, "status": "absent",  "overtime_hours": 0}
      ]
    }
    """
    created = []
    skipped = []

    for item in payload.records:
        worker_id = item.get("worker_id")
        att_status = item.get("status", "absent")
        overtime = float(item.get("overtime_hours", 0))

        if att_status not in VALID_STATUSES:
            skipped.append({"worker_id": worker_id, "reason": "Invalid status"})
            continue

        worker = db.query(Worker).filter(
            Worker.id == worker_id,
            Worker.foreman_id == current_user.id,
        ).first()
        if not worker:
            skipped.append({"worker_id": worker_id, "reason": "Worker not found"})
            continue

        # Skip duplicates
        existing = db.query(Attendance).filter(
            Attendance.worker_id == worker_id,
            Attendance.date == payload.date,
        ).first()
        if existing:
            skipped.append({"worker_id": worker_id, "reason": "Already recorded"})
            continue

        amount_earned = calculate_daily_earning(worker, att_status, overtime)
        record = Attendance(
            worker_id=worker_id,
            date=payload.date,
            status=att_status,
            overtime_hours=overtime,
            amount_earned=amount_earned,
        )
        db.add(record)
        created.append(worker.full_name)

    db.commit()
    return {
        "message": f"Bulk attendance recorded for {payload.date}.",
        "recorded": created,
        "skipped": skipped,
    }


@router.get("/today")
def today_attendance(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Get today's attendance summary across all workers for this foreman.
    Shows present, half, absent counts and total wages for the day.
    """
    today = date.today()

    # Get all worker IDs for this foreman
    worker_ids = [w.id for w in db.query(Worker).filter(
        Worker.foreman_id == current_user.id,
        Worker.status == "active",
    ).all()]

    records = db.query(Attendance).filter(
        Attendance.date == today,
        Attendance.worker_id.in_(worker_ids),
    ).all()

    # Enrich with worker names
    workers_map = {
        w.id: w for w in db.query(Worker).filter(Worker.id.in_(worker_ids)).all()
    }

    detailed = [
        {
            "worker_id": r.worker_id,
            "worker_name": workers_map[r.worker_id].full_name,
            "role": workers_map[r.worker_id].role,
            "status": r.status,
            "overtime_hours": r.overtime_hours,
            "amount_earned": r.amount_earned,
        }
        for r in records
    ]

    return {
        "date": str(today),
        "total_active_workers": len(worker_ids),
        "recorded": len(records),
        "not_yet_recorded": len(worker_ids) - len(records),
        "summary": {
            "present": sum(1 for r in records if r.status == "present"),
            "half": sum(1 for r in records if r.status == "half"),
            "absent": sum(1 for r in records if r.status == "absent"),
            "total_wages_today": round(sum(r.amount_earned for r in records), 2),
        },
        "records": detailed,
    }


@router.get("/worker/{worker_id}")
def worker_attendance(
    worker_id: int,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Get all attendance records for a specific worker.

    Optional filters:
      - ?from_date=2025-06-01
      - ?to_date=2025-06-30
    """
    worker = get_worker_or_404(worker_id, current_user.id, db)

    query = db.query(Attendance).filter(Attendance.worker_id == worker_id)
    if from_date:
        query = query.filter(Attendance.date >= from_date)
    if to_date:
        query = query.filter(Attendance.date <= to_date)

    records = query.order_by(Attendance.date.desc()).all()

    return {
        "worker": {
            "id": worker.id,
            "full_name": worker.full_name,
            "role": worker.role,
        },
        "total_records": len(records),
        "records": [
            {
                "id": r.id,
                "date": str(r.date),
                "status": r.status,
                "overtime_hours": r.overtime_hours,
                "amount_earned": r.amount_earned,
            }
            for r in records
        ],
    }


@router.get("/")
def list_attendance(
    target_date: Optional[date] = Query(None, description="Filter by a specific date"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    List all attendance records for the foreman's workers.
    Optionally filter by a specific date: ?target_date=2025-06-08
    """
    worker_ids = [w.id for w in db.query(Worker).filter(
        Worker.foreman_id == current_user.id
    ).all()]

    query = db.query(Attendance).filter(Attendance.worker_id.in_(worker_ids))
    if target_date:
        query = query.filter(Attendance.date == target_date)

    records = query.order_by(Attendance.date.desc()).all()

    workers_map = {
        w.id: w for w in db.query(Worker).filter(Worker.id.in_(worker_ids)).all()
    }

    return [
        {
            "id": r.id,
            "worker_id": r.worker_id,
            "worker_name": workers_map[r.worker_id].full_name,
            "date": str(r.date),
            "status": r.status,
            "overtime_hours": r.overtime_hours,
            "amount_earned": r.amount_earned,
        }
        for r in records
    ]


@router.put("/{record_id}")
def update_attendance(
    record_id: int,
    payload: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Correct an existing attendance record (status or overtime hours).
    Re-calculates amount_earned automatically after the update.
    """
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")

    worker = get_worker_or_404(record.worker_id, current_user.id, db)

    if payload.status:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="status must be 'present', 'half', or 'absent'.")
        record.status = payload.status

    if payload.overtime_hours is not None:
        if payload.overtime_hours < 0:
            raise HTTPException(status_code=400, detail="overtime_hours cannot be negative.")
        record.overtime_hours = payload.overtime_hours

    # Recalculate earnings
    record.amount_earned = calculate_daily_earning(worker, record.status, record.overtime_hours)
    db.commit()
    db.refresh(record)

    return {
        "message": "Attendance record updated.",
        "record": {
            "id": record.id,
            "worker_name": worker.full_name,
            "date": str(record.date),
            "status": record.status,
            "overtime_hours": record.overtime_hours,
            "amount_earned": record.amount_earned,
        },
    }


@router.delete("/{record_id}")
def delete_attendance(
    record_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """Delete an attendance record (e.g. entered by mistake)."""
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")

    # Confirm it belongs to this foreman's worker
    get_worker_or_404(record.worker_id, current_user.id, db)

    db.delete(record)
    db.commit()
    return {"message": "Attendance record deleted."}


@router.get("/report/summary")
def wage_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_foreman),
):
    """
    Overall wage summary for ALL workers under this foreman.

    Returns each worker's:
      - Days present / half / absent
      - Total overtime hours
      - Total wages owed
    """
    workers = db.query(Worker).filter(Worker.foreman_id == current_user.id).all()

    result = []
    grand_total = 0.0

    for worker in workers:
        records = db.query(Attendance).filter(Attendance.worker_id == worker.id).all()

        days_present = sum(1 for r in records if r.status == "present")
        days_half = sum(1 for r in records if r.status == "half")
        days_absent = sum(1 for r in records if r.status == "absent")
        overtime = sum(r.overtime_hours or 0 for r in records)
        total_wages = sum(r.amount_earned or 0 for r in records)
        grand_total += total_wages

        result.append({
            "worker_id": worker.id,
            "full_name": worker.full_name,
            "role": worker.role,
            "wage_type": worker.wage_type,
            "wage_amount": worker.wage_amount,
            "days_present": days_present,
            "days_half": days_half,
            "days_absent": days_absent,
            "overtime_hours": overtime,
            "total_wages_owed": round(total_wages, 2),
            "currency": "KES",
        })

    return {
        "total_workers": len(workers),
        "grand_total_wages_owed": round(grand_total, 2),
        "currency": "KES",
        "workers": result,
    }