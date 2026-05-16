import pandas as pd
from pathlib import Path
from time import sleep

from .config import UPLOAD_DIR, RESULT_DIR
from .celery_app import celery_app

from .tracker import process_tracking

@celery_app.task(bind=True, name='recognizer.tasks.process_video')
def process_video(self, video_path_str: str):
    video_path = Path(video_path_str)
    self.update_state(state='PROCESSING', meta={'progress': 0})

    # пайплайн

    # 1. Отслеживание треков :50% прогресс-бара

    # dir/vid.mp4 -> dir/vid.mp4.tracks/
    # можно заменить на то как удобней будет
    tracks_path = video_path.parent / (video_path.name + '.tracks')
    tracks_path.mkdir(parents=True, exist_ok=True)

    for frames_processed, total_frames in process_tracking(
        source_path=video_path,
        output_path=tracks_path,
        # пока хардкод + модель с hugging face хорошо себя показывает
        frame_interval=2,
        repo_id="openfoodfacts/price-tag-detection",
        repo_filename="weights/best.pt",
    ):
        self.update_state(state='PROCESSING', meta={'progress': 50 * frames_processed / total_frames})

    # 2.
    ...

    results = [video_path_str.split('/')[-1].split('.')[0]]
    csv_path = video_path_str.replace('.mp4', '.csv').replace(UPLOAD_DIR, RESULT_DIR)
    pd.DataFrame(results).to_csv(csv_path, index=False)
    return {'csv_path': csv_path}