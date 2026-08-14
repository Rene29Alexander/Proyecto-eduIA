# ============================================================
# EduIA — Dockerfile
# Imagen para la API FastAPI (servicio de IA)
# ============================================================

# Imagen base oficial Python 3.11 slim
FROM python:3.11-slim

# Metadatos
LABEL maintainer="Grupo 2 - EduIA"
LABEL description="API REST inteligente de EduIA con FastAPI y Google Gemini"
LABEL version="1.0.0"

# Variables de entorno del contenedor
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar solo requirements primero (optimiza cache de capas)
COPY requirements-test.txt .

# Instalar dependencias
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-test.txt

# Copiar el código fuente necesario para la API
COPY api.py .
COPY config.py .
COPY database.py .
COPY utils_ai.py .
COPY models/ ./models/
COPY evaluacion/ ./evaluacion/

# Crear directorio para la base de datos SQLite
RUN mkdir -p /app/data

# Puerto expuesto
EXPOSE 8000

# Healthcheck: verifica que la API responde
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando de inicio
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
