from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "Jalproloi API"
    database_url: str = "postgresql+psycopg://jalproloi:jalproloi@localhost:5432/jalproloi"
    redis_url: str = "redis://localhost:6379/0"
    # Serve clearly-labelled synthetic data until the engines publish real forecasts.
    demo_mode: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    cap_sender: str = "jalproloi@example.org"
    cap_status: str = "Exercise"  # "Actual" only for real operational alerts
    telegram_bot_token: str | None = None


settings = Settings()
