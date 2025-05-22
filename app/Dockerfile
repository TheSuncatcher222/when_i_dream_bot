FROM python:3.12-slim

LABEL description="When I Dream Bot" \
      version="1.0" \
      maintainer="https://github.com/TheSuncatcher222/"

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

COPY . .
