"""Crop regressions with model/network dependencies replaced by doubles."""
import ast
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class APIError(Exception):
    pass


def load_module(name, path, dependencies):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', dependencies):
        spec.loader.exec_module(module)
    return module


class CropRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = SimpleNamespace(
            QR_CONFIDENCE=0.5, QR_DEVICE='cpu', QR_MODEL='unused',
            ENABLE_OCR='false', LLM_BASE_URL='unused', LLM_MODEL='test',
        )
        cls.qr = load_module('crop_regression.qr', 'recognizer/src/qr.py', {
            'crop_regression.config': config,
            'ultralytics': SimpleNamespace(YOLO=Mock()),
        })
        cls.recognizer = load_module(
            'crop_regression.recognizer', 'recognizer/src/recognizer.py', {
                'crop_regression.config': config,
                'openai': SimpleNamespace(APIError=APIError, OpenAI=Mock()),
            },
        )

    def test_cpu_qr_preserves_cuda_visibility_on_success_and_failure(self):
        for initial in (None, '0', '2,3'):
            for fail in (False, True):
                with self.subTest(initial=initial, fail=fail), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'crop.png'
                    Image.new('RGB', (16, 16)).save(path)

                    def predict(*args, **kwargs):
                        self.assertEqual(str(kwargs['device']), 'cpu')
                        self.assertNotIsInstance(kwargs['device'], str)
                        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
                        if fail:
                            raise RuntimeError('QR failed')
                        boxes = SimpleNamespace(
                            xyxy=Mock(), conf=Mock(),
                        )
                        boxes.xyxy.cpu.return_value.numpy.return_value = np.empty((0, 4))
                        boxes.conf.cpu.return_value.numpy.return_value = np.empty(0)
                        return [SimpleNamespace(boxes=boxes)]

                    with patch.dict(os.environ), patch.object(self.qr, '_get_model', return_value=SimpleNamespace(predict=predict)):
                        os.environ.pop('CUDA_VISIBLE_DEVICES', None)
                        if initial is not None:
                            os.environ['CUDA_VISIBLE_DEVICES'] = initial
                        if fail:
                            with self.assertRaises(RuntimeError):
                                self.qr.detect_qr(path)
                        else:
                            self.assertEqual(self.qr.detect_qr(path), [])
                        self.assertEqual(os.environ.get('CUDA_VISIBLE_DEVICES'), initial)

    def test_crop_reports_vlm_failures_while_video_keeps_fallback(self):
        for content in ('', '{broken', '[]'):
            client = Mock()
            client.chat.completions.create.return_value = SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(content=content), finish_reason='stop'),
            ])
            with self.subTest(content=content), patch.object(self.recognizer, '_encode_image', return_value='image'):
                with self.assertRaises(ValueError):
                    self.recognizer._recognize_crop(client, Path('crop.jpg'), strict=True)
                self.assertEqual(self.recognizer._recognize_crop(client, Path('crop.jpg')), self.recognizer.EMPTY_RESULT)

    def test_crop_reports_service_failure(self):
        client = Mock()
        client.chat.completions.create.side_effect = APIError('connection failed')
        with patch.object(self.recognizer, '_encode_image', return_value='image'):
            with self.assertRaisesRegex(RuntimeError, 'Сервис распознавания'):
                self.recognizer._recognize_crop(client, Path('crop.jpg'), strict=True)

    def test_failure_status_is_json_serializable(self):
        # Exercise the endpoint function without starting FastAPI or Redis.
        tree = ast.parse((ROOT / 'backend/src/main.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'get_status')
        function.decorator_list = []
        namespace = {'celery_app': Mock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
        for state in ('FAILURE', 'REVOKED'):
            namespace['celery_app'].AsyncResult.return_value = SimpleNamespace(state=state, result=ValueError('Ошибка обработки'))
            response = namespace['get_status']('task-id')
            self.assertEqual(json.loads(json.dumps(response))['result'], 'Ошибка обработки')


if __name__ == '__main__':
    unittest.main()
