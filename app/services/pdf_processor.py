"""Extracción de texto de CVs en PDF."""

import logging
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.exceptions import PDFExtractionError

logger = logging.getLogger(__name__)


def extraer_texto_pdf(contenido: bytes, *, max_chars: int | None = None) -> str:
    """Extrae el texto de un PDF en memoria.

    Recibe `bytes` en lugar de un file-like para que el servicio no dependa de
    Streamlit ni de FastAPI: ambos adaptan su propio objeto de subida antes de
    llamar aquí.

    Args:
        contenido: Bytes crudos del PDF.
        max_chars: Si se indica, trunca el texto a esa longitud. Sirve para
            acotar el coste de la llamada al LLM en CVs muy largos.

    Returns:
        El texto extraído, con marcas de página para dar contexto al modelo.

    Raises:
        PDFExtractionError: Si el PDF está vacío, corrupto, cifrado o es una
            imagen escaneada sin capa de texto.
    """
    if not contenido:
        raise PDFExtractionError("El archivo está vacío.")

    try:
        lector = PdfReader(BytesIO(contenido))
    except PdfReadError as exc:
        raise PDFExtractionError(
            f"El archivo no es un PDF válido o está dañado: {exc}"
        ) from exc

    if lector.is_encrypted:
        # pypdf permite intentar descifrar con contraseña vacía; muchos PDFs
        # "protegidos" solo restringen impresión y se abren así.
        try:
            if lector.decrypt("") == 0:
                raise PDFExtractionError("El PDF está protegido con contraseña.")
        except PdfReadError as exc:
            raise PDFExtractionError(
                f"El PDF está cifrado y no se pudo abrir: {exc}"
            ) from exc

    partes: list[str] = []
    for numero, pagina in enumerate(lector.pages, start=1):
        try:
            texto = pagina.extract_text() or ""
        except Exception as exc:  # pypdf lanza tipos variados por página
            logger.warning(
                "No se pudo extraer una página; se omite.",
                extra={"pagina": numero, "error": str(exc)},
            )
            continue

        if texto.strip():
            partes.append(f"--- PÁGINA {numero} ---\n{texto.strip()}")

    if not partes:
        raise PDFExtractionError(
            "El PDF no contiene texto extraíble. Suele pasar con CVs escaneados "
            "como imagen: exporta el CV a PDF desde el editor original."
        )

    texto_completo = "\n\n".join(partes)

    if max_chars is not None and len(texto_completo) > max_chars:
        logger.info(
            "CV truncado por exceder el límite de caracteres.",
            extra={"original": len(texto_completo), "limite": max_chars},
        )
        texto_completo = texto_completo[:max_chars]

    logger.info(
        "Texto extraído del PDF.",
        extra={"paginas": len(lector.pages), "caracteres": len(texto_completo)},
    )
    return texto_completo
