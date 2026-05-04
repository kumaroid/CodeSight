from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@auth_db:5432/auth_db"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
