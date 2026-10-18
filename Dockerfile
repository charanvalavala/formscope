FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY static ./static
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn formscope.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
