#!/bin/bash

echo "Collect static files"
python /app/manage.py collectstatic --noinput

echo "Compress static files"
python /app/manage.py compress --extension=.haml,.html

echo "Compile messages"
python /app/manage.py compilemessages

echo "Starting server"
/usr/local/bin/gunicorn casepro.wsgi:application -t 120 -w 2 --max-requests 5000 -b 0.0.0.0:8000

#echo "Starting server"
#python manage.py runserver 127.0.0.0:8000
