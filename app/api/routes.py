"""Endpoints HTTP."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app import __version__
from app.api.schemas import RespuestaError, RespuestaEvaluacion, RespuestaSalud
from app.config import Settings, get_settings
from app.services.cv_evaluator import evaluar_candidato
from app.services.pdf_processor import extraer_texto_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=RespuestaSalud,
    tags=["operaciones"],
    summary="Estado del servicio",
)
def health(settings: Settings = Depends(get_settings)) -> RespuestaSalud:
    """Sonda de salud para orquestadores.

    Devuelve 200 aunque falte la clave de API: el proceso está vivo y debe
    seguir recibiendo tráfico, pero `status` pasa a 'degraded' para que sea
    visible en monitorización.
    """
    configurado = settings.is_configured
    return RespuestaSalud(
        status="ok" if configurado else "degraded",
        version=__version__,
        modelo=settings.openai_model,
        proveedor_configurado=configurado,
    )


@router.post(
    "/evaluations",
    response_model=RespuestaEvaluacion,
    status_code=status.HTTP_200_OK,
    tags=["evaluaciones"],
    summary="Evaluar un CV frente a una descripción de puesto",
    responses={
        400: {"model": RespuestaError, "description": "PDF ilegible o entrada inválida"},
        413: {
            "model": RespuestaError,
            "description": "El archivo excede el tamaño máximo",
        },
        415: {"model": RespuestaError, "description": "El archivo no es un PDF"},
        502: {"model": RespuestaError, "description": "Fallo del proveedor de IA"},
    },
)
async def crear_evaluacion(
    cv: UploadFile = File(description="CV del candidato en PDF."),
    descripcion_puesto: str = Form(
        min_length=20,
        description="Requisitos y responsabilidades del puesto.",
    ),
    settings: Settings = Depends(get_settings),
) -> RespuestaEvaluacion:
    """Extrae el texto del CV y lo evalúa contra la descripción del puesto."""
    if cv.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Se esperaba un PDF, se recibió '{cv.content_type}'.",
        )

    contenido = await cv.read()

    # El Content-Length es cosa del cliente; el tamaño real solo se conoce tras
    # leer, así que el límite se comprueba aquí.
    if len(contenido) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"El archivo pesa {len(contenido):,} bytes y el máximo es "
                f"{settings.max_upload_bytes:,}."
            ),
        )

    texto_cv = extraer_texto_pdf(contenido, max_chars=settings.max_cv_chars)
    analisis = evaluar_candidato(texto_cv, descripcion_puesto)

    return RespuestaEvaluacion.desde_analisis(analisis)
