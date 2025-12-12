ARG AZLINUX_BASE_VERSION=3.13-pythonnginx

# Base stage
FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=manifestservice

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

USER gen3

# Unset base image's VIRTUAL_ENV and configure poetry to create venv in project directory
ENV VIRTUAL_ENV=
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_VIRTUALENVS_CREATE=true

# copy ONLY poetry artifact, install the dependencies but not the app
# this will make sure that the dependencies are cached
COPY poetry.lock pyproject.toml /${appname}/
RUN poetry install -vv --no-root --only main --no-interaction

# Move app files into working directory
COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}/wsgi.py

# install the app
RUN poetry install --without dev --no-interaction

# Final stage

FROM base

ENV appname=manifestservice
ENV PATH="/${appname}/.venv/bin:/usr/sbin:${PATH}"

COPY --from=builder /${appname} /${appname}

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
