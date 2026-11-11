# Imagem do pipeline para o AWS Lambda (ADR-007). Só tem código e dependências:
# os dados (Referência, modelo, lotes) ficam no S3, e o .dockerignore mantém data/ fora daqui.
# Versões fixadas: a imagem base por digest e as dependências pelo uv.lock.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM public.ecr.aws/lambda/python:3.12@sha256:cdb746c1eb56b61de56e1b5e78f6194392eb00494a1bb257a592852e72d8314b

COPY --from=uv /uv /bin/uv

# Primeiro só o que define as dependências: mudar o código não refaz esta camada, que é a mais lenta.
COPY pyproject.toml uv.lock ./
# --no-emit-package mlflow: o painel do MLflow é local; a função não o usa, e ele pesa na imagem.
RUN uv export --frozen --no-dev --group cloud --no-emit-project --no-emit-package mlflow \
        --format requirements-txt --output-file /tmp/requirements.txt \
    && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt pyproject.toml uv.lock

COPY src/credit_risk_observability "${LAMBDA_TASK_ROOT}/credit_risk_observability"

# No Lambda só /tmp aceita escrita: bibliotecas que guardam cache na pasta do usuário vão para lá.
ENV HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    DO_NOT_TRACK=1

CMD ["credit_risk_observability.cloud.handler.handler"]
