FROM ultralytics/ultralytics:8.4.51

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/download_model.py .
RUN python download_model.py

COPY ./src ./src
COPY ./assets ./assets

CMD ["celery", "-A", "src.tasks", "worker", "--loglevel=info", "-Q", "recognizer"]