"""
Pipeline de visión no biométrica de GastroInsight AI.

- Detección de rostros: YuNet (CNN, OpenCV Zoo), entrega puntaje de confianza.
- Expresiones faciales: FER+ (CNN entrenada con FER+), 8 categorías.

Los fotogramas se procesan solo en memoria: este módulo nunca escribe
imágenes en disco ni conserva recortes de rostros.
"""
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from django.conf import settings

MODELS_DIR = Path(
    getattr(settings, "AI_MODELS_DIR", Path(__file__).resolve().parent.parent / "ml_models")
)
YUNET_FILE = "face_detection_yunet_2023mar.onnx"
FERPLUS_FILE = "emotion-ferplus-8.onnx"

FERPLUS_LABELS = (
    "neutral", "happiness", "surprise", "sadness",
    "anger", "disgust", "fear", "contempt",
)
# Etiquetas FER+ -> valores de DetectionEvent.Emotion
TO_EMOTION = {
    "neutral": "neutral",
    "happiness": "happy",
    "surprise": "surprised",
    "sadness": "sad",
    "anger": "angry",
    "disgust": "disgust",
    "fear": "fear",
    "contempt": "contempt",
}


class ModelsNotAvailable(RuntimeError):
    """Los archivos de modelo no están descargados."""


def _softmax(values):
    exp = np.exp(values - np.max(values))
    return exp / exp.sum()


class VisionPipeline:
    def __init__(self, score_threshold=0.70, models_dir=None):
        directory = Path(models_dir) if models_dir else MODELS_DIR
        yunet = directory / YUNET_FILE
        ferplus = directory / FERPLUS_FILE
        missing = [path.name for path in (yunet, ferplus) if not path.exists()]
        if missing:
            raise ModelsNotAvailable(
                "Faltan modelos de visión: " + ", ".join(missing)
                + ". Ejecuta: python scripts/download_models.py"
            )
        self.score_threshold = score_threshold
        self.detector = cv2.FaceDetectorYN.create(
            str(yunet), "", (320, 320), score_threshold, 0.3, 50,
        )
        self.fer = cv2.dnn.readNetFromONNX(str(ferplus))

    def analyze(self, frame):
        """Analiza un fotograma BGR y retorna rostros con su expresión estimada."""
        start = perf_counter()
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        faces = faces if faces is not None else []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        results = []
        for face in faces:
            x, y, w, h = (int(v) for v in face[:4])
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(width, x + w), min(height, y + h)
            if x1 - x0 < 20 or y1 - y0 < 20:
                continue
            crop = cv2.resize(gray[y0:y1, x0:x1], (64, 64))
            self.fer.setInput(crop.reshape(1, 1, 64, 64).astype(np.float32))
            probs = _softmax(self.fer.forward()[0])
            index = int(np.argmax(probs))
            results.append({
                "box": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                "detector_score": float(face[14]),
                "emotion": TO_EMOTION[FERPLUS_LABELS[index]],
                "emotion_confidence": float(probs[index]),
            })
            del crop
        del gray

        return {
            "faces_count": len(results),
            "faces": results,
            "processing_time_ms": int((perf_counter() - start) * 1000),
        }


class EventWindow:
    """Acumula resultados de varios fotogramas para guardar un evento agregado."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.frames = 0
        self.max_faces = 0
        self.emotions = Counter()
        self.emotion_confidences = defaultdict(list)
        self.detector_scores = []
        self.times = []

    def add(self, result):
        self.frames += 1
        self.max_faces = max(self.max_faces, result["faces_count"])
        self.times.append(result["processing_time_ms"])
        for face in result["faces"]:
            self.emotions[face["emotion"]] += 1
            self.emotion_confidences[face["emotion"]].append(face["emotion_confidence"])
            self.detector_scores.append(face["detector_score"])

    def summary(self):
        if self.emotions:
            dominant = self.emotions.most_common(1)[0][0]
            confidence = float(np.mean(self.emotion_confidences[dominant]))
        else:
            dominant, confidence = "unknown", None
        return {
            "faces_count": self.max_faces,
            "estimated_emotion": dominant,
            "confidence": confidence,
            "detector_confidence": float(np.mean(self.detector_scores)) if self.detector_scores else None,
            "emotion_distribution": dict(self.emotions),
            "processing_time_ms": int(np.mean(self.times)) if self.times else None,
            "frames_in_window": self.frames,
        }
