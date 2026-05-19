import os
from dotenv import load_dotenv

load_dotenv()

CELERY_NAME = os.getenv("CELERY_NAME", "backend")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/shared/uploads")
RESULT_DIR = os.getenv("RESULT_DIR", "/shared/results")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://host.docker.internal:12434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "ai/qwen3-vl:2B-UD-Q4_K_XL")
ENABLE_OCR = os.getenv("ENABLE_OCR", "false")