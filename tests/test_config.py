"""Tests de la configuración."""

import pytest

from app.config import Settings, get_settings


def test_lee_la_clave_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-desde-el-entorno")
    get_settings.cache_clear()

    assert get_settings().openai_api_key.get_secret_value() == "sk-desde-el-entorno"


def test_la_clave_no_aparece_al_serializar_los_ajustes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SecretStr evita que un log accidental de Settings publique la clave."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-muy-secreta-12345")
    get_settings.cache_clear()
    settings = get_settings()

    assert "sk-muy-secreta-12345" not in repr(settings)
    assert "sk-muy-secreta-12345" not in str(settings.model_dump())


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("sk-real", True), ("", False), ("   ", False)],
)
def test_is_configured(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: bool
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", valor)
    get_settings.cache_clear()

    assert get_settings().is_configured is esperado


def test_get_settings_esta_cacheado() -> None:
    """La configuración se lee del entorno una sola vez."""
    assert get_settings() is get_settings()


def test_rechaza_temperatura_fuera_de_rango(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPERATURE", "5.0")

    with pytest.raises(ValueError):
        Settings()


def test_valores_por_defecto(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("OPENAI_MODEL", "TEMPERATURE", "MAX_UPLOAD_BYTES", "MAX_CV_CHARS"):
        monkeypatch.delenv(variable, raising=False)
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.openai_model == "gpt-4o-mini"
    assert settings.temperature == 0.2
    assert settings.max_upload_bytes == 5 * 1024 * 1024
    assert settings.max_cv_chars == 30_000
