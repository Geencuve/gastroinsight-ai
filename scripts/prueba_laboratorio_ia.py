"""
Prueba de laboratorio (Espiral 1): detector YuNet + clasificador FER+.

Mide latencia por fotograma, confianza del detector y distribución de
expresiones. Los fotogramas se procesan solo en memoria: no se guarda
ninguna imagen en disco.
"""
import argparse
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

MODELS = Path(__file__).resolve().parent.parent / "ai_vision" / "ml_models"
LABELS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]
ES = {
    "neutral": "neutral", "happiness": "alegria", "surprise": "sorpresa",
    "sadness": "tristeza", "anger": "enojo", "disgust": "disgusto",
    "fear": "miedo", "contempt": "desprecio",
}


def softmax(values):
    exp = np.exp(values - np.max(values))
    return exp / exp.sum()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--frames", type=int, default=150)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    print(f"OpenCV {cv2.__version__}")
    detector = cv2.FaceDetectorYN.create(
        str(MODELS / "face_detection_yunet_2023mar.onnx"), "", (320, 320), args.threshold, 0.3, 50,
    )
    fer = cv2.dnn.readNetFromONNX(str(MODELS / "emotion-ferplus-8.onnx"))

    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        raise SystemExit("No se pudo abrir la webcam (¿otra aplicación la está usando?)")

    latencies, det_conf, fer_conf = [], [], []
    emotions = Counter()
    frames_with_faces = 0
    frames = 0

    try:
        while frames < args.frames:
            ok, frame = capture.read()
            if not ok:
                print("No se pudo leer un fotograma")
                break
            frames += 1
            start = time.perf_counter()

            height, width = frame.shape[:2]
            detector.setInputSize((width, height))
            _, faces = detector.detect(frame)
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
                fer.setInput(crop.reshape(1, 1, 64, 64).astype(np.float32))
                probs = softmax(fer.forward()[0])
                index = int(np.argmax(probs))
                emotions[LABELS[index]] += 1
                det_conf.append(float(face[14]))
                fer_conf.append(float(probs[index]))
                results.append((x0, y0, x1, y1, LABELS[index], float(probs[index])))

            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            if results:
                frames_with_faces += 1

            if args.preview:
                for x0, y0, x1, y1, label, conf in results:
                    cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 200, 0), 2)
                    cv2.putText(frame, f"{ES[label]} {conf:.2f}", (x0, max(18, y0 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
                cv2.putText(frame, f"{elapsed_ms:.0f} ms | {frames}/{args.frames}", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.imshow("GastroInsight AI - Prueba de laboratorio (Q para salir)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            del frame, gray  # el fotograma se descarta: no se conserva en memoria ni disco
    finally:
        capture.release()
        cv2.destroyAllWindows()

    print("\n=== RESULTADOS PRUEBA DE LABORATORIO ===")
    print(f"Fotogramas analizados: {frames}")
    if frames:
        print(f"Fotogramas con rostro: {frames_with_faces} ({100 * frames_with_faces / frames:.1f}%)")
    print(f"Rostros clasificados: {sum(emotions.values())}")
    if latencies:
        steady = latencies[1:] or latencies
        under = 100 * sum(1 for v in steady if v < 200) / len(steady)
        print(f"Latencia por fotograma: promedio {np.mean(steady):.1f} ms | p95 {np.percentile(steady, 95):.1f} ms | "
              f"max {max(steady):.1f} ms | bajo 200 ms: {under:.1f}%")
        print(f"(primer fotograma, con carga del modelo: {latencies[0]:.1f} ms)")
    if det_conf:
        print(f"Confianza detector: promedio {np.mean(det_conf):.3f} | minima {min(det_conf):.3f} (umbral {args.threshold})")
        print(f"Confianza FER+: promedio {np.mean(fer_conf):.3f}")
        print("Distribucion de expresiones:")
        total = sum(emotions.values())
        for label, count in emotions.most_common():
            print(f"  {ES[label]:<10} {count:>4}  ({100 * count / total:.1f}%)")
    print("Fotogramas guardados en disco: 0 (procesamiento solo en memoria)")


if __name__ == "__main__":
    main()
