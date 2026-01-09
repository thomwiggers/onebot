FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for caching
COPY pyproject.toml uv.lock /app/
RUN uv pip install --no-cache-dir --system -r pyproject.toml

# Copy application and install it
COPY . /app
RUN uv pip install --no-cache-dir --system .

RUN useradd -m onebot && mkdir /config && chown onebot:onebot /config
USER onebot

ENTRYPOINT ["onebot"]
CMD ["/config/config.ini"]
