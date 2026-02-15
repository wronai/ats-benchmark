FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir litellm>=1.44

# Copy workspace
COPY . /workspace/

CMD ["python", "-m", "benchmarks.baseline.benchmark"]
