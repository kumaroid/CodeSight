import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    arch_db_user: str = pydantic.Field("postgres", alias="ARCH_DB_USER")
    arch_db_password: str = pydantic.Field("postgres", alias="ARCH_DB_PASSWORD")
    arch_db_name: str = pydantic.Field("arch_db", alias="ARCH_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./arch.db", alias="ARCH_DATABASE_URL"
    )

    project_storage_dir: str = pydantic.Field(
        "/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8006

    kafka_bootstrap_servers: str = pydantic.Field(
        "localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_command: str = "codesight.arch.start"
    kafka_topic_result: str = "codesight.arch.result"
    kafka_consumer_group: str = pydantic.Field(
        "codesight-arch-worker", alias="KAFKA_CONSUMER_GROUP"
    )
    archer_url: str | None = pydantic.Field(None, alias="ARCHER_URL")
    archer_timeout_seconds: float = pydantic.Field(45.0, alias="ARCHER_TIMEOUT_SECONDS")

    arch_blueprint_timeout_seconds: float = pydantic.Field(
        120.0, alias="ARCH_BLUEPRINT_TIMEOUT_SECONDS"
    )

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
