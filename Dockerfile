FROM python:3.12-slim

# Evitar escritura de archivos .pyc y activar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Directorio de datos persistentes para SQLite
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "bot.py"]
