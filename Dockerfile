FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS builder

ENV appname=manifestservice

WORKDIR /${appname}

USER gen3

COPY --chown=gen3:gen3 poetry.lock pyproject.toml /${appname}/

# Unset VIRTUAL_ENV to force Poetry to create a new project-local venv
RUN unset VIRTUAL_ENV && \
    poetry config virtualenvs.in-project true --local && \
    poetry install -vv --no-interaction --without dev

COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}wsgi.py

RUN unset VIRTUAL_ENV && poetry install -vv --no-interaction --without dev

ENV PATH="/manifestservice/.venv/bin:$PATH"

FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS final

ENV appname=manifestservice

WORKDIR /${appname}

COPY --from=builder /${appname} /${appname}

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
