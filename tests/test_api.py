"""Tests de la capa HTTP.

Cubren el contrato de la API y la traducción de errores del dominio a códigos
de estado. La evaluación real se sustituye por un doble.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.routes import router  # noqa: F401  (asegura el import del módulo)
from app.exceptions import ConfigurationError, EvaluationError
from app.models.cv_model import AnalisisCV

PUESTO = "Backend Engineer con 3+ años en Python, FastAPI y bases de datos relacionales."


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, analisis_ejemplo: AnalisisCV) -> TestClient:
    """Cliente con el evaluador parcheado para devolver un análisis fijo."""
    from app.api import routes

    monkeypatch.setattr(routes, "evaluar_candidato", lambda *_: analisis_ejemplo)
    # raise_server_exceptions=False: queremos observar la respuesta 500 que
    # produce el handler, no que TestClient relance la excepción.
    return TestClient(create_app(), raise_server_exceptions=False)


def _archivo(contenido: bytes, nombre: str = "cv.pdf", tipo: str = "application/pdf"):
    return {"cv": (nombre, contenido, tipo)}


def test_health_ok_con_api_key(client: TestClient) -> None:
    respuesta = client.get("/api/v1/health")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["proveedor_configurado"] is True


def test_health_degraded_sin_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin credenciales el proceso sigue vivo, pero lo reporta."""
    from app.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    respuesta = TestClient(create_app()).get("/api/v1/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "degraded"


def test_evaluacion_correcta(client: TestClient, pdf_valido: bytes) -> None:
    respuesta = client.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["analisis"]["nombre_candidato"] == "Ana García"
    assert cuerpo["analisis"]["porcentaje_ajuste"] == 85
    assert cuerpo["nivel_ajuste"] == "excelente"
    assert cuerpo["recomendado"] is True


def test_devuelve_request_id(client: TestClient, pdf_valido: bytes) -> None:
    respuesta = client.get("/api/v1/health")

    assert respuesta.headers["X-Request-ID"]


def test_respeta_request_id_del_cliente(client: TestClient) -> None:
    respuesta = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})

    assert respuesta.headers["X-Request-ID"] == "abc-123"


def test_rechaza_tipo_de_archivo_no_pdf(client: TestClient) -> None:
    respuesta = client.post(
        "/api/v1/evaluations",
        files=_archivo(b"texto", nombre="cv.txt", tipo="text/plain"),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 415
    assert respuesta.json()["error_type"] == "UnsupportedMediaType"


def test_pdf_ilegible_devuelve_400(client: TestClient) -> None:
    respuesta = client.post(
        "/api/v1/evaluations",
        files=_archivo(b"no soy un pdf de verdad"),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error_type"] == "PDFExtractionError"


def test_archivo_demasiado_grande_devuelve_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, pdf_valido: bytes
) -> None:
    from app.config import Settings, get_settings

    monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")
    get_settings.cache_clear()
    assert Settings().max_upload_bytes == 10  # el límite se aplicó de verdad

    respuesta = client.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 413
    assert respuesta.json()["error_type"] == "PayloadTooLarge"


def test_descripcion_demasiado_corta_devuelve_422(
    client: TestClient, pdf_valido: bytes
) -> None:
    """FastAPI valida min_length antes de tocar el PDF."""
    respuesta = client.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": "corto"},
    )

    assert respuesta.status_code == 422


def test_falta_el_archivo_devuelve_422(client: TestClient) -> None:
    respuesta = client.post("/api/v1/evaluations", data={"descripcion_puesto": PUESTO})

    assert respuesta.status_code == 422


def test_fallo_del_proveedor_devuelve_502(
    monkeypatch: pytest.MonkeyPatch, pdf_valido: bytes
) -> None:
    from app.api import routes

    def falla(*_args):
        raise EvaluationError("el proveedor no responde")

    monkeypatch.setattr(routes, "evaluar_candidato", falla)
    cliente = TestClient(create_app(), raise_server_exceptions=False)

    respuesta = cliente.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 502
    assert respuesta.json()["error_type"] == "EvaluationError"


def test_falta_de_configuracion_devuelve_503(
    monkeypatch: pytest.MonkeyPatch, pdf_valido: bytes
) -> None:
    from app.api import routes

    def falla(*_args):
        raise ConfigurationError("falta OPENAI_API_KEY")

    monkeypatch.setattr(routes, "evaluar_candidato", falla)
    cliente = TestClient(create_app(), raise_server_exceptions=False)

    respuesta = cliente.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 503


def test_error_inesperado_no_filtra_detalles_internos(
    monkeypatch: pytest.MonkeyPatch, pdf_valido: bytes
) -> None:
    """Un fallo no controlado devuelve 500 genérico, sin traza ni rutas."""
    from app.api import routes

    def falla(*_args):
        raise RuntimeError("secreto interno: /home/app/config con clave sk-real")

    monkeypatch.setattr(routes, "evaluar_candidato", falla)
    cliente = TestClient(create_app(), raise_server_exceptions=False)

    respuesta = cliente.post(
        "/api/v1/evaluations",
        files=_archivo(pdf_valido),
        data={"descripcion_puesto": PUESTO},
    )

    assert respuesta.status_code == 500
    assert "secreto interno" not in respuesta.text
    assert respuesta.json()["detail"] == "Error interno del servidor."


def test_openapi_se_genera(client: TestClient) -> None:
    respuesta = client.get("/openapi.json")

    assert respuesta.status_code == 200
    assert "/api/v1/evaluations" in respuesta.json()["paths"]
