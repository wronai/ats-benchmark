FROM python:3.12-slim

WORKDIR /workspace

# Install build dependencies for local package installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install litellm and build tools first
RUN pip install --no-cache-dir setuptools wheel litellm>=1.44

# Copy workspace
COPY . /workspace/

# Install nfo from local source (mounted at /src/nfo at runtime)
# Fallback: pip install from PyPI during docker run if local not available
RUN echo '#!/bin/bash\n\
if [ -d /src/nfo ]; then\n\
  pip install --no-cache-dir /src/nfo 2>/dev/null || pip install --no-cache-dir nfo;\n\
else\n\
  pip install --no-cache-dir nfo;\n\
fi\n\
python -m benchmarks.nfo.benchmark' > /entrypoint.sh && chmod +x /entrypoint.sh

CMD ["/bin/bash", "/entrypoint.sh"]
