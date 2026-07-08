import base64
import csv
import json
import logging
import random
import time
from pathlib import Path

import cv2
import numpy as np
from openai import OpenAI
from PIL import Image

from .config import ENABLE_OCR, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

if ENABLE_OCR == "true":
    from .ocr import OCRService

# LLM_BASE_URL = "http://host.docker.internal:12434/v1"
# LLM_MODEL = "ai/qwen3-vl:2B-UD-Q4_K_XL"  # уточни через `docker model list`

FIELDS = [
    "filename",
    "product_name",
    "price_default",
    "price_card",
    "price_discount",
    "barcode",
    "discount_amount",
    "id_sku",
    "print_datetime",
    "code",
    "additional_info",
    "color",
    "special_symbols",
    "frame_timestamp",
    "x_min",
    "y_min",
    "x_max",
    "y_max",
    "qr_code_barcode",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
]

RECOGNIZED_FIELDS = [
    "product_name",
    "price_default",
    "price_card",
    "price_discount",
    "barcode",
    "discount_amount",
    "id_sku",
    "print_datetime",
    "code",
    "additional_info",
    "color",
    "special_symbols",
]

EMPTY_RESULT = {f: None for f in RECOGNIZED_FIELDS}

PRICE_TAG_PROMPT = """На изображении фрагмент ценника. Верни ТОЛЬКО валидный JSON без markdown и пояснений.

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
- special_symbols (string): спецсимволы или пометки на ценнике"""


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


SCHEMA_IMAGE = _encode_image(
    Path(__file__).parent.parent / "assets" / "scheme_price_tag.jpg"
)


def _sample_crops(track_dir: Path, n: int) -> list[Path]:
    images = sorted((track_dir / "images").glob("*.jpg"))
    if not images:
        return []
    random.shuffle(images)
    return images[:n]


def _recognize_crop(client: OpenAI, image_path: Path, ocr_predict=None) -> dict:
    start = time.monotonic()
    has_ocr_hint = ocr_predict is not None
    logger.info("vlm.request", extra={"image": image_path.name, "ocr_hint": has_ocr_hint})

    try:
        content = []
        content.append(
            {
                "type": "text",
                "text": "Ты — профессиональный распознаватель ценников. Используй следующую схему для извлечения данных:",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{SCHEMA_IMAGE}"},
            }
        )
        content.append(
            {
                "type": "text",
                "text": "Распознай данные на следующем изображении ценника, строго следуя структуре полей, описанной выше. Выполни следующие требования: "
                + PRICE_TAG_PROMPT,
            }
        )
        if ocr_predict is not None:
            content.append(
                {
                    "type": "text",
                    "text": (
                        "Для помощи тебе предоставлены данные распознавания от другой OCR-системы: \n"
                        f"--- НАЧАЛО ПОДСКАЗКИ ---\n{ocr_predict}\n--- КОНЕЦ ПОДСКАЗКИ ---\n"
                        "Используй эти данные для уточнения трудночитаемого текста, но помни: "
                        "другая OCR могла ошибиться. Твоя главная задача — извлечь данные СТРОГО по изображению. "
                        "Если данные из подсказки противоречат тому, что ты видишь на фото, приоритет отдавай фото."
                    ),
                }
            )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{_encode_image(image_path)}"},
            }
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=512,
        )

        latency = round(time.monotonic() - start, 3)

        if not response.choices:
            logger.warning("vlm.response", extra={"image": image_path.name, "latency": latency, "status": "no_choices"})
            return EMPTY_RESULT

        raw = response.choices[0].message.content.strip()
        try:
            result = json.loads(raw)
            fields_count = sum(1 for v in result.values() if v is not None)
            fields_ratio = round(fields_count / len(RECOGNIZED_FIELDS), 3)
            logger.info("vlm.response", extra={
                "image": image_path.name, "latency": latency, "status": "ok",
                "fields_count": fields_count, "fields_ratio": fields_ratio,
            })
            return result
        except json.JSONDecodeError:
            logger.warning("vlm.parse_error", extra={
                "image": image_path.name, "latency": latency, "raw": raw,
            })
            return EMPTY_RESULT

    except Exception as exc:
        latency = round(time.monotonic() - start, 3)
        logger.error("vlm.exception", extra={"image": image_path.name, "latency": latency, "error": str(exc)})
        return EMPTY_RESULT


