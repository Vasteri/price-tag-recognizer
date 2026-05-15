"""
Скрипт для автоматического детектирования и трекинга объектов (ценников) в видеопотоке.

Модулем осуществляется:
1. Загрузка предобученной модели YOLO с Hugging Face Hub.
2. Покадровая обработка видео с возможностью пропуска кадров (frame_interval).
3. Поворот кадра на 90 градусов против часовой стрелки перед обработкой.
4. Трекинг объектов (присвоение уникальных ID) с помощью встроенных алгоритмов Ultralytics.
5. Сохранение индивидуальных изображений (кропов) для каждого найденного трека.
6. Экспорт метаданных (номер кадра с 0, временная метка, координаты BBox) в формате JSON.

СТРУКТУРА ВЫХОДНЫХ ДАННЫХ:
output_dir/
├── track_1/
│   ├── images/
│   │   ├── frame_0000.jpg
│   │   └── ...
│   └── metadata.json
├── track_2/
│   └── ...
"""

import os
import cv2
import json
from time import time
from huggingface_hub import hf_hub_download
from ultralytics import YOLO


def process_tracking(
    # обязательные параметры
    source_path, output_path, frame_interval,
    # либо модель с Hugging Face
    repo_id=None, repo_filename=None,
    # либо локальная модель
    model_path=None,
    ):
    if model_path is None:
        model_path = hf_hub_download(repo_id=repo_id, filename=repo_filename)

    model = YOLO(model_path)
    cap = cv2.VideoCapture(source_path)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    frame_idx = -1
    meta_data = {}
    known_tracks = []

    last_time = None

    while cap.isOpened():
        frame_idx += 1
        # каждые 0.5 секунд отдаем статус
        if last_time is None or time() - last_time > 0.5:
            last_time = time()
            yield frame_idx, total_frames

        timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        success, frame = cap.read()
        if not success:
            break
        if frame_idx % frame_interval != 0:
            continue

        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        results = model.track(frame, persist=True, verbose=False)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()

            for box, track_id in zip(boxes, track_ids):
                track_path = os.path.join(output_path, f"track_{track_id}")
                image_path = os.path.join(track_path, f"images")

                if track_id not in known_tracks:
                    known_tracks.append(track_id)
                    os.makedirs(track_path, exist_ok=True)
                    os.makedirs(image_path, exist_ok=True)

                x1, y1, x2, y2 = map(int, box)
                crop = frame[y1:y2, x1:x2]

                img_name = f"frame_{frame_idx:04d}.jpg"
                img_path = os.path.join(image_path, img_name)
                cv2.imwrite(img_path, crop)

                if meta_data.get(track_id, None) is None:
                    meta_data[track_id] = []

                meta_data[track_id].append({
                    "frame": frame_idx,
                    "timestamp": int(timestamp_ms),
                    "bbox": [w-y2, x1, w-y1, x2], # x1, y1, x2, y2 но до поворота
                    "image": img_name
                })

    # После всех итераций - отдельно вернуть этот результат
    cap.release()
    yield total_frames-1, total_frames

    # Запись накопленных метаданных для каждого трека: frame number, timestamp, bbox, image_name
    for key, value in meta_data.items():
        track_path = os.path.join(output_path, f"track_{key}")
        meta_path = os.path.join(track_path, "metadata.json")
        with open(meta_path, 'w') as f:
            f.write(json.dumps(value, indent=4))

    # В конце вернуть 100% прогресс
    yield total_frames, total_frames


def main(
    source_path: str,
    output_path: str,
    frame_interval: int = 2,
    repo_id: str = "openfoodfacts/price-tag-detection",
    repo_filename: str = "weights/best.pt",
):
    process_tracking(
        source_path=source_path,
        output_path=output_path,
        frame_interval=frame_interval,
        repo_id=repo_id,
        filename=repo_filename,
    )
    print('Успешно')


if __name__ == "__main__":
    import tyro
    tyro.cli(main)