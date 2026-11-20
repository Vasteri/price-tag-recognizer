from fastapi import APIRouter

from .routes import crop, health, tasks, video

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(video.router)
api_router.include_router(crop.router)
api_router.include_router(tasks.router)