FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# TLS inceleyen kurumsal ağlar için ek kök sertifikalar (bkz. certs/README.md).
# Dizin yalnızca README içeriyorsa bu adım hiçbir şey değiştirmez.
COPY certs/ /usr/local/share/ca-certificates/kavun/
RUN cat /usr/local/share/ca-certificates/kavun/*.crt >> /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıklar önce kurulur — kaynak değişince katman yeniden kullanılır.
COPY pyproject.toml README.md ./
RUN mkdir -p app tools && touch app/__init__.py tools/__init__.py \
    && pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
