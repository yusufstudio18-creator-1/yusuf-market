# Temel imaj
FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Gereksinimler
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodları kopyala
COPY . .

# Port ve başlatma komutu
ENV PORT 8080
EXPOSE 8080
ENTRYPOINT ["python", "app.py"]