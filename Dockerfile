FROM public.ecr.aws/docker/library/python:3.12-slim

# Copy Lambda Web Adapter (for REST endpoints via Function URL)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set the port uvicorn will listen on
ENV PORT=8000
ENV AWS_LWA_PORT=8000
ENV AWS_LWA_INVOKE_MODE=response_stream

WORKDIR /var/task

# Install dependencies (includes awslambdaric for WS Lambda)
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy application code
COPY backend/ backend/
COPY skills/ skills/
COPY department-resources/ department-resources/

# Default CMD: REST Lambda via Lambda Web Adapter + uvicorn
# The WS Lambda overrides CMD in CDK to use awslambdaric directly:
#   CMD ["python", "-m", "awslambdaric", "backend.lambda_ws.handler"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
