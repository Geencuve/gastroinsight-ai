"""
Datos para entrenamiento: procesamiento con consentimiento, evaluación con matriz de
confusión y calibración supervisada sobre las salidas de FER+.

Minimización de datos: de cada imagen se guarda solo el recorte del rostro en escala de
grises (128x128). La imagen original se descarta en memoria.
"""
import uuid
from collections import Counter

import cv2
import numpy as np
from django.core.files.base import ContentFile
from django.db import transaction

from ai_vision.models import (
    TRAINING_ATTENTION_LABELS, TRAINING_EXPRESSION_LABELS, CalibrationModel, TrainingSample,
)
from ai_vision.services.vision_pipeline import (
    EMOTION_ORDER, LOOKING_AWAY_YAW, VisionPipeline, _softmax, calibrated_emotion,
)

EXPRESSION = TrainingSample.Kind.EXPRESSION
ATTENTION = TrainingSample.Kind.ATTENTION
NAMES = dict(TRAINING_EXPRESSION_LABELS + TRAINING_ATTENTION_LABELS)
MIN_PER_LABEL = 3
MIN_TOTAL = 12
_PIPELINE = None


def _pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = VisionPipeline(score_threshold=0.6)
    return _PIPELINE


def load_active_calibrations():
    expression = CalibrationModel.objects.filter(kind=EXPRESSION, active=True).order_by("-created_at").first()
    attention = CalibrationModel.objects.filter(kind=ATTENTION, active=True).order_by("-created_at").first()
    return {
        "expression": expression.weights if expression else None,
        "attention_threshold": attention.weights.get("threshold") if attention else None,
    }


def current_attention_threshold():
    return load_active_calibrations()["attention_threshold"] or LOOKING_AWAY_YAW


def process_upload(uploaded, kind, label, user=None, venue=None):
    """Procesa una imagen: detecta el rostro, guarda solo el recorte y las salidas del modelo."""
    data = np.frombuffer(uploaded.read(), np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None, f"{uploaded.name}: no es una imagen válida."
    height, width = image.shape[:2]
    scale = min(1.0, 960 / max(width, height))
    if scale < 1.0:
        image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        height, width = image.shape[:2]

    pipeline = _pipeline()
    pipeline.detector.setInputSize((width, height))
    _, faces = pipeline.detector.detect(image)
    if faces is None or not len(faces):
        return None, f"{uploaded.name}: no se detectó un rostro con confianza suficiente."
    face = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = (int(v) for v in face[:4])
    x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None, f"{uploaded.name}: el rostro es demasiado pequeño."

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    crop = gray[y0:y1, x0:x1]
    pipeline.fer.setInput(cv2.resize(crop, (64, 64)).reshape(1, 1, 64, 64).astype(np.float32))
    probs = _softmax(pipeline.fer.forward()[0])
    eye_distance = abs(face[6] - face[4]) or 1.0
    yaw = float((face[8] - (face[4] + face[6]) / 2) / eye_distance)
    ok, png = cv2.imencode(".png", cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA))
    del image, gray, crop
    if not ok:
        return None, f"{uploaded.name}: no se pudo procesar el recorte."

    if kind == ATTENTION:
        predicted = "seeking" if abs(yaw) > current_attention_threshold() else "attentive"
        confidence = None
    else:
        index = int(np.argmax(probs))
        predicted, confidence = EMOTION_ORDER[index], float(probs[index])

    sample = TrainingSample(
        kind=kind, label=label, consent_confirmed=True, uploaded_by=user, venue=venue,
        probabilities=[round(float(p), 5) for p in probs], predicted_label=predicted,
        predicted_confidence=confidence, detector_score=float(face[14]), yaw=yaw,
    )
    sample.image.save(f"muestra_{uuid.uuid4().hex[:12]}.png", ContentFile(png.tobytes()), save=False)
    sample.save()
    return sample, None


def _matrix(true, pred, labels):
    rows = []
    for real in labels:
        predictions = [p for t, p in zip(true, pred) if t == real]
        total = len(predictions)
        cells = []
        for predicted in labels:
            count = sum(1 for p in predictions if p == predicted)
            alpha = round(0.12 + 0.78 * count / total, 2) if total and count else 0
            cells.append({"value": count, "alpha": alpha, "diag": predicted == real})
        hits = sum(1 for p in predictions if p == real)
        rows.append({"label": NAMES.get(real, real), "cells": cells, "total": total,
                     "recall": 100 * hits / total if total else None})
    return {"labels": [NAMES.get(l, l) for l in labels], "rows": rows}


def _ordered(labels_set, order):
    return [l for l in order if l in labels_set]


def expression_samples():
    return [s for s in TrainingSample.objects.filter(kind=EXPRESSION) if s.probabilities]


