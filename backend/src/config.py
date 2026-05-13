import os
from dotenv import load_dotenv

load_dotenv()

CELERY_NAME = os.getenv("CELERY_NAME", "backend")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/shared/uploads")
RESULT_DIR = os.getenv("RESULT_DIR", "/shared/results")