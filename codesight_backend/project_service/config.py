import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_db_user: str = pydantic.Field("postgres", alias="PROJECT_DB_USER")
    project_db_password: str = pydantic.Field("postgres", alias="PROJECT_DB_PASSWORD")
    project_db_name: str = pydantic.Field("project_db", alias="PROJECT_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./projects.db", alias="PROJECT_DATABASE_URL"
    )

    # Каталог для хранения распакованных проектов
    storage_dir: str = pydantic.Field("/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR")

    # Максимальный размер ZIP-архива в байтах (50 МБ по умолчанию)
    max_zip_size_bytes: int = pydantic.Field(52_428_800, alias="PROJECT_MAX_ZIP_SIZE")

    app_host: str = "0.0.0.0"
    app_port: int = 8002

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
