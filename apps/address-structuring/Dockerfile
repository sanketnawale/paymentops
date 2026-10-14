# syntax=docker/dockerfile:1
# CloudNova PaymentOps - address-structuring internal service.
# Runs the vendored upstream (Swift-SC/iso20022-address-structuring) engine. Heavy inference
# deps (torch) are isolated here, NOT in the core API image. Resources are mounted at
# /resources at runtime.
# Build context MUST be the repository root:
#   docker build -f apps/address-structuring/Dockerfile -t paymentops-address-structuring:dev .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /build

# Vendored upstream package (pinned commit) + service code + resources.
COPY third_party/swift-address ./swift-address
COPY third_party/swift-address-resources ./swift-resources
COPY apps/address-structuring ./addr-service
COPY tools/address-data ./addr-tools

# Install CPU-only torch first (avoids pulling the multi-GB CUDA wheel).
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.8.0" \
    && /opt/venv/bin/pip install ./swift-address \
    && /opt/venv/bin/pip install "fastapi>=0.115" "uvicorn[standard]>=0.32"

# Build the bundled DEVELOPMENT reference dataset (reproducible, small) + vendor model/misc.
# This is a reduced dev corpus (not the production GeoNames/restCountries corpus).
RUN /opt/venv/bin/python addr-tools/generate_dev_reference.py --out /bundled-resources \
    && mkdir -p /bundled-resources/models \
    && cp swift-resources/models/* /bundled-resources/models/ \
    && cp swift-resources/misc/* /bundled-resources/misc/

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DS_PREFIX_FOLDER_PATH=/resources

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=base /opt/venv /opt/venv
COPY --from=base --chown=appuser:appgroup /build/addr-service/service /srv/service
# Bundled dev reference data (seeded into the PVC by an initContainer).
COPY --from=base --chown=appuser:appgroup /bundled-resources /bundled-resources

WORKDIR /srv

USER appuser

EXPOSE 8000

# The reference data is seeded into the mounted /resources volume by an initContainer.
CMD ["sh", "-c", "cd /srv && uvicorn service.main:app --host 0.0.0.0 --port 8000"]
