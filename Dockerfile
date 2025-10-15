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

# Debug: check available Python versions
RUN which -a python python3 python3.13 || true && \
    ls -la /usr/bin/python* || true && \
    ls -la /usr/local/bin/python* || true

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