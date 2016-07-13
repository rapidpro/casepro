FROM praekeltfoundation/django-bootstrap
RUN apt-get-install.sh git libjpeg-dev zlib1g-dev libtiff-dev nodejs npm \
    nginx redis-server supervisor libpq-dev && \
    ln -s /usr/bin/nodejs /usr/bin/node

ENV DJANGO_SETTINGS_MODULE "casepro.settings_production"
ENV APP_MODULE "casepro.wsgi:application"


RUN mkdir -p /etc/supervisor/conf.d/
RUN mkdir -p /var/log/supervisor
RUN rm /etc/nginx/sites-enabled/default

COPY docker/docker-start.sh /scripts/
RUN chmod a+x /scripts/docker-start.sh

COPY docker/nginx.conf /etc/nginx/sites-enabled/molo.conf
COPY docker/supervisor.conf /etc/supervisor/conf.d/molo.conf
COPY docker/supervisord.conf /etc/supervisord.conf

EXPOSE 80

CMD ["docker-start.sh"]

RUN pip install -r pip-freeze.txt
RUN npm install -g less coffee-script
RUN ./manage.py collectstatic --noinput
