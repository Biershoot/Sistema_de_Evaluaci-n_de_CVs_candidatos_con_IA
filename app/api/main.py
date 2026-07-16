"""Construcción de la aplicación FastAPI."""

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.exceptions import ConfigurationError, EvaluationError, PDFExtractionError
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Cada error del dominio tiene un único código HTTP. Centralizarlo aquí evita
# que cada endpoint repita la traducción.
_MAPA_ERRORES: dict[type[Exception], int] = {
    PDFExtractionError: status.HTTP_400_BAD_REQUEST,
    EvaluationError: status.HTTP_502_BAD_GATEWAY,
    ConfigurationError: status.HTTP_503_SERVICE_UNAVAILABLE,
}

# Identificadores estables para los errores que lanza la capa HTTP, para que el
# cliente pueda ramificar sin parsear `detail`.
_NOMBRES_HTTP: dict[int, str] = {
    status.HTTP_413_CONTENT_TOO_LARGE: "PayloadTooLarge",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "UnsupportedMediaType",
}


def _respuesta_error(exc: Exception, codigo: int) -> JSONResponse:
    return JSONResponse(
        status_code=codigo,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )


def create_app() -> FastAPI:
    """Crea y configura la aplicación.

    Es una factoría (y no un módulo con `app = FastAPI()`) para que los tests
    puedan construir instancias limpias con distintos ajustes.
    """
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Sistema de Evaluación de CVs con IA",
        description=(
            "API que analiza currículums en PDF y los evalúa frente a una "
            "descripción de puesto, devolviendo un análisis estructurado."
        ),
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.include_router(router, prefix="/api/v1")

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ):
        """Asigna un ID a cada petición para poder correlacionar logs."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    for tipo_error, codigo in _MAPA_ERRORES.items():

        @app.exception_handler(tipo_error)
        async def manejar_error_dominio(
            request: Request,
            exc: Exception,
            _codigo: int = codigo,  # se fija ahora: si no, el closure leería
        ) -> JSONResponse:  # la última `codigo` del bucle en todos los handlers
            logger.warning(
                "Error de dominio.",
                extra={"error_type": type(exc).__name__, "path": request.url.path},
            )
            return _respuesta_error(exc, _codigo)

    @app.exception_handler(ValueError)
    async def manejar_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _respuesta_error(exc, status.HTTP_400_BAD_REQUEST)

    @app.exception_handler(HTTPException)
    async def manejar_http_exception(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Añade `error_type` a los errores que lanza la propia capa HTTP.

        El handler por defecto de FastAPI devuelve solo `detail`, lo que dejaría
        un 415 con una forma distinta a la de los errores del dominio.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_type": _NOMBRES_HTTP.get(exc.status_code, "HTTPError"),
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def manejar_error_inesperado(request: Request, exc: Exception) -> JSONResponse:
        # Se registra la traza completa pero no se expone al cliente: podría
        # filtrar rutas internas o fragmentos de configuración.
        logger.exception("Error no controlado.", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Error interno del servidor.",
                "error_type": "InternalServerError",
            },
        )

    return app


app = create_app()
