FROM quay.io/cdis/amazonlinux-base:3.13-pythonbase AS builder

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
FROM quay.io/cdis/amazonlinux-base:3.13-pythonbase AS final

ENV appname=manifestservice

# Install nginx and Poetry (needed by dockerrun.bash)
RUN yum install -y nginx && yum clean all && \
    python3 -m pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Create gen3 user and group with home directory
RUN groupadd -r gen3 && useradd -r -g gen3 -m -d /home/gen3 gen3 && \
    # Give gen3 user permissions for nginx directories
    mkdir -p /var/log/nginx /var/lib/nginx /run && \
    chown -R gen3:gen3 /var/log/nginx /var/lib/nginx /run && \
    chmod -R 755 /var/log/nginx /var/lib/nginx /run

WORKDIR /${appname}

# Copy the installed Python packages from builder
COPY --from=builder /venv /venv

# Copy the application from builder
COPY --from=builder /${appname} /${appname}

RUN chown -R gen3:gen3 /${appname}

# Note: Starting as root to allow nginx to bind to port 80
# Nginx will run worker processes as the configured user
# The application can switch to gen3 user in dockerrun.bash if needed
CMD ["/bin/bash", "-c", "/manifestservice/dockerrun.bash"]
