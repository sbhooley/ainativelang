# AINL emitted server (build from server dir: docker compose up --build)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt server.py ir.json runtime.py ./
COPY adapters ./adapters/
COPY static ./static/
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8765
ENV PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
