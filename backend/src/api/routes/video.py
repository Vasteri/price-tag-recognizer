from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from ...schemas.common import TaskQueuedResponse
from ...services.video_service import VideoService
from ..deps import get_video_service

router = APIRouter(prefix="/upload", tags=["video"])

VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]

@router.post("", response_model=TaskQueuedResponse)
async def upload_video(file: UploadFile, service: VideoServiceDep) -> TaskQueuedResponse:
    task_id = await service.submit(file)
    return TaskQueuedResponse(task_id=task_id)