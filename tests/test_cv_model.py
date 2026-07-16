"""Tests del esquema del análisis."""

import pytest
from pydantic import ValidationError

from app.models.cv_model import AnalisisCV, NivelAjuste


def _analisis(porcentaje: int, **extra) -> AnalisisCV:
    base = {
        "nombre_candidato": "Test",
        "experiencia_anios": 3,
        "habilidades_clave": ["Python"],
        "educacion": "Ingeniería",
        "experiencia_relevante": "Backend",
        "fortalezas": ["Rápido aprendizaje"],
        "areas_mejora": ["Testing"],
        "porcentaje_ajuste": porcentaje,
    }
    return AnalisisCV(**{**base, **extra})


@pytest.mark.parametrize(
    ("porcentaje", "esperado"),
    [
        (100, NivelAjuste.EXCELENTE),
        (80, NivelAjuste.EXCELENTE),  # límite inferior
        (79, NivelAjuste.BUENO),
        (60, NivelAjuste.BUENO),
        (59, NivelAjuste.REGULAR),
        (40, NivelAjuste.REGULAR),
        (39, NivelAjuste.BAJO),
        (0, NivelAjuste.BAJO),
    ],
)
def test_nivel_ajuste_en_los_limites(porcentaje: int, esperado: NivelAjuste) -> None:
    assert _analisis(porcentaje).nivel_ajuste is esperado


@pytest.mark.parametrize(
    ("porcentaje", "esperado"),
    [(70, True), (69, False), (100, True), (0, False)],
)
def test_recomendado_usa_umbral_70(porcentaje: int, esperado: bool) -> None:
    assert _analisis(porcentaje).recomendado is esperado


@pytest.mark.parametrize("porcentaje", [-1, 101, 500])
def test_rechaza_porcentaje_fuera_de_rango(porcentaje: int) -> None:
    with pytest.raises(ValidationError):
        _analisis(porcentaje)


def test_rechaza_experiencia_negativa() -> None:
    with pytest.raises(ValidationError):
        _analisis(50, experiencia_anios=-3)


def test_limpia_entradas_vacias_de_las_listas() -> None:
    """El modelo a veces devuelve strings vacíos o con espacios sobrantes."""
    analisis = _analisis(
        50,
        habilidades_clave=["Python", "", "  ", "  Docker  "],
        fortalezas=["Comunicación", ""],
    )

    assert analisis.habilidades_clave == ["Python", "Docker"]
    assert analisis.fortalezas == ["Comunicación"]
