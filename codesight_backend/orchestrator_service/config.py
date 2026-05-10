import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    orchestrator_db_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./orchestrator.db",
        alias="ORCHESTRATOR_DATABASE_URL",
    )

    # Kafka
    kafka_bootstrap_servers: str = pydantic.Field(
        "kafka:29092",
        alias="KAFKA_BOOTSTRAP_SERVERS",
    )

    # Topics – commands (orchestrator → services)
    topic_analysis_start: str = "codesight.analysis.start"
    topic_security_start: str = "codesight.security.start"
    topic_arch_start: str = "codesight.arch.start"
    topic_testing_start: str = "codesight.testing.start"

    # Topics – results (services → orchestrator)
    topic_analysis_result: str = "codesight.analysis.result"
    topic_security_result: str = "codesight.security.result"
    topic_arch_result: str = "codesight.arch.result"
    topic_testing_result: str = "codesight.testing.result"

    # Topic for saga state updates (orchestrator → frontend/gateway)
    topic_saga_state: str = "codesight.saga.state"

    # Consumer group
    kafka_consumer_group: str = "orchestrator-group"

    app_host: str = "0.0.0.0"
    app_port: int = 8007

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
