"""
E08 (PR-PRV-05, Tabla 18.137): búsqueda de imágenes persistidas en todas las rutas.

Paso 1, antes del análisis:     venv/bin/python scripts/linux/e08_inventario_imagenes.py antes
Paso 2: usa la plataforma 10 minutos con una cámara en análisis, revoca la autorización
        a mitad de camino y reinicia la aplicación (como dice la ficha).
Paso 3, después del análisis:   venv/bin/python scripts/linux/e08_inventario_imagenes.py despues

Busca archivos de imagen por extensión y por contenido (firma del archivo) en la carpeta del
programa, la de medios, la temporal del sistema y la caché del usuario. Los recortes consentidos
de entrenamiento (media/training/) se informan aparte y no cuentan como hallazgo.
"""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "evidencias" / "E08"
RUTAS = [RAIZ, Path(os.environ.get("MEDIA_ROOT", RAIZ / "media")), Path(tempfile.gettempdir()),
         Path.home() / ".cache"]
EXCLUIR = {"venv", ".git", "node_modules", "__pycache__", "static", "staticfiles", "evidencias"}
EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".npy", ".raw"}
FIRMAS = [b"\xff\xd8\xff", b"\x89PNG", b"BM", b"GIF8", b"RIFF", b"II*\x00", b"MM\x00*"]


def es_imagen(p):
    if p.suffix.lower() in EXT:
        return True
    try:
        with open(p, "rb") as f:
            cab = f.read(8)
        return any(cab.startswith(s) for s in FIRMAS if s != b"BM") or (cab.startswith(b"BM") and p.stat().st_size > 1000)
    except OSError:
        return False


def inventario():
    vistos = {}
    for base in RUTAS:
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUIR]
            for n in filenames:
                p = Path(dirpath) / n
                try:
                    if p.is_file() and p.stat().st_size > 0 and es_imagen(p):
                        st = p.stat()
                        vistos[str(p)] = {"bytes": st.st_size, "modificado": st.st_mtime}
                except OSError:
                    pass
    return vistos


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("antes", "despues"):
        raise SystemExit(__doc__)
    SALIDA.mkdir(parents=True, exist_ok=True)
    modo = sys.argv[1]
    inv = inventario()
    (SALIDA / f"inventario_{modo}.json").write_text(json.dumps(
        {"fecha": datetime.now().isoformat(timespec="seconds"), "rutas": [str(r) for r in RUTAS], "archivos": inv},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Inventario '{modo}': {len(inv)} archivos de imagen en {len(RUTAS)} rutas.")
    if modo == "antes":
        print("Ahora usa la plataforma según la ficha y luego ejecuta este script con 'despues'.")
        return
    previo = json.loads((SALIDA / "inventario_antes.json").read_text(encoding="utf-8"))
    antes, inicio = previo["archivos"], datetime.fromisoformat(previo["fecha"]).timestamp()
    nuevos = {p: d for p, d in inv.items() if p not in antes or d["modificado"] > inicio}
    consentidos = {p: d for p, d in nuevos.items() if "/media/training/" in p.replace("\\", "/")}
    hallazgos = {p: {**d, "sha256": sha(p)} for p, d in nuevos.items() if p not in consentidos}
    lineas = ["FICHA PR-PRV-05: BÚSQUEDA DE IMÁGENES", f"Inicio: {previo['fecha']}   Fin: {datetime.now().isoformat(timespec='seconds')}",
              "Rutas revisadas:"] + [f"  - {r}" for r in previo["rutas"]] + [
              f"Archivos de imagen nuevos o modificados: {len(nuevos)}",
              f"  Recortes consentidos (media/training): {len(consentidos)}",
              f"  Hallazgos fuera de los recortes consentidos: {len(hallazgos)}"]
    lineas += [f"    {p} ({d['bytes']} bytes, sha256 {d['sha256'][:16]}...)" for p, d in hallazgos.items()]
    lineas += ["", "Texto para la ficha (Resultado obtenido):",
               (f"{'Aprobada' if not hallazgos else 'No aprobada'}: {len(hallazgos)} archivos de imagen fuera de los recortes "
                f"consentidos tras el procesamiento, en {len(previo['rutas'])} rutas revisadas (programa, medios, temporal "
                f"y caché del usuario). Límite de la prueba: no se revisó la memoria de intercambio ni otras particiones. "
                "Inventario por ruta en evidencias/E08.")]
    (SALIDA / "resumen.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
