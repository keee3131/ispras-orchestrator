from pydantic_settings import BaseSettings
from pydantic.config import BaseConfig

class SettingsConfig(BaseConfig):
    env_nested_delimiter = "__"
    env_file = (".env.local", ".env")
    env_file_encoding = "utf-8"

class Settings(BaseSettings):
    database_url: str
    ttl_poll_seconds: int
    expire_batch_size: int

    class Config(SettingsConfig):
        pass