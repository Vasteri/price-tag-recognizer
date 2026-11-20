from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from ...schemas.common import TaskQueuedResponse
from ...services.crop_service import CropService
from ..deps import get_crop_service

router = APIRouter(prefix="/crop", tags=["crop"])

CropServiceDep = Annotated[CropService, Depends(get_crop_service)]

@router.post("/upload", response_model=TaskQueuedResponse)
async def upload_crop(file: UploadFile, service: CropServiceDep) -> TaskQueuedResponse:
    task_id = await service.submit(file)
    return TaskQueuedResponse(task_id=task_id)