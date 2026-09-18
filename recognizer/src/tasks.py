import json
import logging
import time
from pathlib import Path

from .celery_app import celery_app
from .config import RESULT_DIR, UPLOAD_DIR
from .recognizer import recognize_tracks, save_to_csv
from .tracker import process_tracking


class JsonFormatter(logging.Formatter):
    def format(self, record):
        standard_fields = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "message", "asctime",
        }
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_fields and not key.startswith("_")
        }
        return json.dumps({
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            **extra,
        }, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="recognizer.tasks.process_video")
def process_video(self, video_path_str: str):
    video_path = Path(video_path_str)
    pipeline_start = time.monotonic()
    logger.info("pipeline.start", extra={"video": video_path.name})
    self.update_state(state="PROCESSING", meta={"progress": 0})

    # 1. Трекинг: 0% → 50%
    tracks_path = video_path.parent / (video_path.name + ".tracks")
    tracks_path.mkdir(parents=True, exist_ok=True)

    tracking_start = time.monotonic()
    for frames_processed, total_frames in process_tracking(
        source_path=video_path,
        output_path=tracks_path,
        frame_interval=2,
        repo_id="openfoodfacts/price-tag-detection",
        repo_filename="weights/best.pt",
    ):
        self.update_state(
            state="PROCESSING",
            meta={"progress": 50 * frames_processed / total_frames},
        )
    tracking_duration = round(time.monotonic() - tracking_start, 2)

    # 2. Распознавание: 50% → 100%
    self.update_state(state="PROCESSING", meta={"progress": 50})

    results = []
    recognition_start = time.monotonic()
    for current, total, batch in recognize_tracks(tracks_path):
        results.extend(batch)
        self.update_state(
            state="PROCESSING",
            meta={"progress": 50 + 50 * current / total},
        )
    recognition_duration = round(time.monotonic() - recognition_start, 2)

    track_dirs = list(tracks_path.glob("track_*"))
    tracks_count = len(track_dirs)
    crops_count = sum(
        len(list((track_dir / "images").glob("*.jpg")))
        for track_dir in track_dirs
    )

    csv_path = Path(
        video_path_str.replace(".mp4", ".csv").replace(UPLOAD_DIR, RESULT_DIR)
    )
    save_to_csv(results, csv_path, video_path.name, tracks_path)

    duration = round(time.monotonic() - pipeline_start, 2)
    logger.info("pipeline.done", extra={
        "video": video_path.name,
        "tracking_duration_sec": tracking_duration,
        "recognition_duration_sec": recognition_duration,
        "duration_sec": duration,
        "tracks_count": tracks_count,
        "crops_count": crops_count,
        "tracks_processed": len(results),
        "csv": str(csv_path),
    })

    return {"csv_path": str(csv_path)}
