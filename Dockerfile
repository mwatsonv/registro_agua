# Imagen base ligera de Python
FROM python:3.11-slim

# Evitar la creación de archivos .pyc y forzar logs inmediatos en consola
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias primero
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Puerto dinámico expuesto por Cloud Run / Render
ENV PORT=8080
EXPOSE 8080

# Comando ajustado a la estructura de tu proyecto
CMD ["sh", "-c", "uvicorn main:app --app-dir cerebro_condominios --host 0.0.0.0 --port ${PORT}"]
