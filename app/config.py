"""Configuración cargada desde variables de entorno."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes de la aplicación.

    Los valores se leen de variables de entorno y, en desarrollo, de un fichero
    `.env` que nunca se versiona.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SecretStr y no str: Pydantic lo enmascara en repr() y en las trazas, así
    # que un log accidental del objeto Settings no publica la clave.
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Clave de API de OpenAI. Obligatoria para evaluar CVs.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Modelo de chat usado para el análisis.",
    )
    # Temperatura baja: la evaluación debe ser lo más reproducible posible
    # entre ejecuciones sobre el mismo CV.
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    request_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Timeout por llamada al proveedor, en segundos.",
    )
    max_retries: int = Field(default=2, ge=0)

    max_upload_bytes: int = Field(
        default=5 * 1024 * 1024,
        gt=0,
        description="Tamaño máximo aceptado para el PDF subido.",
    )
    max_cv_chars: int = Field(
        default=30_000,
        gt=0,
        description="Límite de caracteres del CV enviados al modelo, para acotar coste.",
    )

    log_level: str = Field(default="INFO")

    @property
    def is_configured(self) -> bool:
        """True si hay credenciales suficientes para llamar al proveedor."""
        return bool(self.openai_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    """Devuelve los ajustes (cacheados: se leen del entorno una sola vez)."""
    return Settings()
