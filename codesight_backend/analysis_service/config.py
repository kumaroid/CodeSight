import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    analysis_db_user: str = pydantic.Field("postgres", alias="ANALYSIS_DB_USER")
    analysis_db_password: str = pydantic.Field("postgres", alias="ANALYSIS_DB_PASSWORD")
    analysis_db_name: str = pydantic.Field("analysis_db", alias="ANALYSIS_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./analysis.db", alias="ANALYSIS_DATABASE_URL"
    )

    # Путь к хранилищу проектов (тот же, что у loader_service)
    storage_dir: str = pydantic.Field(
        "/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8003

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
