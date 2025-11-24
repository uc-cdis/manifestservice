FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS builder

ENV appname=manifestservice

WORKDIR /${appname}

USER root
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:/usr/sbin:${PATH}"
ENV POETRY_VIRTUALENVS_CREATE=false

COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}wsgi.py

# Refresh lock metadata to satisfy content-hash without updating deps and install once into /venv
RUN poetry lock --no-update --no-interaction && \
    rm -rf /venv/lib*/python3.13/site-packages/click* /venv/bin/click 2>/dev/null || true && \
    poetry install -vv --no-interaction --without dev

FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS final

ENV appname=manifestservice

WORKDIR /${appname}

ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:/usr/sbin:${PATH}"
ENV POETRY_VIRTUALENVS_CREATE=false

USER root
RUN dnf install -y nginx && \
    ln -sf /usr/sbin/nginx /usr/bin/nginx && \
    setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx && \
    mkdir -p /var/run/nginx /var/cache/nginx /var/log/nginx && \
    chown -R gen3:gen3 /var/run/nginx /var/cache/nginx /var/log/nginx && \
    sed -i 's/^user .*/user gen3;/' /etc/nginx/nginx.conf && \
    rm -rf /var/cache/dnf

COPY --from=builder /${appname} /${appname}
COPY --from=builder /venv /venv

USER gen3

CMD ["/manifestservice/dockerrun.bash"]
