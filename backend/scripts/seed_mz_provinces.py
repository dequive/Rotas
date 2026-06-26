"""Seed Mozambique provinces into mz_provinces table. Idempotent.

Usage:
    cd backend && python scripts/seed_mz_provinces.py
"""

import asyncio

# Province data: (code, name, name_local, region)
PROVINCES = [
    ("MZ-MPM", "Maputo City", "Cidade de Maputo", "Sul"),
    ("MZ-L", "Maputo Province", "Província de Maputo", "Sul"),
    ("MZ-G", "Gaza", "Gaza", "Sul"),
    ("MZ-I", "Inhambane", "Inhambane", "Sul"),
    ("MZ-S", "Sofala", "Sofala", "Centro"),
    ("MZ-B", "Manica", "Manica", "Centro"),
    ("MZ-T", "Tete", "Tete", "Centro"),
    ("MZ-Q", "Zambézia", "Zambézia", "Norte"),
    ("MZ-N", "Nampula", "Nampula", "Norte"),
    ("MZ-A", "Niassa", "Niassa", "Norte"),
    ("MZ-P", "Cabo Delgado", "Cabo Delgado", "Norte"),
]


async def seed() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        for code, name, name_local, region in PROVINCES:
            await conn.execute(
                text(
                    "INSERT INTO mz_provinces (code, name, name_local, region) "
                    "VALUES (:code, :name, :name_local, :region) "
                    "ON CONFLICT (code) DO NOTHING"
                ),
                {"code": code, "name": name, "name_local": name_local, "region": region},
            )
    await engine.dispose()
    print(f"Seeded {len(PROVINCES)} provinces (idempotent — existing rows skipped).")


if __name__ == "__main__":
    asyncio.run(seed())
