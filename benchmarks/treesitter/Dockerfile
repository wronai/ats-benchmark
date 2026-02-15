FROM python:3.12-slim

WORKDIR /workspace

# Install build dependencies for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY benchmarks/treesitter/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities
COPY benchmarks/common.py /workspace/benchmarks/
COPY sample-app/ /workspace/sample-app/

WORKDIR /workspace
CMD ["python", "benchmarks/treesitter/benchmark.py"]
