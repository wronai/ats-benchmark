FROM python:3.12-slim

WORKDIR /workspace

COPY benchmarks/baseline/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy workspace
COPY . /workspace/

CMD ["python", "-m", "benchmarks.baseline.benchmark"]
