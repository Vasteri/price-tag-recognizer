from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ...schemas.common import TaskStatusResponse
from ...services.task_service import TaskService
from ..deps import get_task_service

router = APIRouter(tags=["tasks"])

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_status(task_id: str, service: TaskServiceDep) -> TaskStatusResponse:
    return TaskStatusResponse(**service.get_status(task_id))


@router.get("/download/{task_id}")
def download(task_id: str, service: TaskServiceDep) -> FileResponse:
    path = service.get_result_path(task_id)
    return FileResponse(path, filename=path.name)