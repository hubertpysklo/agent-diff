FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./

RUN uv pip install --system -r pyproject.toml

COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.src.platform.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
