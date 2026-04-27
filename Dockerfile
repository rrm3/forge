FROM public.ecr.aws/docker/library/python:3.12-slim

# Copy Lambda Web Adapter (for REST endpoints via Function URL)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set the port uvicorn will listen on
ENV PORT=8000
ENV AWS_LWA_PORT=8000
ENV AWS_LWA_INVOKE_MODE=response_stream

WORKDIR /var/task

# Install uv (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# Install dependencies from lockfile (copy these first for Docker layer caching)
# Point uv's venv at the system Python so installed binaries are on PATH
ENV UV_PROJECT_ENVIRONMENT="/usr/local"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY backend/ backend/
COPY skills/ skills/
COPY department-resources/ department-resources/
# backend/storage.py::load_pulse_config reads pulse-survey definitions
# from <lambda_root>/config/pulse-surveys.json. Without this COPY the
# config silently resolves to an empty list, pulse_to_ask is empty, the
# rendered Pulse section is omitted from the wrapup prompt entirely, and
# the wrap-up agent freelances its own 1-5 questions. Root cause of all
# Week 5+ pulse contamination.
COPY config/pulse-surveys.json config/pulse-surveys.json

# Default CMD: REST Lambda via Lambda Web Adapter + uvicorn
# The WS Lambda overrides CMD in CDK to use awslambdaric directly:
#   CMD ["python", "-m", "awslambdaric", "backend.lambda_ws.handler"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
