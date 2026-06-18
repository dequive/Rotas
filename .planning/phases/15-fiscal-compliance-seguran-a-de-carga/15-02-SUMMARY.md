---
plan: "02"
phase: 15-fiscal-compliance-seguran-a-de-carga
status: complete
wave: 2
---

# Plan 15-02 Summary — LOAD-01 + LOAD-02 Cargo Safety Guards

## What was done

**LOAD-01 — Payload weight guard:**
- `trips/schemas.py`: Added `cargo_weight`, `payload_override_reason`, `is_hazmat`, `hazmat_class`, `un_number`, `hazmat_label` to `TripCreate`
- `trips/service.py`: Guard in `create_trip()` raises `ApiError("payload_exceeded", 409)` when `cargo_weight > vehicle.max_payload_kg` and no override reason provided
- `trips/service.py`: Same guard in `start_trip()` — double-checked at trip start
- Admin bypass: `payload_override_reason` field skips the guard

**LOAD-02 — Hazmat declaration guard:**
- `cargo/service.py`: `create_load_permit()` raises `ApiError("hazmat_declaration_required", 422)` if `trip.is_hazmat=True` and `hazmat_class` is missing/blank
- `trips/service.py`: `start_trip()` creates a `hazmat_active` alert after commit (best-effort, wrapped in try/except — trip start never fails due to alert error)

**Vehicles serialization:**
- `vehicles/service.py`: `serialize_vehicle()` now includes `max_payload_kg`

## Files modified
- `backend/app/modules/trips/service.py`
- `backend/app/modules/trips/schemas.py`
- `backend/app/modules/vehicles/service.py`
- `backend/app/modules/cargo/service.py`
