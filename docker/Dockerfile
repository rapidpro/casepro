FROM python:3.6-alpine

ENV PYTHONUNBUFFERED 1
WORKDIR /app

RUN apk update \
  && apk add --virtual build-deps gcc python3-dev musl-dev \
  && apk add postgresql-client postgresql-dev libxml2-dev libxslt-dev gettext-dev \
  && apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev \
  && apk add libffi-dev py-cffi gettext nodejs npm git build-base

RUN addgroup -S django \
  && adduser -S -G django django

RUN npm install --global --unsafe-perm \
  coffeescript \
  less

COPY ./pip-freeze.txt /app
COPY ./package.json /app

RUN pip install --no-cache-dir -r pip-freeze.txt
RUN npm install

COPY . .

RUN ln -s /app/casepro/settings.py_prod /app/casepro/settings.py

RUN chmod +x app-entrypoint.sh

RUN chown -R django /app
USER django

EXPOSE 8000
ENTRYPOINT ["sh", "app-entrypoint.sh"]
