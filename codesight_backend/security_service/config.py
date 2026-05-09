import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    security_db_user: str = pydantic.Field("postgres", alias="SECURITY_DB_USER")
    security_db_password: str = pydantic.Field("postgres", alias="SECURITY_DB_PASSWORD")
    security_db_name: str = pydantic.Field("security_db", alias="SECURITY_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./security.db", alias="SECURITY_DATABASE_URL"
    )

    # Путь к хранилищу проектов (тот же, что у loader_service)
    storage_dir: str = pydantic.Field(
        "/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8005

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
