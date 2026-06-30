"""
DigitalAttendanceSystem — FastAPI Backend
Deploy to Render or Railway. Stores attendance data per office.
"""

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

app = FastAPI(title="Attendance Dashboard API", version="1.0.0")

# ─────────────────────────────────────────────
# CORS — allow GitHub Pages frontend
# ─────────────────────────────────────────────
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# API Key registry
# Each office has a unique hashed key stored in env vars.
# Format: OFFICE_KEY_<OFFICE_SLUG>=<sha256 of the actual key>
# e.g. OFFICE_KEY_PROVOST=abc123hash...
# ─────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "changeme123")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/attendance_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def resolve_office_from_key(raw_key: str) -> Optional[str]:
    """Return office slug if the key matches any registered office key."""
    if not raw_key:
        return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    for env_name, env_val in os.environ.items():
        if env_name.startswith("OFFICE_KEY_") and env_val == key_hash:
            return env_name.replace("OFFICE_KEY_", "").lower()
    return None


def require_office_key(raw_key: str = Security(api_key_header)):
    office = resolve_office_from_key(raw_key)
    if not office:
        raise HTTPException(status_code=403, detail="Invalid or missing API key.")
    return office


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class AttendancePayload(BaseModel):
    cleaned_daily: dict        # DataFrame as JSON (orient='split')
    cleaned_totals: dict
    cleaned_months: dict
    cleaned_monthly: dict


class LoginRequest(BaseModel):
    password: str


# ─────────────────────────────────────────────
# Storage helpers
# ─────────────────────────────────────────────
def office_file(slug: str) -> Path:
    return DATA_DIR / f"{slug}.json"


def load_office(slug: str) -> Optional[dict]:
    f = office_file(slug)
    if f.exists():
        return json.loads(f.read_text())
    return None


def save_office(slug: str, data: dict):
    office_file(slug).write_text(json.dumps(data, ensure_ascii=False))


def list_offices() -> list[dict]:
    offices = []
    for env_name in os.environ:
        if env_name.startswith("OFFICE_KEY_"):
            slug = env_name.replace("OFFICE_KEY_", "").lower()
            record = load_office(slug)
            offices.append({
                "slug": slug,
                "name": slug.replace("_", " ").title(),
                "last_updated": record.get("last_updated") if record else None,
                "has_data": record is not None,
            })
    return sorted(offices, key=lambda x: x["name"])


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "Attendance Dashboard API"}


@app.get("/debug/office-keys")
def debug_office_keys():
    """TEMPORARY — lists registered office key env var names only (not values)."""
    names = [k for k in os.environ if k.startswith("OFFICE_KEY_")]
    return {"registered_office_key_vars": names}


@app.post("/auth/login")
def login(req: LoginRequest):
    if req.password != VIEWER_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"authenticated": True}


@app.get("/offices")
def get_offices():
    return list_offices()


@app.post("/upload/{office_slug}")
def upload(office_slug: str, payload: AttendancePayload, office: str = Depends(require_office_key)):
    if office != office_slug:
        raise HTTPException(status_code=403, detail="API key does not match the target office.")
    record = {
        "slug": office_slug,
        "name": office_slug.replace("_", " ").title(),
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "cleaned_daily": payload.cleaned_daily,
        "cleaned_totals": payload.cleaned_totals,
        "cleaned_months": payload.cleaned_months,
        "cleaned_monthly": payload.cleaned_monthly,
    }
    save_office(office_slug, record)
    return {"status": "saved", "office": office_slug, "timestamp": record["last_updated"]}


@app.get("/offices/{office_slug}")
def get_office_data(office_slug: str):
    record = load_office(office_slug)
    if not record:
        raise HTTPException(status_code=404, detail=f"No data found for office: {office_slug}")
    return record


@app.delete("/offices/{office_slug}")
def clear_office(office_slug: str, office: str = Depends(require_office_key)):
    if office != office_slug:
        raise HTTPException(status_code=403, detail="API key does not match.")
    f = office_file(office_slug)
    if f.exists():
        f.unlink()
    return {"status": "cleared", "office": office_slug}
