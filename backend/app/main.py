"""
Corvo Engineering - Procurement Engine FastAPI Application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import batch

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Deterministic, Policy-as-Data Procurement Decision Engine"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batch.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION, "app": settings.APP_NAME}

