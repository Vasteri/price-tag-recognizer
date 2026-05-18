from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from paddleocr import PaddleOCR
#from pyzbar import pyzbar


@dataclass(frozen=True)
class OCRResult:
    """
    Структура данных, содержащая результаты OCR-инференса для одного изображения.

    Attributes:
        texts (List[str]): Список распознанных текстовых строк.
        confidences (List[float]): Соответствующий список коэффициентов уверенности модели.
    """

    texts: List[str]
    confidences: List[float]


class OCRService:
    """
    Сервис для распознавания текста на изображениях с использованием PaddleOCR.

    Класс инкапсулирует логику инициализации моделей детектирования и
    распознавания текста, а также предоставляет методы для пакетной обработки изображений.
    """

    def __init__(
        self,
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="cyrillic_PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        use_textline_orientation=True,
        text_det_thresh=0.3,
        text_det_box_thresh=0.6,
        text_det_unclip_ratio=1.5,
        text_det_limit_side_len=960,
        enable_mkldnn=False,
    ):

        self._model = PaddleOCR(
            text_detection_model_name=text_detection_model_name,
            text_recognition_model_name=text_recognition_model_name,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            text_det_thresh=text_det_thresh,
            text_det_box_thresh=text_det_box_thresh,
            text_det_unclip_ratio=text_det_unclip_ratio,
            text_det_limit_side_len=text_det_limit_side_len,
            enable_mkldnn=enable_mkldnn,
        )

    def predict(self, crops) -> list[OCRResult]:
        results = self._model.predict(crops)
        return self._parse_results(results)

    def _parse_results(self, results) -> list[OCRResult]:
        parsed_results = []
        for result in results:
            texts = result.get("rec_texts", [])
            scores = result.get("rec_scores", [])

            parsed_results.append(OCRResult(texts=texts, confidences=scores))

        return parsed_results


# @dataclass(frozen=True)
# class QRResult:
#     """
#     Контейнер данных для результата декодирования QR-кода.

#     Attributes:
#         data (bytes): Сырые данные, извлеченные из QR-кода.
#         type (str): Тип/формат QR-кода (например, 'QRCODE').
#     """

#     data: bytes
#     type: str


# class QRService:
#     """
#     Сервис для декодирования QR-кодов с помощью библиотеки pyzbar.
#     """

#     def __init__(self):

#         self._model = pyzbar

#     def predict(self, crops) -> list[QRResult]:
#         results = []

#         for crop in crops:
#             qr = self._model.decode(crop)
#             results.append(QRResult(data=qr[0].data, type=qr[0].type))

#         return results


# @dataclass(frozen=True)
# class AggregatedTrack:
#     """
#     Итоговый агрегированный результат для одного отслеженного (tracked) объекта.

#     Класс хранит "лучшие" данные, выбранные из истории трека по результатам всех кадров.
#     """

#     track_id: int
#     ocr_text: str
#     ocr_confidence: float
#     qr_data: Optional[bytes]
#     qr_type: Optional[str]
#     num_frames_used: int

#     def to_dict(self):
#         return asdict(self)


# class TrackingAggregator:
#     """
#     Управляет состоянием отслеженных объектов (треков) и выполняет агрегацию данных.

#     Класс накапливает результаты инференса (OCR/QR) для каждого `track_id` по мере
#     поступления кадров. При завершении трека выполняет выборку наиболее вероятных
#     данных (агрегацию) для формирования итогового отчета.
#     """

#     def __init__(self, ocr_conf_threshold: float = 0.7):
#         self.ocr_conf_threshold = ocr_conf_threshold
#         self.track_history: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

#     def process_batch(
#         self,
#         track_ids: List[int],
#         ocr_results: List[OCRResult],
#         qr_results: List[Optional[QRResult]],
#     ):
#         for i, tid in enumerate(track_ids):
#             self.track_history[tid].append({"ocr": ocr_results[i], "qr": qr_results[i]})

#     def finalize_track(self, track_id: int) -> Optional[AggregatedTrack]:
#         history = self.track_history.pop(track_id, [])
#         if not history:
#             return None

#         ocr_list = [h["ocr"] for h in history]
#         qr_list = [h["qr"] for h in history if h["qr"] is not None]

#         best_text, best_conf = self._aggregate_ocr(ocr_list)
#         qr_data, qr_type = self._aggregate_qr(qr_list)

#         return AggregatedTrack(
#             track_id=track_id,
#             ocr_text=best_text,
#             ocr_confidence=best_conf,
#             qr_data=qr_data,
#             qr_type=qr_type,
#             num_frames_used=len(history),
#         )

#     def _aggregate_ocr(self, ocr_results: List[OCRResult]) -> Tuple[str, float]:
#         best_text = ""
#         max_avg_conf = -1.0

#         for res in ocr_results:
#             if not res.confidences:
#                 continue

#             avg_conf = sum(res.confidences) / len(res.confidences)

#             if avg_conf > max_avg_conf:
#                 max_avg_conf = avg_conf
#                 best_text = " ".join(res.texts)

#         return best_text, max_avg_conf

#     def _aggregate_qr(
#         self, qr_results: List[QRResult]
#     ) -> Tuple[Optional[bytes], Optional[str]]:
#         if not qr_results:
#             return None, None

#         counts = Counter([(res.data, res.type) for res in qr_results])
#         (best_data, best_type), _ = counts.most_common(1)[0]

#         return best_data, best_type
