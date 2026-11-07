from django.test import SimpleTestCase

from assistant_chat import services
from assistant_chat.robust import correct


class TypoCorrectionTests(SimpleTestCase):
    def test_corrige_solo_lo_que_esta_mal_escrito(self):
        self.assertIn("mas vendido", correct("que es lo mas vendidp", services.STAFF_RULES))
        self.assertEqual(correct("cual es el ticket promedio", services.STAFF_RULES), "cual es el ticket promedio")

    def test_errores_de_tipeo_frecuentes(self):
        for message, expected in (("¿Cómo va la cosina?", "kitchen_queue"),
                                  ("estado de las mezas", "floor_status"),
                                  ("¿Cuál es el tiket promedio?", "average_ticket")):
            self.assertEqual(services.classify_intent(message, "STAFF"), expected, message)

from assistant_chat.robust import edit_distance  # noqa: E402


class EditDistanceTests(SimpleTestCase):
    def test_distancia_de_edicion(self):
        self.assertEqual(edit_distance("cosina", "cocina"), 1)
        self.assertEqual(edit_distance("tikcet", "ticket"), 1)
        self.assertEqual(edit_distance("comida", "cocina"), 2)

    def test_no_corrige_palabras_distintas(self):
        self.assertNotIn("cocina", correct("la comida estuvo rica", services.STAFF_RULES))
