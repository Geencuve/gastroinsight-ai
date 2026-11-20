"""
E07 / E26 (PR-REN-01, Tabla 9.6): latencia por fotograma de cada componente visual.

Mide cuatro escenarios sobre los mismos fotogramas:
  1. Haar Cascade (referencia)
  2. YuNet (umbral 0,70)
  3. YuNet + FER+ (pipeline completo de la v1)
  4. YOLO26s + YuNet + FER+ (pipeline v2.0.0), si está el modelo del equipo

Los fotogramas se procesan solo en memoria: no se guarda ninguna imagen.

Uso (desde la carpeta del proyecto):
  venv/bin/python scripts/linux/e07_medir_latencia.py --camara 0
  venv/bin/python scripts/linux/e07_medir_latencia.py --video ruta/al/video.mp4
Opciones: --fotogramas 1000 --calentamiento 100
"""
import argparse
import importlib.util
import json
import platform
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
MODELOS = RAIZ / "ai_vision" / "ml_models"
SALIDA = RAIZ / "evidencias" / "E07"


def softmax(v):
    e = np.exp(v - np.max(v))
    return e / e.sum()


def abrir_fuente(args):
    if args.video:
        cap = cv2.VideoCapture(args.video)
    else:
        cap = cv2.VideoCapture(args.camara, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(args.camara)
    if not cap.isOpened():
        raise SystemExit("No se pudo abrir la cámara o el video.")
    return cap


def leer(cap, args):
    ok, frame = cap.read()
    if not ok and args.video:  # el video se repite si es más corto que la prueba
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = cap.read()
    if not ok:
        raise SystemExit("La fuente dejó de entregar fotogramas.")
    return frame


def cargar_yolo():
    ruta = RAIZ / "ai_vision" / "services" / "scene_detector.py"
    if not (MODELOS / "mesas_personas_yolo26s.onnx").exists():
        return None
    spec = importlib.util.spec_from_file_location("scene_detector", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SceneDetector(engine="auto")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--camara", type=int, default=0)
    p.add_argument("--video")
    p.add_argument("--fotogramas", type=int, default=1000)
    p.add_argument("--calentamiento", type=int, default=100)
    p.add_argument("--ancho", type=int, default=640, help="ancho máximo para la detección (igual que la plataforma)")
    args = p.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)

    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    yunet = cv2.FaceDetectorYN.create(str(MODELOS / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.70, 0.3, 50)
    fer = cv2.dnn.readNetFromONNX(str(MODELOS / "emotion-ferplus-8.onnx"))
    yolo = cargar_yolo()

    def reducir(frame):
        h, w = frame.shape[:2]
        s = min(1.0, args.ancho / w)
        return (cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else frame), s

    def t_haar(frame):
        small, _ = reducir(frame)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        t = time.perf_counter()
        haar.detectMultiScale(gray, 1.1, 5)
        return (time.perf_counter() - t) * 1000

    def yunet_fer(frame, clasificar):
        small, s = reducir(frame)
        yunet.setInputSize((small.shape[1], small.shape[0]))
        _, caras = yunet.detect(small)
        if clasificar and caras is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            H, W = gray.shape
            for c in caras:
                x, y, w, h = (int(v / s) for v in c[:4])
                x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
                if x1 - x0 < 20 or y1 - y0 < 20:
                    continue
                crop = cv2.resize(gray[y0:y1, x0:x1], (64, 64))
                fer.setInput(crop.reshape(1, 1, 64, 64).astype(np.float32))
                softmax(fer.forward()[0])
        return 0 if caras is None else len(caras)

    def t_yunet(frame):
        t = time.perf_counter(); yunet_fer(frame, False); return (time.perf_counter() - t) * 1000

    def t_pipeline(frame):
        t = time.perf_counter(); yunet_fer(frame, True); return (time.perf_counter() - t) * 1000

    def t_v2(frame):
        t = time.perf_counter(); yolo.detect(frame); yunet_fer(frame, True); return (time.perf_counter() - t) * 1000

    escenarios = [("Haar Cascade (referencia)", t_haar), ("YuNet (umbral 0,70)", t_yunet),
                  ("YuNet + FER+ (pipeline completo)", t_pipeline)]
    if yolo:
        escenarios.append(("YOLO26s + YuNet + FER+ (pipeline v2.0.0)", t_v2))
    else:
        print("AVISO: sin modelo YOLO26s; se omite el escenario v2.0.0 (E26).")

    cap = abrir_fuente(args)
    resultados = []
    for nombre, fn in escenarios:
        print(f"Midiendo: {nombre} ...")
        for _ in range(args.calentamiento):
            fn(leer(cap, args))
        tiempos, t0 = [], time.perf_counter()
        for _ in range(args.fotogramas):
            tiempos.append(fn(leer(cap, args)))
        total = time.perf_counter() - t0
        q = np.percentile(tiempos, [50, 95])
        resultados.append({"componente": nombre, "fotogramas": len(tiempos),
                           "mediana_ms": round(float(q[0]), 1), "p95_ms": round(float(q[1]), 1),
                           "media_ms": round(statistics.mean(tiempos), 1),
                           "fps_medidos": round(len(tiempos) / total, 1)})
    cap.release()

    def cmd(c):
        try:
            return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
        except Exception:
            return ""
    cpu = cmd("lscpu | grep 'Model name' | sed 's/Model name:\\s*//'") or platform.processor()
    ram = cmd("free -h | awk '/Mem:/ {print $2}'")
    equipo = f"{cpu}; RAM {ram}; {platform.system()} {platform.release()}; OpenCV {cv2.__version__}"
    fuente = args.video or f"cámara {args.camara}"
    datos = {"fecha": datetime.now().isoformat(timespec="minutes"), "fuente": fuente, "equipo": equipo,
             "calentamiento": args.calentamiento, "resultados": resultados}
    (SALIDA / "medir_latencia_resumen.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    lineas = ["TABLA 9.6: LATENCIA POR COMPONENTE", f"Fecha: {datos['fecha']}   Fuente: {fuente}", f"Equipo: {equipo}", "",
              f"{'Componente':<44}{'Mediana':>9}{'P95':>9}{'FPS':>8}"]
    for r in resultados:
        lineas.append(f"{r['componente']:<44}{r['mediana_ms']:>7} ms{r['p95_ms']:>7} ms{r['fps_medidos']:>8}")
    pipe = next(r for r in resultados if r["componente"].startswith("YuNet + FER+"))
    ok = pipe["p95_ms"] <= 200
    lineas += ["", "FICHA PR-REN-01 (Resultado obtenido):",
               f"Percentil 95 del pipeline completo: {str(pipe['p95_ms']).replace('.', ',')} ms con una fuente "
               f"({'aprobada' if ok else 'no aprobada'}; criterio ≤ 200 ms). Mediciones de "
               f"{args.fotogramas} fotogramas tras {args.calentamiento} de calentamiento, el {datos['fecha'][:10]}; "
               "evidencia en evidencias/E07/medir_latencia_resumen.json."]
    (SALIDA / "resumen.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
