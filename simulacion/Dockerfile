# Servicio de simulación (entorno de pruebas). Se construye desde la raíz del
# repositorio porque importa el arnés y la red de tsc-thesis/:
#   docker build -f simulacion/Dockerfile .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Bibliotecas de sistema que enlazan los binarios de SUMO y libsumo (aunque no se use la interfaz gráfica).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libx11-6 libxext6 libxrender1 libgl1 libexpat1 libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY simulacion/requirements.txt simulacion/requirements.txt
RUN pip install --no-cache-dir -r simulacion/requirements.txt

# Solo lo que la simulación necesita de la tesis: el arnés y la red del eje.
COPY tsc-thesis/src tsc-thesis/src
COPY tsc-thesis/scenarios/eje_comunal/net.net.xml \
     tsc-thesis/scenarios/eje_comunal/routes.rou.xml \
     tsc-thesis/scenarios/eje_comunal/webster_plan.json \
     tsc-thesis/scenarios/eje_comunal/
COPY simulacion simulacion

ENV TSC_RAIZ=/app/tsc-thesis
WORKDIR /app/simulacion
EXPOSE 8000
CMD ["python", "run.py", "--host", "0.0.0.0"]
