"""Export and verify the canonical ROTAS OpenAPI contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_ROOT / "openapi" / "rotas-v1.json"


def build_contract() -> dict[str, Any]:
    schema = app.openapi()
    if not str(schema.get("openapi", "")).startswith("3."):
        raise RuntimeError("Expected an OpenAPI 3.x document.")
    paths = schema.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise RuntimeError("OpenAPI contract contains no paths.")

    operation_ids: dict[str, str] = {}
    for route, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {
                "delete",
                "get",
                "head",
                "options",
                "patch",
                "post",
                "put",
                "trace",
            } or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise RuntimeError(f"Missing operationId for {method.upper()} {route}.")
            previous = operation_ids.get(operation_id)
            if previous:
                raise RuntimeError(
                    f"Duplicate operationId {operation_id!r}: {previous} and "
                    f"{method.upper()} {route}."
                )
            operation_ids[operation_id] = f"{method.upper()} {route}"
    return schema


def serialize_contract(contract: dict[str, Any]) -> bytes:
    content = json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)
    return f"{content}\n".encode()


def contract_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = args.output.resolve()
    content = serialize_contract(build_contract())
    digest = contract_digest(content)

    if args.check:
        if not output.is_file():
            print(f"OpenAPI contract missing: {output}")
            return 1
        if output.read_bytes() != content:
            print(
                "OpenAPI contract drift detected. Regenerate with "
                "`python scripts/export_openapi.py`."
            )
            return 1
        print(f"OpenAPI contract verified: {output} sha256={digest}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    print(f"OpenAPI contract written: {output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
