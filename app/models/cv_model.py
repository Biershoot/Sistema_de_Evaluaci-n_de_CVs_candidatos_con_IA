"""Esquema del análisis de un CV.

Este modelo es el contrato en dos sentidos a la vez: es el cuerpo de la respuesta
de la API y es el esquema que se le impone al LLM vía `with_structured_output`.
Las descripciones de cada campo se envían al modelo como parte de la
especificación de la herramienta, así que están redactadas para el modelo, no
solo para quien lee el código.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class NivelAjuste(StrEnum):
    """Banda cualitativa derivada del porcentaje de ajuste."""

    EXCELENTE = "excelente"
    BUENO = "bueno"
    REGULAR = "regular"
    BAJO = "bajo"


class AnalisisCV(BaseModel):
    """Análisis estructurado de un CV frente a una descripción de puesto."""

    nombre_candidato: str = Field(
        description="Nombre completo del candidato extraído del CV. "
        "Si no aparece, usa 'No identificado'."
    )
    experiencia_anios: int = Field(
        ge=0,
        le=60,
        description="Años totales de experiencia laboral relevante.",
    )
    habilidades_clave: list[str] = Field(
        description="Entre 5 y 7 habilidades del candidato más relevantes para el puesto."
    )
    educacion: str = Field(
        description="Nivel educativo más alto y especialización principal."
    )
    experiencia_relevante: str = Field(
        description="Resumen conciso de la experiencia más relevante para el puesto."
    )
    fortalezas: list[str] = Field(
        description="Entre 3 y 5 fortalezas principales del candidato."
    )
    areas_mejora: list[str] = Field(
        description="Entre 2 y 4 áreas donde el candidato podría desarrollarse."
    )
    porcentaje_ajuste: int = Field(
        ge=0,
        le=100,
        description=(
            "Porcentaje de ajuste al puesto (0-100), ponderando: experiencia "
            "relevante 40%, habilidades técnicas 35%, formación 15%, "
            "coherencia profesional 10%."
        ),
    )

    @field_validator("habilidades_clave", "fortalezas", "areas_mejora")
    @classmethod
    def _limpiar_listas(cls, v: list[str]) -> list[str]:
        """Descarta entradas vacías y espacios sobrantes que a veces devuelve el LLM."""
        return [item.strip() for item in v if item and item.strip()]

    @property
    def nivel_ajuste(self) -> NivelAjuste:
        """Banda cualitativa del ajuste.

        Se calcula aquí y no en la UI para que API y Streamlit apliquen
        exactamente los mismos umbrales.
        """
        if self.porcentaje_ajuste >= 80:
            return NivelAjuste.EXCELENTE
        if self.porcentaje_ajuste >= 60:
            return NivelAjuste.BUENO
        if self.porcentaje_ajuste >= 40:
            return NivelAjuste.REGULAR
        return NivelAjuste.BAJO

    @property
    def recomendado(self) -> bool:
        """True si el candidato debería pasar a la siguiente fase."""
        return self.porcentaje_ajuste >= 70
