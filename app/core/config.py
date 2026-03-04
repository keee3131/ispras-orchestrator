from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orchestrator"
    ttl_poll_seconds: int = 5

settings = Settings()