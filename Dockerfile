# Imagen base oficial de Python
FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc en disco
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Exponer el puerto que asigna Cloud Run (por defecto 8080)
EXPOSE 8080

# Comando para arrancar FastAPI en producción
CMD ["uvicorn", "cerebro_condominios.main:app", "--host", "0.0.0.0", "--port", "8080"]
