"""Reusable OpenAPI response contracts for non-JSON payloads.

FastAPI cannot infer a schema for endpoints that stream bytes (`Response`,
`FileResponse`), so the generated contract would expose an empty `2xx` schema.
The frontend contract auditor (`apps/manager/scripts/verify-api-contracts.mjs`)
rejects empty success schemas, so binary endpoints must declare their media type
explicitly through these helpers.
"""

from __future__ import annotations

from typing import Any


def binary_response(media_type: str, description: str) -> dict[int | str, dict[str, Any]]:
    """Return an OpenAPI `responses` entry for a binary 200 payload."""

    return {
        200: {
            "description": description,
            "content": {media_type: {"schema": {"type": "string", "format": "binary"}}},
        }
    }


PDF_RESPONSE = binary_response("application/pdf", "PDF document bytes.")
XLSX_RESPONSE = binary_response(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "XLSX workbook bytes.",
)
FILE_DOWNLOAD_RESPONSE = binary_response(
    "application/octet-stream", "Stored file bytes with its original media type."
)
