FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir .

RUN useradd -m onebot
USER onebot

ENTRYPOINT ["onebot"]
CMD ["--help"]
