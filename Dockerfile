FROM python:3.11-slim-bullseye

# Instalar dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libffi-dev \
    libnacl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Expón el puerto (opcional pero recomendado)
EXPOSE 8080

CMD ["python", "bot.py"]