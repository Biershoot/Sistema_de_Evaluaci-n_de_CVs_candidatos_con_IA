"""Tests de la extracción de texto de PDFs."""

import pytest

from app.exceptions import PDFExtractionError
from app.services.pdf_processor import extraer_texto_pdf


def test_extrae_texto_de_pdf_valido(pdf_valido: bytes) -> None:
    texto = extraer_texto_pdf(pdf_valido)

    assert "Ana Garcia" in texto
    assert "Python" in texto


def test_marca_los_numeros_de_pagina(pdf_multipagina: bytes) -> None:
    """Las marcas de página dan contexto de estructura al modelo."""
    texto = extraer_texto_pdf(pdf_multipagina)

    assert "--- PÁGINA 1 ---" in texto
    assert "--- PÁGINA 2 ---" in texto
    assert texto.index("Pagina uno") < texto.index("Pagina dos")


def test_trunca_al_limite_de_caracteres(pdf_valido: bytes) -> None:
    texto = extraer_texto_pdf(pdf_valido, max_chars=20)

    assert len(texto) == 20


def test_no_trunca_por_debajo_del_limite(pdf_valido: bytes) -> None:
    completo = extraer_texto_pdf(pdf_valido)
    limitado = extraer_texto_pdf(pdf_valido, max_chars=10_000)

    assert completo == limitado


def test_rechaza_contenido_vacio() -> None:
    with pytest.raises(PDFExtractionError, match="vacío"):
        extraer_texto_pdf(b"")


def test_rechaza_bytes_que_no_son_pdf() -> None:
    with pytest.raises(PDFExtractionError):
        extraer_texto_pdf(b"esto no es un pdf, solo texto plano")


def test_rechaza_pdf_sin_texto_extraible(pdf_sin_texto: bytes) -> None:
    """Un CV escaneado como imagen debe fallar con un mensaje accionable."""
    with pytest.raises(PDFExtractionError, match="escaneados"):
        extraer_texto_pdf(pdf_sin_texto)


def test_rechaza_pdf_con_contrasena(pdf_con_contrasena: bytes) -> None:
    with pytest.raises(PDFExtractionError, match="contraseña"):
        extraer_texto_pdf(pdf_con_contrasena)


def test_lee_pdf_cifrado_sin_contrasena_de_usuario(pdf_solo_restringido: bytes) -> None:
    """Un PDF que solo restringe la impresión sí debe leerse."""
    texto = extraer_texto_pdf(pdf_solo_restringido)

    assert "Ana Garcia" in texto
