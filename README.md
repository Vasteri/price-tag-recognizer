# Price Tag Recognizer

<p align="center">
  <b>End-to-end пайплайн для распознавания ценников из видео</b><br>
  Object Detection (YOLOv11x) · OCR (PaddleOCR) · Vision-Language Model (Qwen3-VL-2B)
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/GPU-NVIDIA%20CUDA-76B900?logo=nvidia" alt="GPU">
</p>

---

## Содержание

- [О проекте](#о-проекте)
- [Архитектура пайплайна](#архитектура-пайплайна)
- [Быстрый старт](#быстрый-старт)
- [Пайплайн обработки](#пайплайн-обработки)
- [Инфраструктура](#инфраструктура)
  - [Сервисы](#сервисы)
  - [Переменные окружения](#переменные-окружения)
  - [Профили](#профили)
  - [Тома и данные](#тома-и-данные)
- [Структура проекта](#структура-проекта)
- [Технологический стек](#технологический-стек)
- [Лицензия](#лицензия)

---

## О проекте

**Price Tag Recognizer** — это пайплайн компьютерного зрения для автоматического извлечения структурированных данных с ценников из видеопотока. Система принимает видеофайл, детектирует ценники на кадрах, вырезает их, при необходимости прогоняет через OCR и vision-language модель, а затем агрегирует результаты в единый CSV.

**Зачем это нужно:**
- Автоматический сбор и актуализация цен в ритейле
- Мониторинг цен конкурентов
- Создание датасетов для обучения моделей
- Цифровизация товарного учёта

---

## Архитектура пайплайна

```
Video Input
    │
    ▼
Frame Extraction (OpenCV, frame_skipping=2)
    │
    ▼
YOLOv11x Detection (Ultralytics) → bounding boxes ценников
    │
    ▼
Crop Extraction (OpenCV, Pillow) → ROI с padding
    │
    ▼
[Опционально] PaddleOCR → text hints для VLM
    │
    ▼
Qwen3-VL-2B Inference → извлечение семантических полей
    │
    ▼
Aggregation → выбор лучшего предикта среди кадров
    │
    ▼
CSV Export
```

**Извлекаемые поля:** `product_name`, `price_default`, `price_card`, `price_discount`, `barcode`, `discount_amount`, `id_sku`, `print_datetime`, `code`, `additional_info`, `color`, `special_symbols`.

---

## Быстрый старт

### Требования

- **Docker** ≥ 24 и **Docker Compose** v2
- **NVIDIA GPU** с драйвером от CUDA 13.0 и установленным `nvidia-container-toolkit` (для GPU-режима)
- ~8 ГБ свободной оперативной памяти
- ~10 ГБ дискового пространства под образы и модели
- **bash**, **curl**/**wget** — для запуска `scripts/linux/install_model.sh`
- **PowerShell** ≥ 5.1 — для запуска `scripts/windows/install_model.ps1`

### 1. Клонирование

```bash
git clone https://github.com/Vasteri/price-tag-recognizer.git
cd price-tag-recognizer
```

### 2. Настройка окружения

Скопируйте шаблон и при необходимости отредактируйте значения:
```bash
cp .env.example .env
```

Файл .env.example уже содержит все необходимые переменные с разумными значениями по умолчанию — для локального запуска менять ничего не нужно.

### 3. Загрузка моделей

Модели Qwen3-VL-2B и mmproj скачиваются автоматически:

**Linux / macOS:**
```bash
bash scripts/linux/install_model.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_model.ps1
```

Оба скрипта кладут файлы в `./models/`:

```
models/
├── Qwen3-VL-2B-Instruct-Q4_K_M.gguf
└── mmproj-Qwen3-VL-2B-Instruct-F16.gguf
```

### 4. Запуск

**GPU-режим (основной):**

```bash
docker compose up -d --build
```

**CPU-режим (без GPU):**

```bash
docker compose -f docker-compose-cpu.yml up -d --build
```

### 5. Проверка

```bash
docker compose ps
```

- **Nginx / Frontend:** http://localhost:80
- **Flower:** http://localhost/flower
- **Grafana:** http://localhost/grafana

---

## Пайплайн обработки

Пайплайн разбит на независимые этапы, каждый из которых может выполняться и тестироваться отдельно. Управление — через Celery: `backend` принимает запрос и ставит задачу, `worker` её выполняет, результат складывается в общий том.

### Этапы

**1. Загрузка видео**
Пользователь отправляет видеофайл через API (`POST /recognize`). Файл сохраняется в `shared_volume` и получает `task_id`.

**2. Извлечение кадров**
OpenCV читает видео с пропуском кадров (`frame_skipping=2` по умолчанию). Каждый N-й кадр уходит дальше по пайплайну. Параметры (`fps`, `skip`, `max_frames`) настраиваются через API.

**3. Детекция ценников (YOLOv11x)**
Каждый кадр прогоняется через YOLO. На выходе — список bounding boxes с классами (`price_tag`, `barcode`, `qr` и т.д.). Отсекаются детекции с `confidence < threshold`.

**4. Кроп и предобработка**
Из кадра вырезаются ROI с padding, нормализуется размер и контраст (Pillow + OpenCV). Для мелких ценников применяется апскейл.

**5. OCR (PaddleOCR, опционально)**
Если включён, PaddleOCR извлекает текстовые подсказки с кропа. Они передаются в VLM как дополнительный контекст и повышают точность на сложных ценниках.

**6. Инференс VLM (Qwen3-VL-2B)**
Кроп + OCR-подсказки отправляются в `llama-cpp-server` (`POST /v1/chat/completions`). Модель возвращает JSON со структурированными полями

#### Пример prompt

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

**7. Валидация и агрегация**
Ответы модели валидируются (Pydantic). Если ценник попал в несколько кадров — выбирается лучший предикт по эвристике: приоритет у кадров с большей уверенностью YOLO и меньшим `distance to camera`. Дубликаты схлопываются по `id_sku` или `barcode`.

**8. Экспорт**
Результат сохраняется в CSV и JSON в `shared_volume`. Пользователь забирает его через `GET /result/{task_id}` или видит в веб-интерфейсе.

### Что где живёт

| Этап | Где | Кто выполняет |
|---|---|---|
| Приём запроса | `backend/` | FastAPI |
| Постановка задачи | `backend/` | Celery producer |
| Очередь | `redis` | Redis broker |
| Извлечение кадров | `recognizer/` | Celery worker |
| Детекция YOLO | `recognizer/` | Celery worker (GPU) |
| OCR | `recognizer/` | Celery worker |
| VLM-инференс | `llama-cpp-server` | llama.cpp (GPU) |
| Агрегация | `recognizer/` | Celery worker |
| Отдача результата | `backend/` | FastAPI |

---

## Инфраструктура

Проект полностью контейнеризирован и управляется через **Docker Compose**.

### Сервисы

| Сервис | Образ / сборка | Назначение | Порт | Профиль |
|---|---|---|---|---|
| **nginx** | `nginx:1.29.5` | Reverse proxy, отдача статики frontend | `80` | — |
| **redis** | `redis:alpine3.23` | Брокер сообщений Celery, кеш | `6379` (внутр.) | — |
| **backend** | `./backend/` | FastAPI, API, постановка задач в Celery | `8000` (внутр.) | — |
| **worker** | `./recognizer/` | Celery worker, обработка задач распознавания | — | — |
| **llama-cpp-server** | `ghcr.io/ggml-org/llama.cpp:server-cuda13` | Инференс Qwen3-VL-2B (GPU) | `8000` (внутр.) | — |
| **flower** | `mher/flower:2.0.1` | UI мониторинга Celery | `5555` → `/flower` | `monitoring` |
| **prometheus** | `prom/prometheus:v2.50.1` | Сбор метрик | `9090` (внутр.) | `monitoring` |
| **promtail** | `grafana/promtail:3.6.11` | Сбор логов из Docker | — | `monitoring` |
| **loki** | `grafana/loki:3.7.2` | Хранилище логов | `3100` (внутр.) | `monitoring` |
| **grafana** | `grafana/grafana:10.4.0` | Визуализация метрик и логов | `3000` → `/grafana` | `monitoring` |

**Особенности сервисов:**

- **nginx** проксирует трафик на `backend`, `flower` и `grafana`. Статика frontend отдаётся из `./frontend/static`.
- **backend** и **worker** обмениваются данными через общий том `shared_volume`.
- **llama-cpp-server** использует GPU (`deploy.resources.reservations.devices`) и монтирует модели из `./models` только для чтения.
- **worker** также запрашивает GPU-ресурсы, так как выполняет inference YOLO и VLM.
- **healthcheck** настроен для `redis`, `backend`, `llama-cpp-server` и `nginx`.
- **Логирование** ограничено 10 МБ на файл, максимум 3 файла (json-file driver).

### Переменные окружения

Все настраиваемые параметры вынесены в `.env`. Основные группы:

| Переменная | Описание | Пример |
|---|---|---|
| `NGINX_PORT` | Внешний порт Nginx | `80` |
| `MODEL_PATH` | Путь к GGUF-модели Qwen3-VL | `/models/Qwen3-VL-2B-Instruct-Q4_K_M.gguf` |
| `MMPROJ_PATH` | Путь к mmproj-файлу | `/models/mmproj-Qwen3-VL-2B-Instruct-F16.gguf` |
| `CONTEXT_SIZE` | Размер контекста LLM | `65535` |
| `GPU_LAYERS` | Количество слоёв на GPU | `99` |
| `CELERY_BROKER_URL` | URL брокера Celery | `redis://redis:6379/0` |
| `COMPOSE_PROFILES` | Профили по умолчанию | `monitoring` |

### Профили

Сервисы мониторинга (`flower`, `prometheus`, `promtail`, `loki`, `grafana`) вынесены в профиль `monitoring`. Управление:

```bash
# С мониторингом (по умолчанию, если в .env указан COMPOSE_PROFILES=monitoring)
docker compose up -d

# Без мониторинга
COMPOSE_PROFILES= docker compose up -d

# Только мониторинг (если основные сервисы уже запущены)
docker compose --profile monitoring up -d
```

### Тома и данные

| Том | Назначение |
|---|---|
| `shared_volume` | Обмен данными между `backend` и `worker` |
| `flower_data` | Состояние Flower |
| `prometheus_data` | TSDB Prometheus |
| `loki_data` | Хранилище логов Loki |
| `grafana_data` | Дашборды и настройки Grafana |

Bind mounts:
- `./infra/nginx.conf` → конфиг Nginx
- `./frontend/static` → статика
- `./models` → модели (ro)
- `./infra/prometheus.yml` → конфиг Prometheus (ro)
- `./infra/promtail-config.yaml` → конфиг Promtail (ro)
- `./infra/grafana/provisioning` → провижининг Grafana (ro)
- `/var/run/docker.sock` → доступ Promtail к логам контейнеров

---

## Структура проекта

```
price-tag-recognizer/
├── backend/                  # FastAPI + Celery producer
├── frontend/static/          # Статика для Nginx
├── recognizer/               # Celery worker: YOLO, PaddleOCR, VLM
├── infra/                    # Конфиги инфраструктуры
│   ├── nginx.conf
│   ├── prometheus.yml
│   ├── promtail-config.yaml
│   └── grafana/provisioning/
├── models/                   # GGUF-модели (монтируются в llama-cpp-server)
├── scripts/                  # Пока только скачивание Qwen3-VL и mmproj (bash и PowerShell)
├── docker-compose.yml        # Основной compose (GPU)
├── docker-compose-cpu.yml    # Compose для CPU-режима
├── .env.example              # Шаблон переменных окружения
└── README.md
```

---

## Технологический стек

| Категория | Технологии |
|---|---|
| **Язык** | Python 3.11 |
| **Обработка видео** | OpenCV, ffmpeg, NumPy |
| **Детекция** | YOLOv11x, Ultralytics |
| **OCR** | PaddleOCR (PP-OCRv5 mobile) |
| **VLM** | Qwen3-VL-2B (GGUF, llama.cpp) |
| **Обработка изображений** | Pillow, OpenCV |
| **Очередь задач** | Celery + Redis |
| **API** | FastAPI |
| **Reverse proxy** | Nginx |
| **Мониторинг** | Prometheus, Grafana, Loki, Promtail, Flower |
| **Контейнеризация** | Docker, Docker Compose |

---

## Лицензия

MIT License. См. файл [LICENSE](LICENSE) для подробностей.

---

<p align="center">
  Сделано для <b>Lenta Tech Life 2026</b> 🛒
</p>