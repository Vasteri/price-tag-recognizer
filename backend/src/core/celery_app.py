from celery import Celery

from .config import settings

celery_app = Celery(
    settings.CELERY_NAME,
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
)