import io

import numpy as np
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from ai_vision.models import CalibrationModel, TrainingSample
from ai_vision.services import training
from ai_vision.services.vision_pipeline import FERPLUS_FILE, MODELS_DIR, YUNET_FILE, calibrated_emotion
from authentication.models import Profile

MODELS_READY = (MODELS_DIR / YUNET_FILE).exists() and (MODELS_DIR / FERPLUS_FILE).exists()


def probs(neutral, happy):
    rest = max(0.0, 1.0 - neutral - happy) / 6
    return [neutral, happy, rest, rest, rest, rest, rest, rest]


class TrainingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefa", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.admin)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.operator = User.objects.create_user("mesero", password="Test12345!")
        op_profile, _ = Profile.objects.get_or_create(user=self.operator)
        op_profile.role = Profile.Role.OPERATOR
        op_profile.save()

    def _sample(self, label, p, kind="expression", yaw=None):
        return TrainingSample.objects.create(kind=kind, label=label, probabilities=p, yaw=yaw, consent_confirmed=True)

    def test_matriz_de_confusion(self):
        for _ in range(3):
            self._sample("neutral", probs(0.8, 0.1))
            self._sample("happy", probs(0.7, 0.2))
        evaluation = training.evaluate_expression()
        self.assertEqual(evaluation["accuracy"], 50.0)
        happy_row = next(r for r in evaluation["rows"] if r["label"] == "Alegría")
        self.assertEqual(happy_row["recall"], 0.0)

    def test_calibracion_mejora_la_precision(self):
        rng = np.random.default_rng(3)
        for _ in range(8):
            self._sample("happy", probs(0.6 + rng.uniform(-0.05, 0.05), 0.3))
            self._sample("neutral", probs(0.85 + rng.uniform(-0.05, 0.05), 0.05))
        calibration = training.train_expression_calibration(self.admin)
        self.assertGreater(calibration.accuracy_after, calibration.accuracy_before)
        training.activate_calibration(calibration)
        self.assertTrue(CalibrationModel.objects.get(pk=calibration.pk).active)
        label, _, _ = calibrated_emotion(probs(0.6, 0.3), calibration.weights)
        self.assertEqual(label, "happy")

    def test_calibracion_exige_datos_minimos(self):
        self._sample("happy", probs(0.6, 0.3))
        with self.assertRaises(ValueError):
            training.train_expression_calibration(self.admin)

    def test_umbral_de_atencion_sugerido(self):
        for yaw in (0.02, 0.05, 0.08, 0.10):
            self._sample("attentive", [], kind="attention", yaw=yaw)
        for yaw in (0.18, 0.22, 0.26, 0.30):
            self._sample("seeking", [], kind="attention", yaw=yaw)
        evaluation = training.evaluate_attention()
        self.assertTrue(evaluation["can_suggest"])
        self.assertEqual(evaluation["suggested_accuracy"], 100.0)
        self.assertLess(evaluation["suggested"], 0.2)

    def test_pagina_solo_para_administradores(self):
        self.client.force_login(self.admin)
        response = self.client.get("/ai/entrenamiento/")
        self.assertContains(response, "Ingresar datos para entrenamiento")
        self.assertContains(response, "consentimiento informado")
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get("/ai/entrenamiento/").status_code, 403)

    def test_carga_sin_consentimiento_es_rechazada(self):
        self.client.force_login(self.admin)
        image = SimpleUploadedFile("cara.png", b"no-es-imagen", content_type="image/png")
        response = self.client.post("/ai/entrenamiento/", {"kind": "expression", "label": "happy", "images": [image]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrainingSample.objects.exists())

    def test_imagen_sin_rostro_no_se_guarda(self):
        if not MODELS_READY:
            self.skipTest("Modelos no descargados")
        buffer = io.BytesIO()
        Image.new("RGB", (200, 200), (240, 240, 240)).save(buffer, "PNG")
        image = SimpleUploadedFile("pared.png", buffer.getvalue(), content_type="image/png")
        self.client.force_login(self.admin)
        response = self.client.post("/ai/entrenamiento/", {
            "kind": "expression", "label": "happy", "images": [image], "consent": "on",
        }, follow=True)
        self.assertContains(response, "no se detectó un rostro")
        self.assertFalse(TrainingSample.objects.exists())
