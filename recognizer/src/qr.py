from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from ultralytics import YOLO

from .config import QR_CONFIDENCE, QR_DEVICE, QR_MODEL


@lru_cache(maxsize=1)
def _get_model() -> YOLO:
    path = Path(QR_MODEL)
    if not path.is_file():
        raise FileNotFoundError(f"QR weights not found: {path}. Run install_model first.")
    return YOLO(str(path), task="segment")


def detect_qr(image_path: Path) -> list[dict]:
    """Return QR boxes in pixels of the EXIF-oriented image; no decoding."""
    with Image.open(image_path) as source:
        rgb = np.array(ImageOps.exif_transpose(source).convert("RGB"))
    # Ultralytics accepts ndarray images in BGR order.
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    result = _get_model().predict(
        bgr, imgsz=640, conf=QR_CONFIDENCE, iou=0.3,
        max_det=100, device=QR_DEVICE, half=False, verbose=False,
    )[0]
    boxes = result.boxes.xyxy.cpu().numpy()
    scores = result.boxes.conf.cpu().numpy()
    return [
        {"bbox": box.tolist(), "confidence": float(score)}
        for box, score in zip(boxes, scores)
    ]
