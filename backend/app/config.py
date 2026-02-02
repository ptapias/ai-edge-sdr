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
