"""
Detector local de mesas y personas (YOLO26 Small, entrenado por el equipo en Roboflow).

- Se ejecuta en el equipo con ONNX Runtime (CPU) o, si no está instalado, con OpenCV DNN.
- Ninguna imagen se envía a servicios externos.
- Entrada del modelo: 640x640 RGB, BCHW, valores 0-1, redimensionado "stretch" (sin letterbox).
- Salida: (1, 6, 8400) = cx, cy, w, h y una puntuación por clase (0 dining_table, 1 person).
"""
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent.parent / "ml_models"
SCENE_MODEL_FILE = "mesas_personas_yolo26s.onnx"
CLASS_NAMES = {0: "dining_table", 1: "person"}
INPUT_SIZE = 640
DEFAULT_CONFIDENCE = 0.17
DEFAULT_IOU = 0.45


class SceneModelNotAvailable(RuntimeError):
    pass


def postprocess(output, image_width, image_height, confidence=DEFAULT_CONFIDENCE, iou=DEFAULT_IOU):
    """Convierte la salida (1, 6, N) del modelo en detecciones con el formato de Roboflow."""
    predictions = np.asarray(output, dtype=np.float32)[0].T
    scores = predictions[:, 4:]
    class_ids = scores.argmax(axis=1)
    best = scores[np.arange(len(scores)), class_ids]
    keep = best >= confidence
    if not np.any(keep):
        return []
    boxes, best, class_ids = predictions[keep, :4], best[keep], class_ids[keep]

    sx, sy = image_width / INPUT_SIZE, image_height / INPUT_SIZE
    cx, cy = boxes[:, 0] * sx, boxes[:, 1] * sy
    w, h = boxes[:, 2] * sx, boxes[:, 3] * sy
    rects = np.stack([cx - w / 2, cy - h / 2, w, h], axis=1)

    detections = []
    for class_id in np.unique(class_ids):
        idx = np.where(class_ids == class_id)[0]
        chosen = cv2.dnn.NMSBoxes(rects[idx].tolist(), best[idx].tolist(), confidence, iou)
        for i in np.array(chosen).flatten():
            j = idx[int(i)]
            detections.append({
                "x": round(float(cx[j]), 1), "y": round(float(cy[j]), 1),
                "width": round(float(w[j]), 1), "height": round(float(h[j]), 1),
                "confidence": round(float(best[j]), 3),
                "class": CLASS_NAMES.get(int(class_id), str(int(class_id))),
                "class_id": int(class_id),
                "detection_id": str(uuid.uuid4()),
            })
    detections.sort(key=lambda d: -d["confidence"])
    return detections


def assign_people_to_tables(detections, max_distance_factor=1.6):
    """Asigna cada persona a la mesa más cercana (pie de la persona vs. centro de la mesa)."""
    tables = [d for d in detections if d["class"] == "dining_table"]
    people = [d for d in detections if d["class"] == "person"]
    result = [{"table_index": i, "x": t["x"], "y": t["y"], "people": 0} for i, t in enumerate(tables)]
    unassigned = 0
    for person in people:
        px, py = person["x"], person["y"] + person["height"] / 2
        best, best_distance = None, None
        for i, table in enumerate(tables):
            distance = ((px - table["x"]) ** 2 + (py - table["y"]) ** 2) ** 0.5
            limit = max_distance_factor * max(table["width"], table["height"], person["height"] / 2)
            if distance <= limit and (best_distance is None or distance < best_distance):
                best, best_distance = i, distance
        if best is None:
            unassigned += 1
        else:
            result[best]["people"] += 1
    return {"tables": result, "people_unassigned": unassigned}


class SceneDetector:
    def __init__(self, model_path=None, confidence=DEFAULT_CONFIDENCE, iou=DEFAULT_IOU, engine="auto"):
        self.model_path = Path(model_path or MODELS_DIR / SCENE_MODEL_FILE)
        if not self.model_path.exists():
            raise SceneModelNotAvailable(
                f"No se encontró el modelo de mesas y personas en {self.model_path}. "
                f"Copia el archivo ONNX del equipo como ai_vision/ml_models/{SCENE_MODEL_FILE}."
            )
        self.confidence, self.iou = confidence, iou
        self.engine, self._session, self._net = None, None, None
        if engine in ("auto", "onnxruntime"):
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
                self._input_name = self._session.get_inputs()[0].name
                self.engine = "onnxruntime"
            except ImportError:
                if engine == "onnxruntime":
                    raise
        if self.engine is None:
            self._net = cv2.dnn.readNetFromONNX(str(self.model_path))
            self.engine = "opencv-dnn"

    @staticmethod
    def preprocess(image_bgr):
        resized = cv2.resize(image_bgr, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return np.ascontiguousarray(rgb.transpose(2, 0, 1)[None])

    def detect(self, image_bgr):
        height, width = image_bgr.shape[:2]
        tensor = self.preprocess(image_bgr)
        started = time.perf_counter()
        if self._session is not None:
            output = self._session.run(None, {self._input_name: tensor})[0]
        else:
            self._net.setInput(tensor)
            output = self._net.forward()
        elapsed_ms = (time.perf_counter() - started) * 1000
        return postprocess(output, width, height, self.confidence, self.iou), elapsed_ms


def draw(image_bgr, detections):
    """Dibuja las detecciones (solo para imágenes o videos de prueba)."""
    colors = {"dining_table": (238, 211, 34), "person": (246, 92, 139)}
    canvas = image_bgr.copy()
    for d in detections:
        x0, y0 = int(d["x"] - d["width"] / 2), int(d["y"] - d["height"] / 2)
        x1, y1 = int(d["x"] + d["width"] / 2), int(d["y"] + d["height"] / 2)
        color = colors.get(d["class"], (200, 200, 200))
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2)
        label = f"{'mesa' if d['class'] == 'dining_table' else 'persona'} {d['confidence']:.2f}"
        cv2.putText(canvas, label, (x0, max(14, y0 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    return canvas


def iou_xywh(a, b):
    ax0, ay0 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
    ax1, ay1 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
    bx0, by0 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
    bx1, by1 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    inter = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(0.0, min(ay1, by1) - max(ay0, by0))
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union > 0 else 0.0


def compare_with_reference(local, reference, iou_threshold=0.5):
    """Compara detecciones locales con las de Roboflow: coincidencias por clase con IoU >= umbral."""
    used, ious = set(), []
    for ref in sorted(reference, key=lambda d: -d.get("confidence", 0)):
        best, best_iou = None, iou_threshold
        for i, det in enumerate(local):
            if i in used or det["class"] != ref["class"]:
                continue
            value = iou_xywh(det, ref)
            if value >= best_iou:
                best, best_iou = i, value
        if best is not None:
            used.add(best)
            ious.append(best_iou)
    matches = len(ious)
    return {
        "reference": len(reference), "local": len(local), "matches": matches,
        "recall_vs_reference": round(100 * matches / len(reference), 1) if reference else None,
        "precision_vs_reference": round(100 * matches / len(local), 1) if local else None,
        "mean_iou": round(float(np.mean(ious)), 3) if ious else None,
    }
