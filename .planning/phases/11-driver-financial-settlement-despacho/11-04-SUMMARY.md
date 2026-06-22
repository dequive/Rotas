---
plan: 11-04
status: done
---
# 11-04 SUMMARY — HTTP Endpoints

- `backend/app/modules/drivers/advance_router.py` — POST /trips/{trip_id}/advance (201, FLEET_WRITE, Idempotency-Key), GET /trips/{trip_id}/advance (200, FLEET_READ), DELETE /trips/{trip_id}/advance/{adv_id} (200, FLEET_WRITE), GET /advances (200, FLEET_READ)
- `backend/app/modules/drivers/settlement_router.py` — POST /trips/{trip_id}/settlement (compute), GET (get), POST /approve, POST /reject (body: {reason}), GET /pdf (application/pdf response)
- Both routers registered in `backend/app/main.py` under /api/v1 prefix
- Idempotency-Key checked on advance issue via existing idempotency middleware
- PDF endpoint returns `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": ...})`
