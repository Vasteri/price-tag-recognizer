import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
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
    # A torch.device bypasses Ultralytics' CPU selection, which hides CUDA.
    device = torch.device("cpu") if QR_DEVICE.strip().lower() == "cpu" else QR_DEVICE
    # Older Ultralytics versions change GPU visibility for other devices too.
    # Crop QR detection must not affect subsequent video tasks in this worker.
    cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
    try:
        result = _get_model().predict(
            bgr, imgsz=640, conf=QR_CONFIDENCE, iou=0.3,
            max_det=100, device=device, half=False, verbose=False,
        )[0]
    finally:
        if cuda_visible_devices is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
    boxes = result.boxes.xyxy.cpu().numpy()
    scores = result.boxes.conf.cpu().numpy()
    return [
        {"bbox": box.tolist(), "confidence": float(score)}
        for box, score in zip(boxes, scores)
    ]
