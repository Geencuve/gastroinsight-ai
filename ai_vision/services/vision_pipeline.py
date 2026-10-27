"""
Pipeline de visión no biométrica de GastroInsight AI.

- Detección de rostros: YuNet (CNN, OpenCV Zoo) sobre una imagen reducida.
- Expresiones faciales: FER+ (CNN, 8 categorías) sobre el recorte original.
- Actividad: diferencia entre miniaturas borrosas de 64x48 de fotogramas consecutivos.

Los fotogramas se procesan solo en memoria: este módulo nunca escribe imágenes en
disco ni conserva recortes de rostros. La miniatura de actividad se sobrescribe en
cada fotograma y no permite identificar personas.
"""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
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
TO_EMOTION = {
    "neutral": "neutral", "happiness": "happy", "surprise": "surprised", "sadness": "sad",
    "anger": "angry", "disgust": "disgust", "fear": "fear", "contempt": "contempt",
}


# Peso de cada expresión FER+ en la valencia (-1 negativa, +1 positiva)
VALENCE_VECTOR = np.array([0.0, 1.0, 0.3, -0.8, -1.0, -0.9, -0.7, -0.8])
LOOKING_AWAY_YAW = 0.35  # desplazamiento de la nariz respecto del centro de los ojos


class ModelsNotAvailable(RuntimeError):
    """Los archivos de modelo no están descargados."""


def _softmax(values):
    exp = np.exp(values - np.max(values))
    return exp / exp.sum()


class VisionPipeline:
    def __init__(self, score_threshold=0.70, models_dir=None, max_width=640):
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
        self.max_width = max_width
        self.detector = cv2.FaceDetectorYN.create(str(yunet), "", (320, 320), score_threshold, 0.3, 50)
        self.fer = cv2.dnn.readNetFromONNX(str(ferplus))
        self._previous_thumb = None

    def _activity(self, gray_small):
        thumb = cv2.GaussianBlur(cv2.resize(gray_small, (64, 48), interpolation=cv2.INTER_AREA), (3, 3), 0)
        activity = None
        if self._previous_thumb is not None:
            activity = min(100.0, float(cv2.absdiff(thumb, self._previous_thumb).mean()) * 100 / 25)
        self._previous_thumb = thumb
        return activity

    def analyze(self, frame, classify=True):
        """Analiza un fotograma BGR. Si classify=False solo detecta (sin FER+)."""
        start = perf_counter()
        height, width = frame.shape[:2]
        scale = min(1.0, self.max_width / width) if self.max_width else 1.0
        if scale < 1.0:
            small = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        else:
            small = frame
        small_h, small_w = small.shape[:2]
        self.detector.setInputSize((small_w, small_h))
        _, faces = self.detector.detect(small)
        faces = faces if faces is not None else []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small_gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if scale < 1.0 else gray
        activity = self._activity(small_gray)

        results = []
        for face in faces:
            x, y, w, h = (int(v / scale) for v in face[:4])
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(width, x + w), min(height, y + h)
            if x1 - x0 < 20 or y1 - y0 < 20:
                continue
            # Dirección de la cabeza con los puntos faciales de YuNet (ojos y nariz)
            right_eye_x, left_eye_x, nose_x = face[4] / scale, face[6] / scale, face[8] / scale
            eye_distance = abs(left_eye_x - right_eye_x) or 1.0
            yaw = (nose_x - (right_eye_x + left_eye_x) / 2) / eye_distance
            emotion, emotion_confidence, valence = None, None, None
            if classify:
                crop = cv2.resize(gray[y0:y1, x0:x1], (64, 64))
                self.fer.setInput(crop.reshape(1, 1, 64, 64).astype(np.float32))
                probs = _softmax(self.fer.forward()[0])
                index = int(np.argmax(probs))
                emotion, emotion_confidence = TO_EMOTION[FERPLUS_LABELS[index]], float(probs[index])
                valence = float(np.clip(np.dot(probs, VALENCE_VECTOR), -1.0, 1.0))
                del crop
            results.append({
                "box": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                "detector_score": float(face[14]),
                "emotion": emotion,
                "emotion_confidence": emotion_confidence,
                "valence": valence,
                "yaw": float(yaw),
                "looking_away": bool(abs(yaw) > LOOKING_AWAY_YAW),
            })
        del gray, small_gray, small

        return {
            "faces_count": len(results),
            "faces": results,
            "activity": activity,
            "classified": classify,
            "processing_time_ms": int((perf_counter() - start) * 1000),
        }


class EventWindow:
    """Acumula resultados de varios fotogramas para guardar un evento agregado."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.frames = 0
        self.max_faces = 0
        self.faces_per_frame = []
        self.frames_with_faces = 0
        self.activity = []
        self.valences = []
        self.faces_seen = 0
        self.faces_away = 0
        self.emotions = Counter()
        self.emotion_confidences = defaultdict(list)
        self.detector_scores = []
        self.times = []

    def add(self, result):
        self.frames += 1
        count = result["faces_count"]
        self.max_faces = max(self.max_faces, count)
        self.faces_per_frame.append(count)
        if count:
            self.frames_with_faces += 1
        if result.get("activity") is not None:
            self.activity.append(result["activity"])
        self.times.append(result["processing_time_ms"])
        for face in result["faces"]:
            self.detector_scores.append(face["detector_score"])
            self.faces_seen += 1
            if face.get("looking_away"):
                self.faces_away += 1
            if face.get("valence") is not None:
                self.valences.append(face["valence"])
            if face.get("emotion"):
                self.emotions[face["emotion"]] += 1
                self.emotion_confidences[face["emotion"]].append(face["emotion_confidence"])

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
            "occupancy": float(median(self.faces_per_frame)) if self.faces_per_frame else None,
            "presence_ratio": self.frames_with_faces / self.frames if self.frames else None,
            "activity_level": float(np.mean(self.activity)) if self.activity else None,
            "valence": float(np.mean(self.valences)) if self.valences else None,
            "attention_seeking": self.faces_away / self.faces_seen if self.faces_seen else None,
        }
