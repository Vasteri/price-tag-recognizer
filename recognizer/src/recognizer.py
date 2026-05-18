import base64
import csv
import json
import random
from pathlib import Path

from openai import OpenAI

from .config import LLM_BASE_URL, LLM_MODEL

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

PRICE_TAG_PROMPT = """Ты — система распознавания ценников в российских магазинах.
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
- special_symbols (string): спецсимволы или пометки на ценнике"""

SCHEMA_IMAGE = _encode_image(Path(__file__).parent / "assets" / "scheme_price_tag.jpg")


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _sample_crops(track_dir: Path, n: int) -> list[Path]:
    """Равномерно сэмплируем не более n кропов из трека."""
    images = sorted((track_dir / "images").glob("*.jpg"))
    if not images:
        return []
    random.shuffle(images)
    return images[:n]


def _recognize_crop(client: OpenAI, image_path: Path) -> dict:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Схема расположения полей на ценнике:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{SCHEMA_IMAGE}"},
                    },
                    {
                        "type": "text",
                        "text": "Распознай следующий ценник согласно схеме:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{_encode_image(image_path)}"
                        },
                    },
                    {"type": "text", "text": PRICE_TAG_PROMPT},
                ],
            }
        ],
        max_tokens=512,
    )
    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return EMPTY_RESULT


def recognize_tracks(tracks_path: Path, crops_per_track: int = 3) -> list[dict]:
    """
    Возвращает сырые предсказания по каждому кропу каждого трека:
    [
      {
        "track_id": 1,
        "predictions": [
          {"image": "frame_0004.jpg", "data": {...}},
          ...
        ]
      },
      ...
    ]
    """
    client = OpenAI(base_url=LLM_BASE_URL, api_key="none")
    output = []

    for track_dir in sorted(tracks_path.glob("track_*")):
        track_id = int(track_dir.name.split("_")[1])
        crops = _sample_crops(track_dir, crops_per_track)
        if not crops:
            continue

        predictions = [
            {"image": crop.name, "data": _recognize_crop(client, crop)}
            for crop in crops
        ]
        output.append({"track_id": track_id, "predictions": predictions})

    return output


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


def save_to_csv(results: list[dict], csv_path: Path, filename: str, tracks_path: Path):
    rows = []

    for track in results:
        track_id = track["track_id"]
        meta_path = tracks_path / f"track_{track_id}" / "metadata.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else []

        row = {field: "нет" for field in FIELDS}
        row.update(_aggregate_track(track["predictions"], meta))
        row["filename"] = filename
        rows.append(row)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
