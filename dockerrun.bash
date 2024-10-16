#!/bin/bash

nginx
gunicorn -c "/manifestservice/deployment/wsgi/gunicorn.conf.py"
