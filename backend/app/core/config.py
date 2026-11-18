import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Defaults to local SQLite if POSTGRES isn't specified, but easily connects to PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./procurement.db")
    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC", "sqlite:///./procurement.db")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_PRIMARY: str = "gemini-2.5-flash"
    GEMINI_MODEL_LITE: str = "gemini-2.0-flash-lite"
    APP_NAME: str = "Corvo Procurement Management System"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = [".env", "../.env", "../../.env"]
        extra = "ignore"

settings = Settings()

