import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dast_db_user: str = pydantic.Field("postgres", alias="DAST_DB_USER")
    dast_db_password: str = pydantic.Field("postgres", alias="DAST_DB_PASSWORD")
    dast_db_name: str = pydantic.Field("dast_db", alias="DAST_DB_NAME")

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./dast.db", alias="DAST_DATABASE_URL"
    )

    storage_dir: str = pydantic.Field(
        "/tmp/codesight_projects", alias="PROJECT_STORAGE_DIR"
    )

    # Таймаут одного запуска valgrind+python (секунды)
    dast_timeout: int = pydantic.Field(180, alias="DAST_TIMEOUT")

    kafka_bootstrap_servers: str = pydantic.Field(
        "localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_command: str = "codesight.dast.start"
    kafka_topic_result: str = "codesight.dast.result"
    kafka_consumer_group: str = pydantic.Field(
        "codesight-dast-worker", alias="KAFKA_CONSUMER_GROUP"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8008

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
