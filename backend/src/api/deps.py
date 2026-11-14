from functools import lru_cache

from ..core.config import settings
from ..repositories.file_storage import FileStorageRepository
from ..repositories.task_queue import TaskQueueRepository
from ..services.crop_service import CropService
from ..services.task_service import TaskService
from ..services.video_service import VideoService


@lru_cache
def get_storage() -> FileStorageRepository:
    return FileStorageRepository(settings.UPLOAD_DIR)


@lru_cache
def get_queue() -> TaskQueueRepository:
    return TaskQueueRepository()


def get_video_service() -> VideoService:
    return VideoService(get_storage(), get_queue())


def get_crop_service() -> CropService:
    return CropService(get_storage(), get_queue())


def get_task_service() -> TaskService:
    return TaskService(get_queue())