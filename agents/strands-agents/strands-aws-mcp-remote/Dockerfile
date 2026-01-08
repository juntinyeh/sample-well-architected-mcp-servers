FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install AWS OpenTelemetry for observability
RUN pip install --no-cache-dir aws-opentelemetry-distro>=0.10.1

# Set AWS environment variables
ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1

# Signal Docker environment
ENV DOCKER_CONTAINER=1

# MCP Server configuration (to be overridden by environment)
ENV AWS_MCP_SERVER_URL=""

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# Expose ports
EXPOSE 8080
EXPOSE 8000

# Copy application code (respecting .dockerignore)
COPY --chown=bedrock_agentcore:bedrock_agentcore . .

# Run with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "main"]
