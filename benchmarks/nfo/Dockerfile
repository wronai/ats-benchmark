FROM python:3.12-slim

WORKDIR /workspace

# Install nfo from local source if available, else from pip
COPY benchmarks/nfo/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy workspace
COPY . /workspace/

CMD ["python", "-m", "benchmarks.nfo.benchmark"]
