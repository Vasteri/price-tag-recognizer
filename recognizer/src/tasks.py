from pathlib import Path

from .celery_app import celery_app
from .config import RESULT_DIR, UPLOAD_DIR
from .recognizer import recognize_tracks, save_to_csv
from .tracker import process_tracking


@celery_app.task(bind=True, name="recognizer.tasks.process_video")
def process_video(self, video_path_str: str):
    video_path = Path(video_path_str)
    self.update_state(state="PROCESSING", meta={"progress": 0})

    # пайплайн

    # 1. Отслеживание треков :50% прогресс-бара

    # dir/vid.mp4 -> dir/vid.mp4.tracks/
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
    self.update_state(state="PROCESSING", meta={"progress": 50})
    results = recognize_tracks(tracks_path)

    csv_path = Path(
        video_path_str.replace(".mp4", ".csv").replace(UPLOAD_DIR, RESULT_DIR)
    )
    save_to_csv(results, csv_path, video_path.name, tracks_path)

    self.update_state(state="PROCESSING", meta={"progress": 100})

    return {"csv_path": str(csv_path)}
