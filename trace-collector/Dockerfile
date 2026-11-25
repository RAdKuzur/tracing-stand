FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY src ./src
COPY config ./config
RUN mkdir -p /data
EXPOSE 4318
CMD ["python", "app.py"]