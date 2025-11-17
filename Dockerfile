FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS builder

ENV appname=manifestservice

WORKDIR /${appname}

COPY poetry.lock pyproject.toml /${appname}/

RUN poetry install -vv --no-interaction --without dev

COPY . /${appname}
COPY ./deployment/wsgi/wsgi.py /${appname}wsgi.py

RUN poetry install -vv --no-interaction --without dev

ENV PATH="$(poetry env info --path)/bin:$PATH"

FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS final

ENV appname=manifestservice

WORKDIR /${appname}

COPY --from=builder /${appname} /${appname}

RUN chown -R gen3:gen3 /${appname}

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
