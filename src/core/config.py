from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Financial Data Autopilot"
    database_url: str = "postgresql://localhost:5432/financial_autopilot"
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50
    auto_approve_threshold: float = 0.85
    review_threshold: float = 0.5

    model_config = {"env_prefix": "FDA_"}


settings = Settings()
