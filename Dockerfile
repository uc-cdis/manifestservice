# To run: docker run -v /path/to/wsgi.py:/var/www/manifestservice/wsgi.py --name=manifestservice -p 81:80 manifestservice
# To check running container: docker exec -it manifestservice /bin/bash

FROM quay.io/cdis/python-nginx:pybase3-1.0.0

ENV appname=manifestservice

# number of uwsgi worker processes
ENV UWSGI_CHEAPER 2

ENV WORKON_HOME=/.venv

RUN apk update \
    && apk add postgresql-libs postgresql-dev libffi-dev libressl-dev \
    && apk add linux-headers musl-dev gcc \
    && apk add curl bash git vim

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/uwsgi/wsgi.py /$appname/wsgi.py
WORKDIR /$appname

RUN python -m pip install --upgrade pip && pip install pipenv && pipenv install

RUN mkdir -p /var/www/$appname \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown nginx -R /var/www/.cache/Python-Eggs/ \
    && chown nginx /var/www/$appname

EXPOSE 80

RUN COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >$appname/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>$appname/version_data.py \
    && python setup.py install

WORKDIR /var/www/$appname

CMD /dockerrun.sh
