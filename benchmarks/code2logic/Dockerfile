FROM python:3.12-slim

WORKDIR /workspace

# Install build tools for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install litellm and build tools first
RUN pip install --no-cache-dir setuptools wheel litellm>=1.44

# Copy workspace
COPY . /workspace/

# Install code2logic from local source (mounted at /src/code2logic at runtime)
# Fallback: pip install from PyPI during docker run if local not available
RUN echo '#!/bin/bash\n\
if [ -d /src/code2logic ]; then\n\
  pip install --no-cache-dir /src/code2logic[full] || pip install --no-cache-dir code2logic[full];\n\
else\n\
  pip install --no-cache-dir code2logic[full];\n\
fi\n\
python -m benchmarks.code2logic.benchmark' > /entrypoint.sh && chmod +x /entrypoint.sh

CMD ["/bin/bash", "/entrypoint.sh"]
