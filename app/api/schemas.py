"""Esquemas de entrada/salida de la API.

Se mantienen separados de `app.models` para que el contrato HTTP pueda
evolucionar sin arrastrar al modelo del dominio.
"""

from pydantic import BaseModel, Field

from app.models.cv_model import AnalisisCV, NivelAjuste


class RespuestaEvaluacion(BaseModel):
    """Resultado de evaluar un CV."""

    analisis: AnalisisCV
    nivel_ajuste: NivelAjuste = Field(
        description="Banda cualitativa derivada del porcentaje de ajuste."
    )
    recomendado: bool = Field(
        description="True si el candidato debería pasar a la siguiente fase."
    )

    @classmethod
    def desde_analisis(cls, analisis: AnalisisCV) -> "RespuestaEvaluacion":
        """Aplana las propiedades calculadas para que el cliente no las recalcule."""
        return cls(
            analisis=analisis,
            nivel_ajuste=analisis.nivel_ajuste,
            recomendado=analisis.recomendado,
        )


class RespuestaError(BaseModel):
    """Cuerpo devuelto en cualquier respuesta de error."""

    detail: str = Field(description="Descripción legible del error.")
    error_type: str = Field(description="Identificador estable para el cliente.")


class RespuestaSalud(BaseModel):
    """Estado del servicio."""

    status: str = Field(description="'ok' o 'degraded'.")
    version: str
    modelo: str
    proveedor_configurado: bool = Field(
        description="False si falta la clave de API; el servicio no podrá evaluar."
    )
