FROM python:3.12-slim as base

ENV PYTHONUNBUFFERED=1 
ENV POETRY_VIRTUALENVS_CREATE=false
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 80

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "80"]
