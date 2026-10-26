import time
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent.parent / "ai_vision" / "ml_models" / "face_detection_yunet_2023mar.onnx"
detector = cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), 0.30, 0.3, 50)
capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
previous, motion, best = None, [], 0.0
end = time.monotonic() + 15

while time.monotonic() < end:
    ok, frame = capture.read()
    if not ok:
        continue
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if previous is not None:
        motion.append(float(cv2.absdiff(gray, previous).mean()))
    previous = gray
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    score = float(faces[:, 14].max()) if faces is not None and len(faces) else 0.0
    best = max(best, score)
    for f in (faces if faces is not None else []):
        x, y, fw, fh = (int(v) for v in f[:4])
        cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 200, 0), 2)
    cv2.putText(frame, f"Rostro: {score:.2f}  Movimiento: {motion[-1] if motion else 0:.1f}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.imshow("Que ve la camara? (15 s, Q para salir)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

capture.release()
cv2.destroyAllWindows()
print(f"Movimiento promedio entre frames: {np.mean(motion) if motion else 0:.2f}  (cerca de 0 = imagen fija/camara bloqueada)")
print(f"Mejor puntaje de rostro: {best:.2f}")
