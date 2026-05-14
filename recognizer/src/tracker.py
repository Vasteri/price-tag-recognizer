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

TODO: tqdm в консоль выводится дважды, некритично
"""

import os
import cv2
import json
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
from tqdm import tqdm

def setup_model(repo_id, filename):
    model_path = hf_hub_download(repo_id=repo_id, filename=filename)
    return YOLO(model_path)

def process_tracking(repo_id, repo_filename, source_video, output_dir, frame_interval):
    model = setup_model(repo_id, repo_filename)
    cap = cv2.VideoCapture(source_video)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pbar = tqdm(total=total_frames+1, desc="Обработка видео")

    frame_idx = -1
    meta_data = {}
    known_tracks = []
    while cap.isOpened():
        frame_idx += 1
        pbar.update(1)
        
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
                track_dir = os.path.join(output_dir, f"track_{track_id}")
                image_dir = os.path.join(track_dir, f"images")

                if track_id not in known_tracks:
                    known_tracks.append(track_id)
                    os.makedirs(track_dir, exist_ok=True)
                    os.makedirs(image_dir, exist_ok=True)

                x1, y1, x2, y2 = map(int, box)
                crop = frame[y1:y2, x1:x2]
                
                img_name = f"frame_{frame_idx:04d}.jpg"
                img_path = os.path.join(image_dir, img_name)
                cv2.imwrite(img_path, crop)
                
                if meta_data.get(track_id, None) is None:
                    meta_data[track_id] = []

                meta_data[track_id].append({
                    "frame": frame_idx,
                    "timestamp": int(timestamp_ms),
                    "bbox": [w-y2, x1, w-y1, x2], # x1, y1, x2, y2 но до поворота
                    "image": img_name
                })

    cap.release()

    print(f'\nЗаписываются метаданные...')
    for key, value in meta_data.items():
        track_dir = os.path.join(output_dir, f"track_{key}")
        meta_path = os.path.join(track_dir, "metadata.json")
        with open(meta_path, 'w') as f:
            f.write(json.dumps(value, indent=4))


def main(
    repo_id: str = "openfoodfacts/price-tag-detection",
    repo_filename: str = "weights/best.pt",
    source_video: str,
    output_dir: str,
    frame_interval: int = 2,
):
    process_tracking(repo_id, repo_filename, source_video, output_dir, frame_interval)
    print('Успешно')


if __name__ == "__main__":
    import tyro
    tyro.cli(main)
