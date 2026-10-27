#!/bin/bash

nginx
exec gunicorn -c "/manifestservice/deployment/wsgi/gunicorn.conf.py"
