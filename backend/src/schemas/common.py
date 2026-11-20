from pydantic import BaseModel
from typing import Any


class HealthResponse(BaseModel):
    status: str = "ok"


class TaskQueuedResponse(BaseModel):
    task_id: str
    status: str = "queued"


class TaskStatusResponse(BaseModel):
    state: str
    progress: int | None = None
    result: Any = None