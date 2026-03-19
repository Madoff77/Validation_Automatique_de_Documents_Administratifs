FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-télécharger le modèle TrOCR pendant le build (évite tout accès réseau au runtime)
# ENV TRANSFORMERS_CACHE=/root/.cache/huggingface
# RUN python -c "\
# from transformers import TrOCRProcessor, VisionEncoderDecoderModel; \
# TrOCRProcessor.from_pretrained('microsoft/trocr-base-printed'); \
# VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-printed'); \
# print('TrOCR model cached.')"

COPY . .

RUN mkdir -p /app/models/trained

# Variables d'environnement par défaut
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
