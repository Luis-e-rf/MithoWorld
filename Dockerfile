# 1. Imagen base oficial
FROM python:3.12-slim-bookworm

# 2. Variables de entorno de rendimiento y seguridad
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# 3. Actualizar paquetes del SO existentes (corrige las vulnerabilidades H/M) 
#    e instalar dependencias mínimas de PostgreSQL y compilación
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. Obtener el binario oficial de uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 5. Instalar dependencias del proyecto (con caché de capas)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 6. Eliminar el compilador gcc tras instalar dependencias (reduce superficie de ataque)
RUN apt-get purge -y gcc && apt-get autoremove -y

# 7. Crear un usuario de sistema sin privilegios de root (principio de menor privilegio)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/media /app/staticfiles && \
    chown -R appuser:appuser /app

# 8. Copiar el código fuente y transferir propiedad al appuser
COPY --chown=appuser:appuser . .

# 9. Cambiar a usuario no-root
USER appuser

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2"]