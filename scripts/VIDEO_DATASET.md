# Датасет QR из видео

`build_video_dataset.py` детектирует ценники первой YOLO-моделью, сохраняет их кропы в PNG и запускает вторую YOLO-модель для поиска QR. Работает отдельно от Celery, OCR и VLM.

Запуск через Docker Compose, локальное Python-окружение не требуется. Используется тот же базовый образ Ultralytics, что и у worker. Redis, VLM и остальные сервисы приложения не запускаются.

Перед первым запуском загрузите модели из корня проекта (нужны `bash`, `wget` и доступ в интернет):

```bash
bash scripts/linux/install_model.sh
```

Скрипт называется `install_model.sh` (без `s`) и сохраняет веса в `models/`, включая нужные для датасета `yolo-price-tag-detection.pt` и `qrdet-n.pt`. Он также скачивает Qwen3-VL и mmproj для основного приложения; при создании датасета они не используются. Если оба YOLO-файла уже есть, повторная загрузка не нужна.

Положите видео в `videos/`. Из корня проекта:

```bash
mkdir -p videos datasets
DATASET_UID=$(id -u) DATASET_GID=$(id -g) \
  docker compose -f docker-compose-dataset.yml run --rm dataset \
  /videos/video.mp4 \
  --tag-model /models/yolo-price-tag-detection.pt \
  --qr-model /models/qrdet-n.pt \
  --output /datasets/video-01 \
  --frame-step 15
```

CSV и кропы появятся на хосте в `datasets/video-01/`. Создайте `datasets/` до запуска, чтобы Docker не создал директорию от root. `DATASET_UID` и `DATASET_GID` задают владельца выходных файлов; по умолчанию используются 1000:1000.

Для NVIDIA GPU (нужен NVIDIA Container Toolkit):

```bash
DATASET_UID=$(id -u) DATASET_GID=$(id -g) \
  docker compose -f docker-compose-dataset.yml run --rm dataset-gpu \
  /videos/video.mp4 \
  --tag-model /models/yolo-price-tag-detection.pt \
  --qr-model /models/qrdet-n.pt \
  --output /datasets/video-01-gpu \
  --frame-step 15 --device 0
```

Справка: `docker compose -f docker-compose-dataset.yml run --rm dataset --help`.

Сам `build_video_dataset.py` модели не скачивает: используйте предварительную загрузку выше или предоставьте собственные веса. Если видео нужно повернуть, добавьте `--rotation ccw`, `cw` или `180`; по умолчанию поворота нет.

Пороги задаются через `--tag-conf` (0.25) и `--qr-conf` (0.5), размер входа — `--tag-imgsz` и `--qr-imgsz` (640). Для многоклассовых моделей укажите соответствующие ID через `--tag-classes 0` и `--qr-classes 0`. Без фильтра используются все классы модели.

Результат:

```text
datasets/video-01/
├── images/frame_00000000_tag_0000.png
├── images/...
└── annotations.csv
```

CSV содержит одну строку на QR. У нескольких QR одного кропа одинаковый `image_path`. Для кропов без QR сохраняется одна строка с `qr_count=0` и пустыми QR-полями. Пустой результат детекции ценников даёт CSV только с заголовком.

- `image_path`: путь относительно директории датасета.
- `video_path`, `frame_index`, `timestamp_ms`: исходное видео (путь внутри контейнера), номер кадра с нуля и время OpenCV в миллисекундах.
- `image_width`, `image_height`: размеры сохранённого кропа.
- `tag_x_min`, `tag_y_min`, `tag_x_max`, `tag_y_max`: bbox ценника в кадре **после выбранного поворота**.
- `qr_x_min`, `qr_y_min`, `qr_x_max`, `qr_y_max`: bbox QR в сохранённом кропе.
- Все bbox — целочисленные пиксели `xyxy`, правая и нижняя границы не включаются; координаты ограничены размерами картинки.
- `tag_class_id`, `tag_confidence`, `qr_class_id`, `qr_confidence`: классы и уверенность моделей.
- `qr_count`, `qr_index`: количество QR в кропе и индекс детекции с нуля.

`--output` должен указывать на новую директорию, чтобы не перезаписать датасет. При прерывании частичные результаты остаются на диске; для повторного запуска выберите новую директорию. Трекинга и удаления похожих кропов нет: каждый выбранный кадр обрабатывается независимо. Аннотации получены моделью и требуют проверки перед обучением.
