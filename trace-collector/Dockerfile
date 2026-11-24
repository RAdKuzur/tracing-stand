FROM python:3.11-slim
WORKDIR /app
COPY app.py .
COPY src ./src
COPY tests ./tests
EXPOSE 4318
CMD ["python", "app.py"]