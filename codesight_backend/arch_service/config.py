import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    arch_db_user: str = pydantic.Field("postgres", alias="ARCH_DB_USER")
    arch_db_password: str = pydantic.Field("postgres", alias="ARCH_DB_PASSWORD")
    arch_db_name: str = pydantic.Field("arch_db", alias="ARCH_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./arch.db", alias="ARCH_DATABASE_URL"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8006

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
