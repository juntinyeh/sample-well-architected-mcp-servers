# Dockerfile for AWS Cost Optimization Agent with Remote MCP Server
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY config.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AWS_REGION=us-east-1
ENV LOG_LEVEL=INFO

# Run the agent
CMD ["python", "main.py"]
