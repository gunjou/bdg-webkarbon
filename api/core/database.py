# api/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from api.core import config

_engine = None


def get_engine():
    """Engine dibuat sekali saat pertama dipakai, lalu dipakai ulang (pool aman)."""
    global _engine
    if _engine is None:
        # URL.create meng-escape karakter khusus di password (@, /, #, dll)
        url = URL.create(
            "postgresql+psycopg2",
            username=config.DB_USER,
            password=config.DB_PASS,
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
        )
        _engine = create_engine(
            url,
            pool_size=10,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
    return _engine
