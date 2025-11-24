FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS builder

ENV appname=manifestservice

WORKDIR /${appname}

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

USER root
RUN dnf install -y nginx && \
    ln -sf /usr/sbin/nginx /usr/bin/nginx && \
    rm -rf /var/cache/dnf

COPY --from=builder /${appname} /${appname}

# Set PATH to use project-local venv and unset conflicting VIRTUAL_ENV
ENV PATH="/manifestservice/.venv/bin:$PATH" \
    VIRTUAL_ENV=""

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
