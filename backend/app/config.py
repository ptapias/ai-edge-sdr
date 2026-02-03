"""
Configuración centralizada de la aplicación.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""

    # App
    app_name: str = "LinkedIn AI SDR"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///../../data/leads.db"

    # Apify
    apify_api_token: str = ""
    apify_actor_id: str = "IoSHqwTR9YGhzccez"  # code_crafter/leads-finder

    # Anthropic Claude
    anthropic_api_key: str = ""

    # Million Verifier
    million_verifier_api_key: str = ""

    # N8N
    n8n_base_url: str = "http://localhost:5678"
    n8n_webhook_linkedin: str = "/webhook/linkedin-send"

    # Unipile (default values for backward compatibility)
    unipile_api_url: str = "https://api14.unipile.com:14459/api/v1"
    unipile_api_key: str = ""
    unipile_account_id: str = ""

    # JWT Authentication
    jwt_secret_key: str = "your-super-secret-key-change-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Encryption for sensitive data (Fernet key)
    encryption_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración cacheada de la aplicación."""
    return Settings()


# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
