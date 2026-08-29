from fastapi import FastAPI

from routes.generate import router as generate_router

app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="1.0.0",
)

@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "Usage Metering & Billing Engine",
    }

app.include_router(generate_router)