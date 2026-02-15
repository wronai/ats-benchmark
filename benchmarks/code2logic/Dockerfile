FROM python:3.12-slim

WORKDIR /workspace

# Install build tools for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install code2logic from local source if available, else from pip
COPY benchmarks/code2logic/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy workspace
COPY . /workspace/

CMD ["python", "-m", "benchmarks.code2logic.benchmark"]
