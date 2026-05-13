import pandas as pd
from time import sleep

from .config import UPLOAD_DIR, RESULT_DIR
from .celery_app import celery_app

@celery_app.task(bind=True, name='recognizer.tasks.process_video')
def process_video(self, video_path: str):
    # Обновляем прогресс
    self.update_state(state='PROCESSING', meta={'progress': 0})

    # пайплайн
    results = [video_path.split('/')[-1].split('.')[0]]
    for i in range(10 * 2):
        sleep(0.5)    
        self.update_state(state='PROCESSING', meta={'progress': 100*(i / (10 * 2))})
    csv_path = video_path.replace('.mp4', '.csv').replace(UPLOAD_DIR, RESULT_DIR)
    pd.DataFrame(results).to_csv(csv_path, index=False)
    return {'csv_path': csv_path}