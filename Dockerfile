ARG AZLINUX_BASE_VERSION=feat_py3.13_hardened

# Base stage with python-build-base
FROM quay.io/cdis/python-nginx-al:${AZLINUX_BASE_VERSION} AS base

ENV appname=manifestservice

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

USER gen3

COPY poetry.lock pyproject.toml /${appname}/

# Debug: comprehensive Python version check
RUN echo "=== Python version ===" && \
    python3 --version && \
    echo "=== Searching for python3.13 ===" && \
    find /usr -name "python3.13*" 2>/dev/null || echo "No python3.13 found" && \
    echo "=== All Python binaries in /usr/bin ===" && \
    ls -la /usr/bin/python* && \
    echo "=== All Python binaries in /usr/local/bin ===" && \
    ls -la /usr/local/bin/python* 2>/dev/null || echo "No python in /usr/local/bin" && \
    echo "=== Checking /opt ===" && \
    ls -la /opt/python* 2>/dev/null || echo "No python in /opt" && \
    echo "=== Python paths ===" && \
    python3 -c "import sys; print(sys.version); print(sys.executable)"

RUN poetry export -f requirements.txt --output requirements.txt --without dev --without-hashes && \
    python3.13 -m pip install --no-cache-dir -r requirements.txt

COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}wsgi.py

# Install the manifestservice package itself
RUN python3.13 -m pip install --no-cache-dir -e .

RUN git config --global --add safe.directory /${appname} && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" > /${appname}/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >> /${appname}/version_data.py

# Final stage
FROM base

COPY --from=builder /${appname} /${appname}

# Switch to non-root user 'gen3' for the serving process
USER gen3

CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]