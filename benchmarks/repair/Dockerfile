FROM python:3.12-slim

WORKDIR /workspace

# Install build tools for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install litellm
RUN pip install --no-cache-dir litellm>=1.44

# Copy workspace
COPY . /workspace/

# Install code2logic + nfo from local source at runtime (mounted volumes)
RUN echo '#!/bin/bash\n\
if [ -d /src/code2logic ]; then\n\
  pip install --no-cache-dir /src/code2logic[full] 2>/dev/null || pip install --no-cache-dir code2logic[full];\n\
else\n\
  pip install --no-cache-dir code2logic[full] 2>/dev/null || true;\n\
fi\n\
if [ -d /src/nfo ]; then\n\
  pip install --no-cache-dir /src/nfo 2>/dev/null || pip install --no-cache-dir nfo;\n\
else\n\
  pip install --no-cache-dir nfo 2>/dev/null || true;\n\
fi\n\
python -m benchmarks.repair.repair_pipeline "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
CMD ["--tool", "all"]