def evaluate_expression(weights=None):
    samples = expression_samples()
    if not samples:
        return None
    true = [s.label for s in samples]
    if weights:
        pred = [calibrated_emotion(s.probabilities, weights)[0] for s in samples]
    else:
        pred = [EMOTION_ORDER[int(np.argmax(s.probabilities))] for s in samples]
    labels = _ordered(set(true) | set(pred), EMOTION_ORDER)
    accuracy = 100 * sum(t == p for t, p in zip(true, pred)) / len(true)
    return {"total": len(true), "accuracy": accuracy, **_matrix(true, pred, labels)}


def can_train_expression():
    counts = Counter(s.label for s in expression_samples())
    valid = {label for label, count in counts.items() if count >= MIN_PER_LABEL}
    return len(valid) >= 2 and sum(counts[l] for l in valid) >= MIN_TOTAL


def train_expression_calibration(user=None):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    samples = expression_samples()
    counts = Counter(s.label for s in samples)
    valid = {label for label, count in counts.items() if count >= MIN_PER_LABEL}
    samples = [s for s in samples if s.label in valid]
    if len(valid) < 2 or len(samples) < MIN_TOTAL:
        raise ValueError(f"Se necesitan al menos {MIN_TOTAL} imágenes de 2 o más expresiones, "
                         f"con {MIN_PER_LABEL} o más por expresión.")

    features = np.log(np.clip(np.array([s.probabilities for s in samples], dtype=float), 1e-6, 1.0))
    labels = np.array([s.label for s in samples])
    folds = min(5, min(counts[l] for l in valid))
    model = LogisticRegression(max_iter=2000, class_weight="balanced")
    cross_pred = cross_val_predict(model, features, labels,
                                   cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=7))
    base_pred = [EMOTION_ORDER[int(np.argmax(s.probabilities))] for s in samples]
    true = [str(l) for l in labels]
    accuracy_before = 100 * float(np.mean(np.array(base_pred) == labels))
    accuracy_after = 100 * float(np.mean(cross_pred == labels))
    model.fit(features, labels)

    order = _ordered(set(true) | set(base_pred) | {str(p) for p in cross_pred}, EMOTION_ORDER)
    return CalibrationModel.objects.create(
        kind=EXPRESSION, created_by=user, samples_count=len(samples),
        accuracy_before=round(accuracy_before, 1), accuracy_after=round(accuracy_after, 1),
        labels=_ordered(valid, EMOTION_ORDER),
        weights={"coef": model.coef_.tolist(), "intercept": model.intercept_.tolist(),
                 "classes": [str(c) for c in model.classes_]},
        confusion_before=_matrix(true, base_pred, order),
        confusion_after=_matrix(true, [str(p) for p in cross_pred], order),
        notes=f"Regresión logística sobre FER+, validación cruzada estratificada de {folds} pliegues.",
    )


@transaction.atomic
def activate_calibration(calibration, active=True):
    if active:
        CalibrationModel.objects.filter(kind=calibration.kind, active=True).exclude(pk=calibration.pk).update(active=False)
    calibration.active = active
    calibration.save(update_fields=["active"])


def evaluate_attention():
    samples = [s for s in TrainingSample.objects.filter(kind=ATTENTION) if s.yaw is not None]
    if not samples:
        return None
    threshold = current_attention_threshold()
    true = [s.label for s in samples]

    def accuracy_at(value):
        pred = ["seeking" if abs(s.yaw) > value else "attentive" for s in samples]
        return 100 * sum(t == p for t, p in zip(true, pred)) / len(true), pred

    accuracy, pred = accuracy_at(threshold)
    candidates = [round(float(t), 2) for t in np.arange(0.10, 0.81, 0.05)]
    scored = [(accuracy_at(t)[0], -abs(t - threshold), t) for t in candidates]
    best_accuracy, _, best = max(scored)
    return {
        "total": len(true), "accuracy": accuracy, "threshold": round(threshold, 2),
        "suggested": best, "suggested_accuracy": best_accuracy,
        "can_suggest": len(set(true)) == 2 and len(true) >= 6,
        **_matrix(true, pred, ["attentive", "seeking"]),
    }


def apply_attention_threshold(threshold, user=None):
    evaluation = evaluate_attention()
    calibration = CalibrationModel.objects.create(
        kind=ATTENTION, created_by=user, samples_count=evaluation["total"] if evaluation else 0,
        accuracy_before=round(evaluation["accuracy"], 1) if evaluation else None,
        accuracy_after=round(evaluation["suggested_accuracy"], 1) if evaluation else None,
        weights={"threshold": threshold}, labels=["attentive", "seeking"],
        notes=f"Umbral de giro de cabeza ajustado a {threshold:.2f}.",
    )
    activate_calibration(calibration, True)
    return calibration
