from ..core.config import settings
from ..repositories.file_storage import FileStorageRepository
from ..repositories.task_queue import TaskQueueRepository


class VideoService:
    def __init__(self, storage: FileStorageRepository, queue: TaskQueueRepository):
        self.storage = storage
        self.queue = queue

    async def submit(self, upload_file) -> str:
        path = self.storage.new_path(".mp4")
        try:
            await self.storage.save_stream(
                upload_file, path, max_size=settings.MAX_VIDEO_SIZE
            )
        finally:
            await upload_file.close()

        return self.queue.send(
            "recognizer.tasks.process_video",
            args=[str(path)],
            queue="recognizer",
        )