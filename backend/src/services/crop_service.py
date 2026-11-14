from ..core.config import settings
from ..core.exceptions import UnsupportedMediaTypeError
from ..repositories.file_storage import FileStorageRepository
from ..repositories.task_queue import TaskQueueRepository

_EXTENSION_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_MAGIC_CHECK = {
    "image/jpeg": lambda head: head.startswith(b"\xff\xd8\xff"),
    "image/png": lambda head: head.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda head: head.startswith(b"RIFF") and head[8:12] == b"WEBP",
}


class CropService:
    def __init__(self, storage: FileStorageRepository, queue: TaskQueueRepository):
        self.storage = storage
        self.queue = queue

    async def submit(self, upload_file) -> str:
        content_type = upload_file.content_type
        extension = _EXTENSION_BY_TYPE.get(content_type)
        if extension is None:
            await upload_file.close()
            raise UnsupportedMediaTypeError(
                "Поддерживаются только JPEG, PNG и WebP"
            )

        magic_check = _MAGIC_CHECK[content_type]

        def validate_header(head: bytes) -> None:
            if not magic_check(head):
                raise UnsupportedMediaTypeError(
                    "Содержимое файла не соответствует формату изображения"
                )

        path = self.storage.new_path(extension)
        try:
            await self.storage.save_stream(
                upload_file,
                path,
                max_size=settings.MAX_CROP_SIZE,
                on_first_chunk=validate_header,
            )
        finally:
            await upload_file.close()

        return self.queue.send(
            "recognizer.tasks.process_crop",
            args=[str(path)],
            queue="recognizer",
        )