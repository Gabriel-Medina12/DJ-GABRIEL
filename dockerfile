# Usa una imagen de Python con FFmpeg
FROM python:3.11-slim-bullseye

# Instalar FFmpeg y dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copiar el código
WORKDIR /app
COPY . .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Comando para iniciar el bot
CMD ["python", "bot.py"]  # <-- Reemplaza "bot.py" con tu archivo