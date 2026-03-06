from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orchestrator"
    ttl_poll_seconds: int = 5
    expire_batch_size: int = 100

settings = Settings()