from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, loaded from environment variables / .env file."""

    database_url: str = "postgresql+psycopg2://inventory:inventory@localhost:5432/inventory_db"
    debug: bool = True
    project_name: str = "Inventory Management System"
    api_v1_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
