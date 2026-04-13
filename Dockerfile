FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AGROX_FAST_TRAIN=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt && pip install gunicorn

COPY . /app

RUN python train_model.py

EXPOSE 7860

CMD ["gunicorn", "wsgi:application", "-c", "gunicorn.conf.py"]
