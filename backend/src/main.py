from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
import uuid
import os
from pathlib import Path

from .config import UPLOAD_DIR, RESULT_DIR
from .celery_app import celery_app

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
app = FastAPI(root_path="/api")
Instrumentator().instrument(app).expose(app)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

@app.post("/upload")
async def upload_video(file: UploadFile):
    # Сохраняем загруженное видео
    video_id = str(uuid.uuid4())
    video_path = f"{UPLOAD_DIR}/{video_id}.mp4"
    with open(video_path, "wb") as f:
        f.write(await file.read())
    
    task = celery_app.send_task('recognizer.tasks.process_video', args=[video_path], queue='recognizer')
    
    return {"task_id": task.id, "status": "queued"}


@app.post("/crop/upload")
async def upload_crop(file: UploadFile):
    extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extension = extensions.get(file.content_type)
    if extension is None:
        await file.close()
        raise HTTPException(415, "Поддерживаются только JPEG, PNG и WebP.")

    image_path = Path(UPLOAD_DIR) / f"{uuid.uuid4()}{extension}"
    try:
        size = 0
        with image_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise HTTPException(413, "Изображение превышает 20 МБ.")
                if size == len(chunk):
                    valid_header = {
                        "image/jpeg": chunk.startswith(b"\xff\xd8\xff"),
                        "image/png": chunk.startswith(b"\x89PNG\r\n\x1a\n"),
                        "image/webp": chunk.startswith(b"RIFF") and chunk[8:12] == b"WEBP",
                    }[file.content_type]
                    if not valid_header:
                        raise HTTPException(415, "Содержимое файла не соответствует формату изображения.")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "Выбран пустой файл.")

        # The worker will decode the image and perform OCR/VLM/QR recognition.
        task = celery_app.send_task(
            "recognizer.tasks.process_crop", args=[str(image_path)], queue="recognizer"
        )
    except Exception:
        image_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

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
