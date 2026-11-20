from celery.result import AsyncResult

from ..core.celery_app import celery_app


class TaskQueueRepository:
    def send(self, task_name: str, args: list, queue: str) -> str:
        result = celery_app.send_task(task_name, args=args, queue=queue)
        return result.id

    def get(self, task_id: str) -> AsyncResult:
        return celery_app.AsyncResult(task_id)