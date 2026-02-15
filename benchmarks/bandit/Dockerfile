FROM python:3.12-slim

WORKDIR /workspace

# Install Python dependencies
COPY benchmarks/bandit/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities
COPY benchmarks/common.py /workspace/benchmarks/
COPY sample-app/ /workspace/sample-app/

WORKDIR /workspace
CMD ["python", "benchmarks/bandit/benchmark.py"]
