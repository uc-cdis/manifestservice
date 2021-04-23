# To run: docker run -v /path/to/wsgi.py:/var/www/manifestservice/wsgi.py --name=manifestservice -p 81:80 manifestservice
# To check running container: docker exec -it manifestservice /bin/bash

FROM quay.io/cdis/python-nginx:pybase3-1.5.0

ENV appname=manifestservice

RUN pip install --upgrade pip

RUN apk add --update \
    postgresql-libs postgresql-dev libffi-dev openssl-dev \
    linux-headers musl-dev gcc \
    curl bash git vim

RUN mkdir -p /var/www/$appname \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown nginx -R /var/www/.cache/Python-Eggs/ \
    && chown nginx /var/www/$appname

EXPOSE 80

# install poetry
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/uwsgi/wsgi.py /$appname/wsgi.py
WORKDIR /$appname

# cache so that poetry install will run if these files change
COPY poetry.lock pyproject.toml /$appname/

# install Indexd and dependencies via poetry
RUN source $HOME/.poetry/env \
    && poetry config virtualenvs.create false \
    && poetry install -vv --no-dev --no-interaction \
    && poetry show -v

RUN COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >$appname/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>$appname/version_data.py

WORKDIR /var/www/$appname

CMD /dockerrun.sh
