FROM public.ecr.aws/lambda/python:3.12

# Copy Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set the port uvicorn will listen on (Lambda Web Adapter forwards to this)
ENV PORT=8000
ENV AWS_LWA_PORT=8000

WORKDIR /var/task

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy application code
COPY backend/ backend/

# Lambda Web Adapter entrypoint - run uvicorn as a regular process
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
