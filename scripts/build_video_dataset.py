"""Create price-tag crops and QR bounding-box annotations from a video."""

import argparse
import csv
import math
from pathlib import Path

FIELDS = [
    "image_path",
    "video_path",
    "frame_index",
    "timestamp_ms",
    "image_width",
    "image_height",
    "rotation",
    "tag_x_min",
    "tag_y_min",
    "tag_x_max",
    "tag_y_max",
    "tag_class_id",
    "tag_confidence",
    "qr_count",
    "qr_index",
    "qr_x_min",
    "qr_y_min",
    "qr_x_max",
    "qr_y_max",
    "qr_class_id",
    "qr_confidence",
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--tag-model", type=Path, required=True)
    parser.add_argument("--qr-model", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New dataset directory (must not exist)",
    )
    parser.add_argument("--frame-step", type=int, default=15)
    parser.add_argument("--tag-conf", type=float, default=0.25)
    parser.add_argument("--qr-conf", type=float, default=0.5)
    parser.add_argument("--tag-imgsz", type=int, default=640)
    parser.add_argument("--qr-imgsz", type=int, default=640)
    parser.add_argument("--tag-classes", type=int, nargs="+", default=None)
    parser.add_argument("--qr-classes", type=int, nargs="+", default=None)
    parser.add_argument("--device", default="cpu", help="cpu, 0, cuda:0, etc.")
    parser.add_argument(
        "--rotation", choices=["none", "cw", "ccw", "180"], default="none"
    )
    args = parser.parse_args(argv)
    for name in ("frame_step", "tag_imgsz", "qr_imgsz"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in ("tag_conf", "qr_conf"):
        if not 0 <= getattr(args, name) <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    for path in (args.video, args.tag_model, args.qr_model):
        if not path.is_file():
            parser.error(f"File not found: {path}")
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    return args


def clip_box(box, width, height):
    """Return enclosing integer xyxy bounds, clipped to the image."""
    x1, y1, x2, y2 = box
    return (
        max(0, min(width, math.floor(x1))),
        max(0, min(height, math.floor(y1))),
        max(0, min(width, math.ceil(x2))),
        max(0, min(height, math.ceil(y2))),
    )


def detections(result):
    if result.boxes is None:
        return
    yield from zip(
        result.boxes.xyxy.cpu().tolist(),
        result.boxes.conf.cpu().tolist(),
        result.boxes.cls.cpu().tolist(),
    )


def build_dataset(args):
    # Lazy imports keep --help usable without ML dependencies.
    import cv2
    from ultralytics import YOLO

    tag_model = YOLO(str(args.tag_model))
    qr_model = YOLO(str(args.qr_model))
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Cannot open video: {args.video}")
    frame_index = 0
    crops_count = qr_count = processed = 0
    rotations = {
        "cw": cv2.ROTATE_90_CLOCKWISE,
        "ccw": cv2.ROTATE_90_COUNTERCLOCKWISE,
        "180": cv2.ROTATE_180,
    }
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        images_dir = args.output / "images"
        images_dir.mkdir()
        with (args.output / "annotations.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            while True:
                success, frame = cap.read()
                if not success:
                    break
                current_index = frame_index
                frame_index += 1
                if current_index % args.frame_step:
                    continue
                timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                if args.rotation != "none":
                    frame = cv2.rotate(frame, rotations[args.rotation])
                height, width = frame.shape[:2]
                tags = tag_model.predict(
                    frame,
                    conf=args.tag_conf,
                    imgsz=args.tag_imgsz,
                    classes=args.tag_classes,
                    device=args.device,
                    verbose=False,
                )[0]
                for tag_index, (box, confidence, class_id) in enumerate(
                    detections(tags)
                ):
                    x1, y1, x2, y2 = clip_box(box, width, height)
                    if x2 <= x1 or y2 <= y1:
                        continue
                    crop = frame[y1:y2, x1:x2].copy()
                    image_name = f"frame_{current_index:08d}_tag_{tag_index:04d}.png"
                    image_path = images_dir / image_name
                    # PNG preserves exactly the pixels used for QR inference.
                    if not cv2.imwrite(str(image_path), crop):
                        raise OSError(f"Cannot save crop: {image_path}")
                    result = qr_model.predict(
                        crop,
                        conf=args.qr_conf,
                        imgsz=args.qr_imgsz,
                        classes=args.qr_classes,
                        device=args.device,
                        verbose=False,
                    )[0]
                    crop_height, crop_width = crop.shape[:2]
                    qr_boxes = []
                    for qr_box, score, qr_class in detections(result):
                        bounds = clip_box(qr_box, crop_width, crop_height)
                        if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                            qr_boxes.append((bounds, score, qr_class))
                    row = {
                        "image_path": f"images/{image_name}",
                        "video_path": str(args.video.resolve()),
                        "frame_index": current_index,
                        "timestamp_ms": timestamp_ms,
                        "image_width": crop_width,
                        "image_height": crop_height,
                        "rotation": args.rotation,
                        "tag_x_min": x1,
                        "tag_y_min": y1,
                        "tag_x_max": x2,
                        "tag_y_max": y2,
                        "tag_class_id": int(class_id),
                        "tag_confidence": confidence,
                        "qr_count": len(qr_boxes),
                    }
                    if not qr_boxes:
                        writer.writerow(row)
                    for qr_index, (bounds, score, qr_class) in enumerate(qr_boxes):
                        writer.writerow(
                            {
                                **row,
                                "qr_index": qr_index,
                                "qr_x_min": bounds[0],
                                "qr_y_min": bounds[1],
                                "qr_x_max": bounds[2],
                                "qr_y_max": bounds[3],
                                "qr_class_id": int(qr_class),
                                "qr_confidence": score,
                            }
                        )
                    crops_count += 1
                    qr_count += len(qr_boxes)
                processed += 1
                if processed % 10 == 0:
                    print(
                        f"Processed {processed} frames; {crops_count} crops; {qr_count} QR boxes",
                        flush=True,
                    )
            if frame_index == 0:
                raise ValueError(f"Video contains no readable frames: {args.video}")
    finally:
        cap.release()
    print(f"Saved {crops_count} crops and {qr_count} QR boxes to {args.output}")


if __name__ == "__main__":
    build_dataset(parse_args())
