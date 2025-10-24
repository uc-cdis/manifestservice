ARG PYTHON_VERSION=feat_python3.13-alias

FROM quay.io/cdis/python-build-base:${PYTHON_VERSION} AS builder

ENV appname=manifestservice

# Install Poetry as root
RUN python3 -m pip install --no-cache-dir poetry

WORKDIR /${appname}

# Copy dependency files and install as root (before switching to gen3)
COPY poetry.lock pyproject.toml /${appname}/

# Configure poetry to not create virtual environments and install dependencies as root
RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-root

# Now create gen3 user and switch to it
RUN groupadd -r gen3 && useradd -r -g gen3 -m -d /home/gen3 gen3 && \
    chown -R gen3:gen3 /${appname}

USER gen3

# Copy application code
COPY --chown=gen3:gen3 . /${appname}
COPY --chown=gen3:gen3 ./deployment/wsgi/wsgi.py /${appname}wsgi.py

# Install the manifestservice package itself (as gen3, but dependencies already installed)
USER root
RUN poetry install --without dev --no-interaction
USER gen3

RUN git config --global --add safe.directory /${appname} && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" > /${appname}/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >> /${appname}/version_data.py

# Final stage - also use python-build-base since python-nginx-al doesn't have Python 3.13
FROM quay.io/cdis/python-build-base:${PYTHON_VERSION} AS final

ENV appname=manifestservice

# Create gen3 user and group with home directory
RUN groupadd -r gen3 && useradd -r -g gen3 -m -d /home/gen3 gen3

WORKDIR /${appname}

COPY --from=builder /${appname} /${appname}

RUN chown -R gen3:gen3 /${appname}

# Switch to non-root user 'gen3' for the serving process
USER gen3

CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]