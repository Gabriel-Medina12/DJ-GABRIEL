# Usa una imagen con Python y FFmpeg
FROM python:3.11-slim-bullseye

# Instalar FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copiar el código
WORKDIR /app
COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Comando para iniciar el bot
CMD ["python", "bot.py"]  # <-- Reemplaza "bot.py" con tu archivo