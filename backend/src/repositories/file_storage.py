import uuid
from pathlib import Path

import aiofiles

from ..core.config import settings
from ..core.exceptions import BadRequestError, PayloadTooLargeError


class FileStorageRepository:
    def __init__(self, base_dir: str, chunk_size: int = settings.CHUNK_SIZE):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size

    def new_path(self, extension: str = "") -> Path:
        return self.base_dir / f"{uuid.uuid4()}{extension}"

    async def save_stream(
        self,
        upload,
        destination: Path,
        max_size: int | None = None,
        on_first_chunk=None,
    ) -> int:
        """Стримит загрузку на диск. Возвращает число записанных байт."""
        size = 0
        try:
            async with aiofiles.open(destination, "wb") as f:
                while chunk := await upload.read(self.chunk_size):
                    is_first = size == 0
                    size += len(chunk)
                    if max_size is not None and size > max_size:
                        raise PayloadTooLargeError(
                            f"Файл превышает {max_size // (1024 * 1024)} МБ"
                        )
                    if is_first and on_first_chunk is not None:
                        on_first_chunk(chunk)
                    await f.write(chunk)
            if size == 0:
                raise BadRequestError("Выбран пустой файл")
            return size
        except Exception:
            destination.unlink(missing_ok=True)
            raise