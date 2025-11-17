ARG PYTHON_VERSION=master

FROM quay.io/cdis/python-build-base:${PYTHON_VERSION} AS builder

ENV appname=manifestservice

WORKDIR /${appname}

COPY poetry.lock pyproject.toml /${appname}/

RUN poetry install --without dev --no-interaction --no-root

COPY . /${appname}
COPY ./deployment/wsgi/wsgi.py /${appname}wsgi.py

RUN poetry install --without dev --no-interaction

FROM quay.io/cdis/python-nginx-al:${PYTHON_VERSION} AS final

ENV appname=manifestservice

WORKDIR /${appname}

COPY --from=builder /venv /venv
COPY --from=builder /${appname} /${appname}

RUN chown -R gen3:gen3 /${appname}

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
