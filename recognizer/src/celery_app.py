from celery import Celery
from .config import REDIS_URL, CELERY_NAME

celery_app = Celery(
    CELERY_NAME,
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
)