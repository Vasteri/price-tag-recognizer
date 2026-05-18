# recognizer/qwen.py

import base64
import json
import random
from pathlib import Path

from openai import OpenAI

from .config import LLM_BASE_URL, LLM_MODEL

#LLM_BASE_URL = "http://host.docker.internal:12434/v1"
#LLM_MODEL = "ai/qwen3-vl:2B-UD-Q4_K_XL"  # уточни через `docker model list`

EMPTY_RESULT = {
    "product_name": None,
    "price_default": None,
    "price_card": None,
    "price_discount": None,
    "barcode": None,
    "discount_amount": None,
    "id_sku": None,
    "print_datetime": None,
    "code": None,
    "additional_info": None,
    "color": None,
    "special_symbols": None,
}

PRICE_TAG_PROMPT = """Ты — система распознавания ценников в российских магазинах.
На изображении фрагмент ценника. Верни ТОЛЬКО валидный JSON без markdown и пояснений.

Поля:
- product_name: полное название товара с объёмом/весом, например "Напиток безалкогольный SANTO STEFANO Rosso 0,25L"
- price_default: обычная цена (число с копейками через точку), например 252.63
- price_card: цена по карте лояльности (число), например 129.99
- price_discount: цена по акции если есть (число), например 99.99
- barcode: штрихкод (строка цифр), например "4670025474665"
- discount_amount: размер скидки если указан, например "-48%"
- id_sku: внутренний артикул/SKU магазина (строка цифр)
- print_datetime: дата и время печати ценника, например "03.04.2026 3:08"
- code: код на ценнике если есть (отличается от штрихкода и SKU)
- additional_info: любая дополнительная информация (страна, состав, пометки)
- color: цвет ценника (red, yellow, green, white, blue или другой)
- special_symbols: спецсимволы или пометки на ценнике (звёздочки, значки и т.п.)

Если поле не читается или отсутствует — null.

Пример ответа:
{
  "product_name": "Напиток безалкогольный SANTO STEFANO Rosso (Россия) 0,25L",
  "price_default": 252.63,
  "price_card": 129.99,
  "price_discount": null,
  "barcode": "4670025474665",
  "discount_amount": "-48%",
  "id_sku": "270207736530",
  "print_datetime": "03.04.2026 3:08",
  "code": null,
  "additional_info": null,
  "color": "red",
  "special_symbols": null
}"""


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
                    {"type": "text", "text": PRICE_TAG_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{_encode_image(image_path)}"
                        },
                    },
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
