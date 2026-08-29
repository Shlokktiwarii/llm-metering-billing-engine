from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=True,
)


class Base(DeclarativeBase):
    pass


class SessionLocalFactory(sessionmaker):
    def __call__(self, *args, **kwargs):
        ensure_default_seed_data()
        return super().__call__(*args, **kwargs)


def ensure_default_seed_data() -> None:
    """Create tables once and seed the default free plan used by tests."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT 1 FROM plans WHERE id = :plan_id"),
            {"plan_id": "free"},
        ).fetchone()

        if existing is None:
            connection.execute(
                text(
                    """
                    INSERT INTO plans (id, name, api_call_quota, ai_token_quota, price_cents)
                    VALUES (:plan_id, :name, :api_call_quota, :ai_token_quota, :price_cents)
                    """
                ),
                {
                    "plan_id": "free",
                    "name": "Free",
                    "api_call_quota": 0,
                    "ai_token_quota": 0,
                    "price_cents": 0,
                },
            )


SessionLocal = SessionLocalFactory(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "SessionLocal", "engine", "get_db"]
