#!/bin/bash

nginx
poetry run gunicorn -c "/manifestservice/deployment/wsgi/gunicorn.conf.py"
