FROM python:3.12-slim

WORKDIR /workspace

# Install Node.js for ast-grep
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install ast-grep globally via npm
RUN npm install -g @ast-grep/cli

# Install Python dependencies
COPY benchmarks/astgrep/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities
COPY benchmarks/common.py /workspace/benchmarks/
COPY sample-app/ /workspace/sample-app/

WORKDIR /workspace
CMD ["python", "benchmarks/astgrep/benchmark.py"]
