from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Financial Data Autopilot"
    database_url: str = "postgresql://localhost:5432/financial_autopilot"
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50
    auto_approve_threshold: float = 0.85
    review_threshold: float = 0.5

    llm_enabled: bool = False
    llm_api_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_timeout_seconds: int = 10

    model_config = {"env_prefix": "FDA_"}

    @property
    def effective_database_url(self) -> str:
        """Render gives postgres:// but SQLAlchemy 2.0 requires postgresql://"""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


settings = Settings()
