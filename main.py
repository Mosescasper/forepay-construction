"""
main.py

Entry point for the Forepay Construction Payroll API.

Run with:
    uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from views.auth import router as auth_router
from views.workers import router as workers_router
from views.attendance import router as attendance_router

# ── Create all DB tables on startup ──────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Forepay API",
    description="Construction Workforce & Payroll Management for Site Foremen",
    version="1.0.0",
)

# ── CORS (allow React frontend to talk to the API) ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(workers_router)
app.include_router(attendance_router)

# Coming soon:
# from views.payments import router as payments_router
# app.include_router(payments_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Forepay API is running."}