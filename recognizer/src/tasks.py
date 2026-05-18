import json
from pathlib import Path

import pandas as pd

from .celery_app import celery_app
from .config import RESULT_DIR, UPLOAD_DIR
from .recognizer import recognize_tracks
from .tracker import process_tracking


@celery_app.task(bind=True, name="recognizer.tasks.process_video")
def process_video(self, video_path_str: str):
    video_path = Path(video_path_str)
    self.update_state(state="PROCESSING", meta={"progress": 0})

    # пайплайн

    # 1. Отслеживание треков :50% прогресс-бара

    # dir/vid.mp4 -> dir/vid.mp4.tracks/
    # можно заменить на то как удобней будет
    tracks_path = video_path.parent / (video_path.name + ".tracks")
    tracks_path.mkdir(parents=True, exist_ok=True)

    for frames_processed, total_frames in process_tracking(
        source_path=video_path,
        output_path=tracks_path,
        # пока хардкод + модель с hugging face хорошо себя показывает
        frame_interval=2,
        repo_id="openfoodfacts/price-tag-detection",
        repo_filename="weights/best.pt",
    ):
        self.update_state(
            state="PROCESSING", meta={"progress": 50 * frames_processed / total_frames}
        )

    # 2.
    ...

    results = [video_path_str.split("/")[-1].split(".")[0]]
    csv_path = video_path_str.replace(".mp4", ".csv").replace(UPLOAD_DIR, RESULT_DIR)
    pd.DataFrame(results).to_csv(csv_path, index=False)

    json_path = recognize_price_tags(str(tracks_path), video_path_str)["json_path"]
    #return {"csv_path": csv_path}
    return {"csv_path": json_path}


def recognize_price_tags(tracks_path_str: str, video_path_str: str):
    tracks_path = Path(tracks_path_str)

    results = recognize_tracks(tracks_path)

    # сохраняем сырые предсказания — мёрдж потом, когда будет понятна логика
    json_path = video_path_str.replace(".mp4", ".predictions.json").replace(
        UPLOAD_DIR, RESULT_DIR
    )
    Path(json_path).write_text(json.dumps(results, ensure_ascii=False, indent=2))

    return {"json_path": json_path}
