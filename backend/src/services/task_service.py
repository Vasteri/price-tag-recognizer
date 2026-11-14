from pathlib import Path

from ..core.exceptions import TaskNotReadyError
from ..repositories.task_queue import TaskQueueRepository


class TaskService:
    def __init__(self, queue: TaskQueueRepository):
        self.queue = queue

    def get_status(self, task_id: str) -> dict:
        task = self.queue.get(task_id)
        if task.state == "PENDING":
            return {"state": "PENDING", "progress": 0}
        if task.state == "PROCESSING":
            return {"state": "PROCESSING", "progress": task.info.get("progress", 0)}
        return {"state": task.state, "result": task.result}

    def get_result_path(self, task_id: str) -> Path:
        task = self.queue.get(task_id)
        if task.state != "SUCCESS":
            raise TaskNotReadyError()
        return Path(task.result["csv_path"])