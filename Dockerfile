ARG AZLINUX_BASE_VERSION=3.13-pythonnginx

# Base stage
FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=manifestservice

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

USER root

RUN chown -R gen3:gen3 /venv/

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

COPY --from=builder /${appname} /${appname}
COPY --from=builder /venv /venv

# OpenShift runs containers with an arbitrary UID in the root group (GID 0),
# so everything the process writes to must be group-writable by GID 0.
# nginx listens on 8080 (unprivileged) using a config without the `user` directive.
USER root
COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf
# Drop nginx's file capability (cap_net_bind_service); restricted SCCs drop all caps
# and the binary would otherwise fail to exec. Not needed on port 8080.
RUN setcap -r /usr/sbin/nginx && \
    mkdir -p /tmp/nginx && \
    chgrp -R 0 /manifestservice /var/lib/nginx /var/log/nginx /tmp/nginx && \
    chmod -R g=u /manifestservice /var/lib/nginx /var/log/nginx /tmp/nginx && \
    chmod g+rx /etc/nginx/nginx.conf

# Arbitrary UIDs have no home dir; gunicorn writes its control socket under $HOME
ENV HOME=/tmp

EXPOSE 8080

# Non-root user; OpenShift will override the UID but keep GID 0
USER 1000:0

CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]
