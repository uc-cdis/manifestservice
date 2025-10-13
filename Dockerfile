ARG AZLINUX_BASE_VERSION=master

# Base stage with python-build-base
FROM quay.io/cdis/python-nginx-al:${AZLINUX_BASE_VERSION} AS base

ENV appname=manifestservice

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

# Install Python 3.13 from source as root
USER root

RUN yum install -y wget gcc make tar openssl-devel bzip2-devel libffi-devel zlib-devel && \
    wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz && \
    tar -xzf Python-3.13.0.tgz && \
    cd Python-3.13.0 && \
    ./configure --enable-optimizations && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.13.0 Python-3.13.0.tgz && \
    yum clean all

# Switch back to gen3 user
USER gen3

COPY poetry.lock pyproject.toml /${appname}/

# Configure poetry to use Python 3.13 and install dependencies
RUN poetry env use python3.13 && \
    poetry install -vv --without dev --no-interaction

COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}wsgi.py

# Run poetry again so this app itself gets installed too
RUN poetry install --without dev --no-interaction

RUN git config --global --add safe.directory /${appname} && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" > /${appname}/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >> /${appname}/version_data.py

# Final stage
FROM base

COPY --from=builder /${appname} /${appname}

# Switch to non-root user 'gen3' for the serving process
USER gen3

CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]
