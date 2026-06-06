#!/usr/bin/env python
"""One-shot script: migrate all local File records to Cloudflare R2.

Operator workflow (D-09, D-12 from RESEARCH.md):
  1. Configure R2 credentials in environment:
       R2_BUCKET, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
  2. Run from project root:
       cd backend && python scripts/migrate_files_to_r2.py
  3. Verify exit code 0 and "0 failed" in the summary line.
  4. Run gate query to confirm zero local records remain:
       SELECT count(*) FROM files WHERE storage_provider IN ('local', 'local_stub');
  5. ONLY THEN set STORAGE_PROVIDER=r2 in Railway environment variables.

CRITICAL: Never set STORAGE_PROVIDER=r2 before this script completes successfully (D-09).
           Railway deploys on ephemeral disk — local files are wiped on every deploy.
           Any file not migrated before switching will be permanently lost.

Exit codes:
  0 — all files migrated successfully (zero failures)
  1 — one or more files failed to migrate (see output for details)
"""
import asyncio
import sys
from pathlib import Path

# Allow running as: python backend/scripts/migrate_files_to_r2.py from project root
# or as: cd backend && python scripts/migrate_files_to_r2.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiobotocore.session
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.modules.files.models import File

_settings = get_settings()

LOCAL_PROVIDERS = ("local", "local_stub")


def _local_disk_path(storage_key: str) -> Path:
    """Reconstruct the absolute disk path from a storage_key.

    storage_key format: "{tenant_id}/{entity_type}/{file_id}_{filename}"
    Local path: local_upload_dir / {entity_type}/{file_id}_{filename}
    (tenant segment is stripped — mirrors _local_path() in app/storage.py)
    """
    root = Path(_settings.local_upload_dir)
    relative = storage_key.split("/", maxsplit=1)[1] if "/" in storage_key else storage_key
    return root / relative


async def _upload_one_to_r2(storage_key: str, content: bytes, mime_type: str) -> None:
    """Upload a single file to R2 using the configured credentials."""
    session = aiobotocore.session.get_session()
    async with session.create_client(
        "s3",
        endpoint_url=_settings.r2_endpoint_url,
        aws_access_key_id=_settings.r2_access_key_id,
        aws_secret_access_key=_settings.r2_secret_access_key.get_secret_value(),
    ) as client:
        await client.put_object(
            Bucket=_settings.r2_bucket,
            Key=storage_key,
            Body=content,
            ContentType=mime_type,
        )


async def main() -> int:
    """Migrate all local File records to R2. Returns 0 on full success, 1 on any failure."""
    uploaded = 0
    failed: list[tuple[str, str]] = []

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(File).where(File.storage_provider.in_(list(LOCAL_PROVIDERS)))
        )
        files = result.scalars().all()
        total = len(files)
        print(f"Found {total} local file(s) to migrate to R2.")

        if total == 0:
            print("Nothing to migrate. Gate query will return 0.")
            return 0

        for file in files:
            local_path = _local_disk_path(file.storage_key)

            try:
                if not local_path.exists():
                    raise FileNotFoundError(f"File not found on disk: {local_path}")

                content = local_path.read_bytes()
                await _upload_one_to_r2(file.storage_key, content, file.mime_type)

                # Update the record — mark as migrated to R2
                file.storage_provider = "r2"
                await db.flush()
                uploaded += 1
                print(f"  [OK]   {file.id}  {file.storage_key}")

            except Exception as exc:  # noqa: BLE001 — intentional: capture all per-file errors
                failed.append((str(file.id), str(exc)))
                print(f"  [FAIL] {file.id}  {exc}")

        await db.commit()

    skipped = total - uploaded - len(failed)
    print(
        f"\nMigration complete: {uploaded} uploaded | {len(failed)} failed | {skipped} skipped"
    )

    if failed:
        print("\nFailed files:")
        for file_id, reason in failed:
            print(f"  {file_id}: {reason}")
        print(
            "\nFix the failures above, then re-run this script before setting STORAGE_PROVIDER=r2."
        )
        return 1

    print("\nAll files migrated. Gate query should now return 0.")
    print("  SELECT count(*) FROM files WHERE storage_provider IN ('local', 'local_stub');")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
