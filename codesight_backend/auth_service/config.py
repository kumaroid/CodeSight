import pydantic
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret_key: str = pydantic.Field("meow", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = pydantic.Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = pydantic.Field(
        30, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = pydantic.Field(
        7, alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )

    database_url: str = pydantic.Field(
        "sqlite+aiosqlite:///./test.db", alias="DATABASE_URL"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8001

    class Config:
        env_file = ".env.example"
        env_file_encoding = "utf-8"


settings = Settings()
