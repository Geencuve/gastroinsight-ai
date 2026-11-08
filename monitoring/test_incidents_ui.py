"""Incidencias: la plataforma carga el script de mosaicos, filtros y grupos por día."""
from django.test import TestCase


class IncidentsUiTests(TestCase):
    def test_base_carga_script_de_incidencias(self):
        self.assertContains(self.client.get("/legal/acerca/"), "js/incidents.js")