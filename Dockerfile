FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output

ENV TZ=UTC PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]