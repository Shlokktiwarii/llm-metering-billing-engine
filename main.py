from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.config import settings


engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = DeclarativeBase()

print(settings.DATABASE_URL)
app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="1.0.0",
)

@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "Usage Metering & Billing Engine"
    }
