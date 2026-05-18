FROM ultralytics/ultralytics:8.4.51

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install openai

COPY ./src ./src

ENV PYTHONPATH=/app

CMD ["celery", "-A", "src.tasks", "worker", "--loglevel=info", "-Q", "recognizer"]