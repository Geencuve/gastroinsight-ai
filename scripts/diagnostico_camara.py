"""Diagnóstico de cámaras: brillo, color y puntaje de detección de rostros."""
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / "ai_vision" / "ml_models" / "face_detection_yunet_2023mar.onnx"
haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

for index in range(3):
    for backend_name, backend in (("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF)):
        capture = cv2.VideoCapture(index, backend)
        if not capture.isOpened():
            print(f"Camara {index} [{backend_name}]: no disponible")
            capture.release()
            continue

        detector = cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), 0.30, 0.3, 50)
        brightness, colorfulness, best_score, yunet_frames, haar_frames, read = [], [], 0.0, 0, 0, 0
        shape = None

        for _ in range(40):
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            read += 1
            shape = frame.shape
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness.append(float(gray.mean()))
            b, g, r = cv2.split(frame.astype(np.int16))
            colorfulness.append(float(np.mean(np.abs(r - g)) + np.mean(np.abs(g - b))))
            h, w = frame.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
            if faces is not None and len(faces):
                yunet_frames += 1
                best_score = max(best_score, float(faces[:, 14].max()))
            if len(haar.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))):
                haar_frames += 1
            del frame, gray
        capture.release()

        if not read:
            print(f"Camara {index} [{backend_name}]: abre pero no entrega imagen")
            continue
        tipo = "color" if np.mean(colorfulness) > 4 else "GRIS / posible camara infrarroja"
        print(
            f"Camara {index} [{backend_name}]: {shape[1]}x{shape[0]} | brillo {np.mean(brightness):.0f}/255 | {tipo} | "
            f"YuNet: rostro en {yunet_frames}/{read} frames, puntaje max {best_score:.2f} | "
            f"Haar: rostro en {haar_frames}/{read} frames"
        )
