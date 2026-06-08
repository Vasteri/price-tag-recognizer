from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
import uuid
import os

from .config import UPLOAD_DIR, RESULT_DIR
from .celery_app import celery_app

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
app = FastAPI(root_path="/api")
Instrumentator().instrument(app).expose(app)

@app.post("/upload")
async def upload_video(file: UploadFile):
    # Сохраняем загруженное видео
    video_id = str(uuid.uuid4())
    video_path = f"{UPLOAD_DIR}/{video_id}.mp4"
    with open(video_path, "wb") as f:
        f.write(await file.read())
    
    task = celery_app.send_task('recognizer.tasks.process_video', args=[video_path], queue='recognizer')
    
    return {"task_id": task.id, "status": "queued"}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    task = celery_app.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {'state': 'PENDING', 'progress': 0}
    elif task.state == 'PROCESSING':
        response = {'state': 'PROCESSING', 'progress': task.info.get('progress', 0)}
    else:
        response = {'state': task.state, 'result': task.result}
    return response

@app.get("/download/{task_id}")
def download(task_id: str):
    task = celery_app.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        csv_path = task.result.get('csv_path')
        filename = os.path.basename(csv_path)
        return FileResponse(csv_path, filename=filename)
    return {"error": "Not ready"}
