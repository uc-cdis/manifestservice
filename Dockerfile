# To run: docker run -v /path/to/wsgi.py:/var/www/manifestservice/wsgi.py --name=manifestservice -p 81:80 manifestservice
# To check running container: docker exec -it manifestservice /bin/bash

FROM quay.io/cdis/python:python3.9-buster-2.0.0

ENV appname=manifestservice

RUN pip install --upgrade pip

# install poetry
RUN pip install --upgrade poetry

RUN apt-get update \
    && apt-get install -y --no-install-recommends\
    libmcrypt4 libmhash2 mcrypt \
    curl bash git \
    && apt-get clean

RUN mkdir -p /var/www/$appname \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown nginx -R /var/www/.cache/Python-Eggs/ \
    && chown nginx /var/www/$appname

EXPOSE 80

WORKDIR /$appname

# copy ONLY poetry artifact and install
# this will make sure than the dependencies is cached
COPY poetry.lock pyproject.toml /$appname/
RUN poetry config virtualenvs.create false \
    && poetry install -vv --no-root --no-dev --no-interaction \
    && poetry show -v

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/uwsgi/wsgi.py /$appname/wsgi.py

# install Indexd and dependencies via poetry
RUN poetry config virtualenvs.create false \
    && poetry install -vv --no-dev --no-interaction \
    && poetry show -v

RUN COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >$appname/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>$appname/version_data.py

WORKDIR /var/www/$appname

CMD /dockerrun.sh
