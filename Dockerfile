# Production Container for TriCoach AI Web Server
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.web_server:app --host 0.0.0.0 --port ${PORT}"]
