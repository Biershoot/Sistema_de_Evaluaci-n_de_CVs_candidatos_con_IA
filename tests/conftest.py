"""Fixtures compartidas.

Ningún test llama a OpenAI: la cadena de evaluación se sustituye siempre por un
doble. Así la suite corre en CI sin credenciales, sin coste y sin depender de la
red.
"""

from io import BytesIO

import pytest
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.config import Settings, get_settings
from app.models.cv_model import AnalisisCV
from app.services.cv_evaluator import crear_evaluador_cv


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla los tests del entorno real y de las cachés de módulo.

    `get_settings` y `crear_evaluador_cv` usan lru_cache: sin limpiarlas, un
    test filtraría su configuración al siguiente. Se limpian a través de la
    referencia importada, no del atributo del módulo, porque algunos tests
    sustituyen ese atributo por un doble que no tiene `cache_clear`.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    get_settings.cache_clear()
    crear_evaluador_cv.cache_clear()
    yield
    get_settings.cache_clear()
    crear_evaluador_cv.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


def _construir_pdf(paginas: list[str]) -> bytes:
    """Genera un PDF real con el texto dado, una entrada por página."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    for texto in paginas:
        y = 750
        for linea in texto.split("\n"):
            c.drawString(72, y, linea)
            y -= 14
        c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.fixture
def pdf_valido() -> bytes:
    """PDF de una página con texto extraíble."""
    return _construir_pdf(
        ["Ana Garcia\nIngeniera de Software\n5 anios de experiencia en Python"]
    )


@pytest.fixture
def pdf_multipagina() -> bytes:
    """PDF de dos páginas."""
    return _construir_pdf(["Pagina uno: experiencia", "Pagina dos: educacion"])


@pytest.fixture
def pdf_con_contrasena() -> bytes:
    """PDF cifrado con contraseña de usuario: no se puede abrir sin ella."""
    from reportlab.lib import pdfencrypt

    buffer = BytesIO()
    c = canvas.Canvas(
        buffer,
        pagesize=LETTER,
        encrypt=pdfencrypt.StandardEncryption("clave-secreta"),
    )
    c.drawString(72, 750, "CV confidencial")
    c.save()
    return buffer.getvalue()


@pytest.fixture
def pdf_solo_restringido() -> bytes:
    """PDF cifrado pero sin contraseña de usuario.

    Solo restringe la impresión. Es el caso común de "PDF protegido" que sí
    debe poder leerse.
    """
    from reportlab.lib import pdfencrypt

    buffer = BytesIO()
    c = canvas.Canvas(
        buffer,
        pagesize=LETTER,
        encrypt=pdfencrypt.StandardEncryption("", canPrint=0),
    )
    c.drawString(72, 750, "Ana Garcia ingeniera")
    c.save()
    return buffer.getvalue()


@pytest.fixture
def pdf_sin_texto() -> bytes:
    """PDF con una página en blanco: simula un CV escaneado como imagen."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.fixture
def analisis_ejemplo() -> AnalisisCV:
    """Análisis válido de referencia."""
    return AnalisisCV(
        nombre_candidato="Ana García",
        experiencia_anios=5,
        habilidades_clave=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
        educacion="Ingeniería Informática",
        experiencia_relevante="5 años construyendo APIs backend en Python.",
        fortalezas=["Sólida base en Python", "Experiencia en cloud"],
        areas_mejora=["Poca exposición a frontend"],
        porcentaje_ajuste=85,
    )


@pytest.fixture
def descripcion_puesto() -> str:
    return (
        "Backend Engineer con 3+ años en Python, experiencia con FastAPI, "
        "bases de datos relacionales y despliegue en contenedores."
    )
