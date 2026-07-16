"""Tests del evaluador.

La cadena LangChain se sustituye por un doble: no se llama a OpenAI.
"""

import pytest
from langchain_core.runnables import RunnableLambda

from app.config import get_settings
from app.exceptions import ConfigurationError, EvaluationError
from app.models.cv_model import AnalisisCV
from app.services import cv_evaluator
from app.services.cv_evaluator import crear_evaluador_cv, evaluar_candidato


class CadenaFalsa:
    """Doble de la cadena de evaluación."""

    def __init__(self, resultado=None, error: Exception | None = None):
        self._resultado = resultado
        self._error = error
        self.invocaciones: list[dict] = []

    def invoke(self, entrada: dict):
        self.invocaciones.append(entrada)
        if self._error is not None:
            raise self._error
        return self._resultado


@pytest.fixture
def usar_cadena(monkeypatch: pytest.MonkeyPatch):
    """Inyecta una cadena falsa en el evaluador."""

    def _usar(resultado=None, error: Exception | None = None) -> CadenaFalsa:
        cadena = CadenaFalsa(resultado=resultado, error=error)
        monkeypatch.setattr(cv_evaluator, "crear_evaluador_cv", lambda: cadena)
        return cadena

    return _usar


def test_devuelve_el_analisis_del_modelo(
    usar_cadena, analisis_ejemplo: AnalisisCV, descripcion_puesto: str
) -> None:
    usar_cadena(resultado=analisis_ejemplo)

    resultado = evaluar_candidato("CV de Ana García, Python", descripcion_puesto)

    assert resultado == analisis_ejemplo
    assert resultado.porcentaje_ajuste == 85


def test_pasa_cv_y_puesto_al_prompt(
    usar_cadena, analisis_ejemplo: AnalisisCV, descripcion_puesto: str
) -> None:
    cadena = usar_cadena(resultado=analisis_ejemplo)

    evaluar_candidato("texto del cv", descripcion_puesto)

    assert cadena.invocaciones == [
        {"texto_cv": "texto del cv", "descripcion_puesto": descripcion_puesto}
    ]


@pytest.mark.parametrize("cv_invalido", ["", "   ", "\n\t"])
def test_rechaza_cv_vacio(cv_invalido: str, descripcion_puesto: str) -> None:
    with pytest.raises(ValueError, match="CV está vacío"):
        evaluar_candidato(cv_invalido, descripcion_puesto)


@pytest.mark.parametrize("puesto_invalido", ["", "   "])
def test_rechaza_puesto_vacio(puesto_invalido: str) -> None:
    with pytest.raises(ValueError, match="puesto está vacía"):
        evaluar_candidato("un cv", puesto_invalido)


def test_fallo_del_proveedor_lanza_evaluation_error(
    usar_cadena, descripcion_puesto: str
) -> None:
    """Regresión: un fallo del proveedor no puede parecer un candidato malo.

    La versión inicial capturaba la excepción y devolvía un AnalisisCV con
    porcentaje_ajuste=0, indistinguible de un candidato realmente descartable.
    """
    usar_cadena(error=ConnectionError("timeout del proveedor"))

    with pytest.raises(EvaluationError, match="No se pudo completar el análisis"):
        evaluar_candidato("un cv válido", descripcion_puesto)


def test_no_propaga_el_mensaje_del_proveedor(
    usar_cadena, descripcion_puesto: str
) -> None:
    """Regresión: el error del proveedor puede contener la clave de API.

    Ante una clave inválida, OpenAI responde "Incorrect API key provided:
    sk-...". Incrustar ese texto en EvaluationError lo publicaba en el cuerpo
    de la respuesta HTTP.
    """
    usar_cadena(
        error=RuntimeError(
            "Error code: 401 - Incorrect API key provided: sk-secreto-real"
        )
    )

    with pytest.raises(EvaluationError) as exc_info:
        evaluar_candidato("un cv válido", descripcion_puesto)

    assert "sk-secreto-real" not in str(exc_info.value)
    assert "401" not in str(exc_info.value)
    # La causa original sigue disponible para el log y la depuración.
    assert "sk-secreto-real" in str(exc_info.value.__cause__)


def test_tipo_inesperado_lanza_evaluation_error(
    usar_cadena, descripcion_puesto: str
) -> None:
    """Si with_structured_output devolviera un dict, no debe propagarse."""
    usar_cadena(resultado={"porcentaje_ajuste": 50})

    with pytest.raises(EvaluationError, match="tipo inesperado"):
        evaluar_candidato("un cv válido", descripcion_puesto)


def test_sin_api_key_lanza_configuration_error(
    monkeypatch: pytest.MonkeyPatch, descripcion_puesto: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    crear_evaluador_cv.cache_clear()

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        evaluar_candidato("un cv válido", descripcion_puesto)


def test_la_cadena_se_construye_una_sola_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    """El cliente HTTP se reutiliza entre peticiones."""
    llamadas = 0

    class ModeloFalso:
        def with_structured_output(self, _schema):
            # Debe ser un Runnable: crear_evaluador_cv lo compone con `|`.
            return RunnableLambda(lambda _entrada: None)

    def fabrica(**_kwargs):
        nonlocal llamadas
        llamadas += 1
        return ModeloFalso()

    monkeypatch.setattr(cv_evaluator, "ChatOpenAI", fabrica)
    crear_evaluador_cv.cache_clear()

    crear_evaluador_cv()
    crear_evaluador_cv()

    assert llamadas == 1
