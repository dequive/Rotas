from sqlalchemy import create_engine
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()
_alembic_url = settings.resolved_alembic_database_url.replace('+asyncpg', '+psycopg')
engine = create_engine(_alembic_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    tables = [r[0] for r in res]
    for t in ['employees', 'warehouses', 'items', 'stock_movements', 'payroll_slips', 'salary_advances']:
        print(f'{t} exists: {t in tables}')