def recognize_tracks(tracks_path: Path, crops_per_track: int = 5):
    """
    Генератор. После обработки каждого трека yielдит:
      (current_track_index, total_tracks, predictions_so_far)

    Пример использования:
      results = []
      for i, total, batch in recognize_tracks(tracks_path):
          results.extend(batch)
    """
    client = OpenAI(base_url=LLM_BASE_URL, api_key="none")
    if ENABLE_OCR == "true":
        ocr = OCRService()

    track_dirs = sorted(tracks_path.glob("track_*"))
    total = len(track_dirs)

    for idx, track_dir in enumerate(track_dirs, start=1):
        track_id = int(track_dir.name.split("_")[1])
        crops = _sample_crops(track_dir, crops_per_track)
        if not crops:
            yield idx, total, []
            continue

        predictions = []
        for crop in crops:
            ocr_predict = []
            if ENABLE_OCR == "true":
                img = np.array(Image.open(crop))
                ocr_predict = ocr.predict([img])
            if len(ocr_predict) == 0:
                logger.warning("ocr.empty", extra={"crop": crop.name})
                ocr_predict = None
            else:
                ocr_predict = ocr_predict[0].texts

            llm_predict = _recognize_crop(client, crop, ocr_predict)
            predictions.append({"image": crop.name, "data": llm_predict})

        best_fields_count = max(
            sum(1 for f in RECOGNIZED_FIELDS if p["data"].get(f) is not None)
            for p in predictions
        )
        best_fields_ratio = round(best_fields_count / len(RECOGNIZED_FIELDS), 3)
        logger.info("track.completed", extra={
            "track_id": track_id, "num_crops": len(crops),
            "best_fields_count": best_fields_count, "best_fields_ratio": best_fields_ratio,
        })

        yield idx, total, [{"track_id": track_id, "predictions": predictions}]


def _aggregate_track(predictions: list[dict], meta: list[dict]) -> dict:
    # лучший кроп — больше всего непустых полей
    best = max(
        predictions,
        key=lambda p: sum(1 for f in RECOGNIZED_FIELDS if p["data"].get(f) is not None),
    )

    # агрегируем: сначала из лучшего, недостающее добираем из остальных
    result = {**EMPTY_RESULT}
    for pred in [best] + [p for p in predictions if p is not best]:
        for field in RECOGNIZED_FIELDS:
            if result[field] is None:
                result[field] = pred["data"].get(field)

    # bbox и timestamp от лучшего кропа
    best_meta = next(
        (m for m in meta if m["image"] == best["image"]), meta[0] if meta else {}
    )
    result["frame_timestamp"] = best_meta.get("timestamp")
    bbox = best_meta.get("bbox", [None, None, None, None])
    result["x_min"], result["y_min"], result["x_max"], result["y_max"] = bbox

    return result


def _postprocess_row(row: dict) -> dict:
    """
    Правила постобработки одной строки CSV:

    1. Если price_card заполнено, а price_discount нет →
       переносим price_card → price_discount, очищаем price_card.
       Логика: цена «по карте» семантически является скидочной ценой,
       и если отдельной акционной цены нет, она туда и идёт.

    2. Все оставшиеся None / пустые строки → "нет".
    """
    price_card = row.get("price_card")
    price_discount = row.get("price_discount")

    # Нормализуем: считаем пустую строку тоже «отсутствием»
    def is_empty(v) -> bool:
        return v is None or str(v).strip() in ("", "нет", "None")

    if not is_empty(price_card) and is_empty(price_discount):
        row["price_discount"] = price_card
        row["price_card"] = "нет"

    # Заполняем все пустые поля значением "нет"
    for field in FIELDS:
        if is_empty(row.get(field)):
            row[field] = "нет"

    return row


def save_to_csv(results: list[dict], csv_path: Path, filename: str, tracks_path: Path):
    rows = []

    for track in results:
        track_id = track["track_id"]
        meta_path = tracks_path / f"track_{track_id}" / "metadata.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else []

        row = {field: None for field in FIELDS}  # начинаем с None, postprocess заменит
        row.update(_aggregate_track(track["predictions"], meta))
        row["filename"] = filename

        row = _postprocess_row(row)
        rows.append(row)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
