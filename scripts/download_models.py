"""Descarga los modelos de visión usados por GastroInsight AI."""
import hashlib
import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "ai_vision" / "ml_models"

MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "min_bytes": 100_000,
        "urls": [
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        ],
    },
    "emotion-ferplus-8.onnx": {
        "min_bytes": 30_000_000,
        "urls": [
            "https://huggingface.co/onnxmodelzoo/legacy_models/resolve/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
            "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
            "https://github.com/spmallick/learnopencv/raw/master/Facial-Emotion-Recognition/emotion-ferplus-8.onnx",
        ],
    },
}


def download(url, target):
    request = urllib.request.Request(url, headers={"User-Agent": "GastroInsightAI/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, info in MODELS.items():
        path = DEST / name
        if path.exists() and path.stat().st_size >= info["min_bytes"]:
            print(f"[ya existe] {name} ({path.stat().st_size / 1e6:.2f} MB)")
            continue
        part = path.with_suffix(".part")
        for url in info["urls"]:
            try:
                print(f"Descargando {name} desde {url.split('/')[2]} ...")
                download(url, part)
                if part.stat().st_size < info["min_bytes"]:
                    print(f"  archivo incompleto ({part.stat().st_size} bytes), probando otra fuente")
                    continue
                part.replace(path)
                sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
                print(f"[OK] {name} ({path.stat().st_size / 1e6:.2f} MB, sha256 {sha}...)")
                break
            except Exception as error:
                print(f"  fallo: {error}")
        else:
            print(f"[ERROR] No se pudo descargar {name}")
            ok = False
        if part.exists():
            part.unlink()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
