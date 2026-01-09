FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir .

RUN useradd -m onebot && mkdir /config && chown onebot:onebot /config
USER onebot

ENTRYPOINT ["onebot"]
CMD ["/config/config.ini"]
