# Price Tag Recognizer

Pipeline для распознавания ценников из видео с использованием object detection(YOLOv11x), OCR(PaddleOCR) и vision-language models(Qwen3-VL-2B).

---

# Overview

Проект реализует end-to-end pipeline:

```text
Video Input
    ↓
Frame Extraction
    ↓
YOLO Detection
    ↓
Crop Price Tags
    ↓
(Optional) PaddleOCR
    ↓
Qwen3-VL-2B
    ↓
Aggregation / Postprocessing
    ↓
CSV Export
```

Система может быть использована для:
- автоматического сбора цен
- ритейл-аналитики
- OCR automation
- dataset generation
- inventory digitization

В рамках хакатона используется для получения информации о ценниках в видео.

---

# Pipeline

## 1. Video Loading

На вход подается видео:

- mp4
- avi
- mov

### Что происходит

- открытие видео
- чтение кадров
- sampling кадров с заданным FPS
- конвертация в OpenCV format

### Инструменты

- OpenCV
- ffmpeg
- NumPy
---

# 2. Frame Extraction

Из видео извлекаются кадры c frame_skipping = 2 для уменьшения нагрузки.

### Инструменты

- OpenCV
- NumPy

---

# 3. YOLO Detection

На кадрах детектируются ценники.

YOLO находит bounding boxes:
- ценников

### Результат

```python
[
    {
        "bbox": [x1, y1, x2, y2],
        "confidence": 0.94
    }
]
```


---

# 4. Crop Extraction

После detection вырезаются области ценников.

### Что происходит

- crop ROI
- padding

### Цель

Подготовить изображение для OCR и vision-language model.

### Инструменты

- OpenCV
- Pillow

---

# 5. Optional PaddleOCR

Дополнительный OCR-этап.

Используется для:
- предварительного извлечения текста
- ускорения inference
- text hints для VLM

### Что распознается

- любой текст с ценника

### Инструменты

- PaddleOCR("PP-OCRv5_mobile_det" + "cyrillic_PP-OCRv5_mobile_rec" и стандарные модели для unwarping, text_orientation)

---

# 6. Qwen3-VL-2B

Главный этап semantic extraction.

Vision-language model получает:
- crop изображения
- схему одного из ценников с заблюренным текстом во избежании детекта информации со схемы
- OCR text (optional)
- prompt

### Что извлекается

Все поля, которые требуются в ответном csv, кроме полей, зависящих от qr/

### Пример prompt

```text
Ты — система распознавания ценников в российских магазинах.
На изображении фрагмент ценника. Верни ТОЛЬКО валидный JSON без markdown и пояснений.

Важно: извлекай ТОЛЬКО то, что реально видно на изображении. Не придумывай и не дополняй значения. Если поле не читается или отсутствует — null.

Поля и их типы:
- product_name (string): полное название товара с объёмом/весом
- price_default (float): обычная цена с копейками через точку
- price_card (float): цена по карте лояльности
- price_discount (float): цена по акции
- barcode (string): штрихкод, только цифры
- discount_amount (string): размер скидки, например "-48%"
- id_sku (string): внутренний артикул/SKU магазина, только цифры
- print_datetime (string): дата и время печати ценника, например "03.04.2026 3:08"
- code (string): код на ценнике если есть, отличается от штрихкода и SKU
- additional_info (string): любая дополнительная информация
- color (string): цвет ценника — одно из: red, yellow, green, white, blue или другой
- special_symbols (string): спецсимволы или пометки на ценнике
```


### Инструменты

- Qwen3-VL-2B
- Docker Model Runner

### Особенности

VLM позволяет:
- понимать структуру ценника
- исправлять OCR ошибки
- извлекать семантику
- работать с noisy изображениями

---

# 7. Aggregation

Результаты агрегируются между кадрами.

### Что делается

- выбор предикта с максимальным числом предсказанных полей
- подтягивание оставшихся полей с других ценников

### Проблемы которые решаются

- OCR noise
- unstable detections

---

# 8. CSV Export

Финальные результаты сохраняются в CSV.


### Инструменты

- csv(python)


---

# Tech Stack

| Category | Tools |
|---|---|
| Language | Python |
| Video Processing | OpenCV, ffmpeg |
| Detection | YOLOv11x, Ultralytics |
| OCR | PaddleOCR |
| Vision-Language Model | Qwen3-VL-2B |
| Data Processing | NumPy |
| Image Processing | Pillow, OpenCV |

---

# Project Structure

```bash
price-tag-recognizer/
│
├── data/
│   ├── videos/
│   ├── frames/
│   └── crops/
│
├── models/
│   ├── yolo/
│   └── qwen/
│
├── src/
│   ├── video/
│   ├── detection/
│   ├── cropping/
│   ├── ocr/
│   ├── vlm/
│   ├── aggregation/
│   └── export/
│
├── outputs/
│   └── result.csv
│
├── requirements.txt
└── README.md
```

---

# Docker Support

Проект поднимается локально через `docker-compose.yml`, без ручной сборки образов.

## Запуск

```bash
docker compose up --build
```

или (если уже собран образ):

```bash
docker compose up
```

---

## Что поднимается через docker-compose

Вся система запускается как единый pipeline-сервис:

- YOLO inference (детекция ценников)
- OCR слой (PaddleOCR, опционально)
- Qwen3-VL-2B inference (semantic extraction)
- Pipeline orchestrator (video → frames → aggregation → CSV)

---

# License

MIT License
