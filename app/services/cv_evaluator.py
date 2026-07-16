"""Evaluación de un CV contra una descripción de puesto mediante un LLM."""

import logging
import time
from functools import lru_cache

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings
from app.exceptions import ConfigurationError, EvaluationError
from app.models.cv_model import AnalisisCV
from app.prompts.cv_prompts import crear_sistema_prompts

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def crear_evaluador_cv() -> Runnable:
    """Construye la cadena de evaluación.

    Se cachea porque instanciar el cliente abre un pool de conexiones HTTP:
    reconstruirlo en cada petición desperdiciaba el pool y añadía latencia.
    La cadena no guarda estado entre invocaciones, así que compartirla es seguro.

    Raises:
        ConfigurationError: Si falta la clave de API.
    """
    settings: Settings = get_settings()

    if not settings.is_configured:
        raise ConfigurationError(
            "Falta OPENAI_API_KEY. Cópiala en un fichero .env "
            "(usa .env.example como plantilla)."
        )

    modelo = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        api_key=settings.openai_api_key,
    )

    # with_structured_output fuerza al modelo a responder con el esquema de
    # AnalisisCV, en vez de texto libre que habría que parsear.
    return crear_sistema_prompts() | modelo.with_structured_output(AnalisisCV)


def evaluar_candidato(texto_cv: str, descripcion_puesto: str) -> AnalisisCV:
    """Evalúa un CV frente a una descripción de puesto.

    Args:
        texto_cv: Texto plano del CV, ya extraído del PDF.
        descripcion_puesto: Requisitos y responsabilidades del puesto.

    Returns:
        El análisis estructurado del candidato.

    Raises:
        ValueError: Si alguna de las entradas está vacía.
        ConfigurationError: Si falta la clave de API.
        EvaluationError: Si el proveedor falla o devuelve algo que no encaja
            en el esquema.
    """
    if not texto_cv.strip():
        raise ValueError("El texto del CV está vacío.")
    if not descripcion_puesto.strip():
        raise ValueError("La descripción del puesto está vacía.")

    cadena = crear_evaluador_cv()
    inicio = time.perf_counter()

    try:
        resultado = cadena.invoke(
            {"texto_cv": texto_cv, "descripcion_puesto": descripcion_puesto}
        )
    except Exception as exc:
        # Se registra con traza completa y se relanza como error del dominio:
        # devolver un AnalisisCV "de error" con porcentaje 0, como se hacía
        # antes, hacía indistinguible un fallo de red de un candidato malo.
        logger.exception(
            "Fallo al evaluar el candidato.",
            extra={"error_type": type(exc).__name__},
        )
        # El mensaje del proveedor no se propaga: ante una clave inválida,
        # OpenAI la devuelve incrustada en el texto del error ("Incorrect API
        # key provided: sk-..."), que acabaría en la respuesta HTTP. La causa
        # real queda en el log vía `logger.exception` y `raise ... from exc`.
        raise EvaluationError(
            "No se pudo completar el análisis: el proveedor de IA no respondió "
            "correctamente. Reinténtalo en unos segundos."
        ) from exc

    if not isinstance(resultado, AnalisisCV):
        raise EvaluationError(
            f"El modelo devolvió un tipo inesperado: {type(resultado).__name__}"
        )

    logger.info(
        "Candidato evaluado.",
        extra={
            "duracion_ms": round((time.perf_counter() - inicio) * 1000),
            "porcentaje_ajuste": resultado.porcentaje_ajuste,
            "nivel": resultado.nivel_ajuste.value,
        },
    )
    return resultado
