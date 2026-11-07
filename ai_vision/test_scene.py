import io
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from django.core.management import call_command
from django.test import SimpleTestCase

from ai_vision.services.scene_detector import (
    MODELS_DIR, SCENE_MODEL_FILE, assign_people_to_tables, compare_with_reference, postprocess,
)

MODEL_READY = (MODELS_DIR / SCENE_MODEL_FILE).exists()


def synthetic_output():
    out = np.zeros((1, 6, 8400), np.float32)
    out[0, :4, 0] = [320, 320, 100, 50]; out[0, 4, 0] = 0.9    # mesa
    out[0, :4, 1] = [322, 321, 98, 52]; out[0, 4, 1] = 0.8     # duplicado de la mesa (NMS lo elimina)
    out[0, :4, 2] = [320, 250, 40, 120]; out[0, 5, 2] = 0.7    # persona
    out[0, :4, 3] = [100, 100, 10, 10]; out[0, 5, 3] = 0.1     # bajo el umbral
    return out


class SceneDetectorTests(SimpleTestCase):
    def test_postproceso_escala_filtra_y_aplica_nms(self):
        detections = postprocess(synthetic_output(), 1280, 720)
        self.assertEqual(len(detections), 2)
        table = next(d for d in detections if d["class"] == "dining_table")
        self.assertEqual((table["x"], table["y"], table["width"]), (640.0, 360.0, 200.0))
        self.assertEqual(table["confidence"], 0.9)

    def test_asigna_personas_a_la_mesa_mas_cercana(self):
        assignment = assign_people_to_tables(postprocess(synthetic_output(), 1280, 720))
        self.assertEqual(assignment["tables"][0]["people"], 1)
        self.assertEqual(assignment["people_unassigned"], 0)

    def test_comparacion_con_resultados_de_roboflow(self):
        local = postprocess(synthetic_output(), 1280, 720)
        reference = [dict(d) for d in local]
        result = compare_with_reference(local, reference)
        self.assertEqual(result["matches"], 2)
        self.assertEqual(result["recall_vs_reference"], 100.0)

    def test_comando_con_imagen_genera_json(self):
        if not MODEL_READY:
            self.skipTest("Modelo de mesas y personas no copiado")
        with tempfile.TemporaryDirectory() as folder:
            image, output = Path(folder) / "sala.jpg", Path(folder) / "resultado.json"
            cv2.imwrite(str(image), np.full((480, 640, 3), 180, np.uint8))
            call_command("detect_scene", str(image), output=str(output), stdout=io.StringIO())
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn(data["engine"], ("onnxruntime", "opencv-dnn"))
            self.assertIn("predictions", data)
            self.assertIn("person", data["counts"])

    def test_comando_con_video_resume_fotogramas(self):
        if not MODEL_READY:
            self.skipTest("Modelo de mesas y personas no copiado")
        with tempfile.TemporaryDirectory() as folder:
            video, output = Path(folder) / "sala.mp4", Path(folder) / "video.json"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
            for i in range(20):
                writer.write(np.full((240, 320, 3), i * 10, np.uint8))
            writer.release()
            call_command("detect_scene", str(video), every=1.0, output=str(output), stdout=io.StringIO())
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["frames_analyzed"], 2)
