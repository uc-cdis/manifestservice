ARG AZLINUX_BASE_VERSION=3.13-pythonnginx

# Base stage
FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=manifestservice

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

USER gen3

COPY poetry.lock pyproject.toml /${appname}/

RUN poetry install -vv --without dev --no-interaction

COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}/wsgi.py

# Run poetry again so this app itself gets installed too
RUN poetry install --without dev --no-interaction

# Final stage
FROM base

ENV PATH="/usr/sbin:${PATH}"

COPY --from=builder /${appname} /${appname}
COPY --from=builder /venv /venv

USER gen3

CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]
