import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    CELERY_NAME: str = os.getenv("CELERY_NAME", "backend")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/shared/uploads")
    RESULT_DIR: str = os.getenv("RESULT_DIR", "/shared/results")

    CHUNK_SIZE: int = 1024 * 1024
    MAX_VIDEO_SIZE: int | None = None          # без ограничения
    MAX_CROP_SIZE: int = 20 * 1024 * 1024      # 20 МБ


settings = Settings()