"""
Detección local de mesas y personas en una imagen, un video o la webcam, con resultados en JSON.

Ejemplos:
  python manage.py detect_scene foto.jpg --output resultado.json
  python manage.py detect_scene video.mp4 --every 1.0 --output video.json
  python manage.py detect_scene foto.jpg --compare roboflow.json
  python manage.py detect_scene 0 --seconds 20 --every 2        (webcam)

Las imágenes y videos se procesan en memoria. Solo con --annotate se guarda una copia
con recuadros, pensada para material de prueba con autorización.
"""
import json
import statistics
from datetime import datetime
from pathlib import Path

import cv2
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_vision.services.scene_detector import (
    DEFAULT_CONFIDENCE, DEFAULT_IOU, SceneDetector, SceneModelNotAvailable, assign_people_to_tables,
    compare_with_reference, draw,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _summary(frame_results, times):
    people = [r["counts"]["person"] for r in frame_results]
    tables = [r["counts"]["dining_table"] for r in frame_results]
    ordered = sorted(times)
    return {
        "frames_analyzed": len(frame_results),
        "people_median": statistics.median(people) if people else 0,
        "people_max": max(people, default=0),
        "tables_median": statistics.median(tables) if tables else 0,
        "inference_ms_avg": round(statistics.mean(times), 1) if times else None,
        "inference_ms_p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1) if ordered else None,
    }


def _pct(value):
    return "—" if value is None else f"{value}%"


class Command(BaseCommand):
    help = "Detecta mesas y personas con el modelo local YOLO26 y genera resultados JSON."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Ruta de imagen o video, o índice de cámara (por ejemplo 0).")
        parser.add_argument("--output", help="Archivo JSON de salida.")
        parser.add_argument("--conf", type=float, default=DEFAULT_CONFIDENCE, help="Umbral de confianza (0.17).")
        parser.add_argument("--iou", type=float, default=DEFAULT_IOU, help="Umbral de NMS (0.45).")
        parser.add_argument("--every", type=float, default=1.0, help="Segundos entre análisis en video (1.0).")
        parser.add_argument("--seconds", type=float, default=0, help="Duración máxima para video o cámara.")
        parser.add_argument("--engine", choices=["auto", "onnxruntime", "opencv"], default="opencv",
                            help="Motor de inferencia (por defecto OpenCV DNN; onnxruntime es más rápido si el equipo lo soporta).")
        parser.add_argument("--compare", help="JSON de Roboflow de la misma imagen, para medir equivalencia.")
        parser.add_argument("--annotate", help="Guardar imagen o video con recuadros (solo material de prueba).")

    def handle(self, *args, **options):
        try:
            detector = SceneDetector(confidence=options["conf"], iou=options["iou"], engine=options["engine"])
        except SceneModelNotAvailable as error:
            raise CommandError(str(error))

        source = str(options["source"])
        is_camera = source.isdigit()
        path = None if is_camera else Path(source)
        if path is not None and not path.exists():
            raise CommandError(f"No existe el archivo {source}.")

        result = {
            "model": detector.model_path.name, "engine": detector.engine,
            "confidence_threshold": options["conf"], "iou_threshold": options["iou"],
            "source": source, "generated_at": timezone.localtime().isoformat(timespec="seconds"),
        }

        if path is not None and path.suffix.lower() in IMAGE_EXTENSIONS:
            image = cv2.imread(str(path))
            if image is None:
                raise CommandError(f"No se pudo leer la imagen {source}.")
            detections, elapsed = detector.detect(image)
            result.update(self._frame(detections, elapsed, 0.0, image.shape))
            if options["annotate"]:
                cv2.imwrite(options["annotate"], draw(image, detections))
            del image
            if options["compare"]:
                reference = json.loads(Path(options["compare"]).read_text(encoding="utf-8-sig"))
                reference = reference.get("predictions", reference) if isinstance(reference, dict) else reference
                result["comparison"] = compare_with_reference(detections, reference)
            self._report_image(result)
        else:
            result.update(self._video(detector, int(source) if is_camera else str(path), options))
            self._report_video(result)

        if options["output"]:
            Path(options["output"]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Resultados guardados en {options['output']}"))

    @staticmethod
    def _frame(detections, elapsed, timestamp, shape):
        counts = {"dining_table": 0, "person": 0}
        for d in detections:
            counts[d["class"]] = counts.get(d["class"], 0) + 1
        return {
            "timestamp_s": round(timestamp, 2), "image": {"width": shape[1], "height": shape[0]},
            "inference_ms": round(elapsed, 1), "counts": counts,
            "assignment": assign_people_to_tables(detections), "predictions": detections,
        }

    def _video(self, detector, source, options):
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            raise CommandError(f"No se pudo abrir la fuente de video {source}.")
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(fps * options["every"])))
        writer, frames, times, index = None, [], [], 0
        started = datetime.now()
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp = index / fps
                if options["seconds"] and timestamp > options["seconds"]:
                    break
                if index % step == 0:
                    detections, elapsed = detector.detect(frame)
                    times.append(elapsed)
                    frames.append(self._frame(detections, elapsed, timestamp, frame.shape))
                    if options["annotate"]:
                        if writer is None:
                            writer = cv2.VideoWriter(options["annotate"], cv2.VideoWriter_fourcc(*"mp4v"),
                                                     max(1.0, 1.0 / options["every"]), (frame.shape[1], frame.shape[0]))
                        writer.write(draw(frame, detections))
                    self.stdout.write(f"  t={timestamp:6.1f}s  personas={frames[-1]['counts']['person']:>2}  "
                                      f"mesas={frames[-1]['counts']['dining_table']:>2}  {elapsed:.0f} ms")
                index += 1
                del frame
        finally:
            capture.release()
            if writer is not None:
                writer.release()
        return {"fps_source": round(fps, 2), "every_s": options["every"],
                "duration_s": round((datetime.now() - started).total_seconds(), 1),
                "summary": _summary(frames, times), "frames": frames}

    def _report_image(self, result):
        counts = result["counts"]
        self.stdout.write(f"Motor: {result['engine']} | Inferencia: {result['inference_ms']:.0f} ms")
        self.stdout.write(f"Personas: {counts['person']} | Mesas: {counts['dining_table']} | "
                          f"Personas sin mesa asignada: {result['assignment']['people_unassigned']}")
        for table in result["assignment"]["tables"]:
            self.stdout.write(f"  Mesa detectada {table['table_index'] + 1}: {table['people']} persona(s)")
        if "comparison" in result:
            c = result["comparison"]
            self.stdout.write(f"Comparación con Roboflow: {c['matches']} de {c['reference']} detecciones coinciden "
                              f"(recall {_pct(c['recall_vs_reference'])}, precisión {_pct(c['precision_vs_reference'])}, "
                              f"IoU medio {c['mean_iou'] if c['mean_iou'] is not None else '—'})")

    def _report_video(self, result):
        s = result["summary"]
        self.stdout.write(f"Motor: {result['engine']} | Fotogramas analizados: {s['frames_analyzed']} | "
                          f"Inferencia media {s['inference_ms_avg']} ms (p95 {s['inference_ms_p95']} ms)")
        self.stdout.write(f"Personas: mediana {s['people_median']}, máximo {s['people_max']} | "
                          f"Mesas: mediana {s['tables_median']}")
