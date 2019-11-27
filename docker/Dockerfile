FROM python:3.6

ENV WORKDIR /casepro
WORKDIR ${WORKDIR}

RUN apt update
RUN apt upgrade -y
RUN apt install -y \ 
    varnish \ 
    gettext \ 
    supervisor \
    curl \
    software-properties-common

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash -
RUN apt update
RUN apt install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pip-requires.txt .
COPY pip-freeze.txt .
COPY app-entrypoint.sh .

RUN ls -lash

RUN pip install -r pip-requires.txt
RUN pip install -r pip-freeze.txt
RUN npm install

COPY . .

RUN ln -s $WORKDIR/casepro/settings.py.prod $WORKDIR/casepro/settings.py

EXPOSE 8000
EXPOSE 8080

RUN chmod +x ./app-entrypoint.sh
ENTRYPOINT ["sh", "app-entrypoint.sh"]

# RUN chmod +x ./docker-entrypoint.sh

#CMD ["supervisor"]
