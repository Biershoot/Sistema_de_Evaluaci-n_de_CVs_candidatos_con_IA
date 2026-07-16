# Build en dos etapas: las dependencias se compilan en `builder` y solo los
# paquetes resultantes pasan a la imagen final, que no lleva toolchain.
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

# Sin .pyc y con stdout sin buffer: los logs salen en tiempo real al recolector.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# Usuario sin privilegios: si se compromete el proceso, no es root.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /install /usr/local

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser ui/ ./ui/
COPY --chown=appuser:appuser streamlit_app.py ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
