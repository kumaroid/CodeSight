import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    testing_db_user: str = pydantic.Field("postgres", alias="TESTING_DB_USER")
    testing_db_password: str = pydantic.Field("postgres", alias="TESTING_DB_PASSWORD")
    testing_db_name: str = pydantic.Field("testing_db", alias="TESTING_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./testing.db", alias="TESTING_DATABASE_URL"
    )

    storage_dir: str = pydantic.Field(
        "/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR"
    )

    # Таймаут выполнения тестов (секунды)
    test_timeout: int = pydantic.Field(120, alias="TESTING_TIMEOUT")

    app_host: str = "0.0.0.0"
    app_port: int = 8004

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
