"""Auditoría: la plataforma carga el script de filtros instantáneos y grupos por día."""
from django.test import TestCase


class AuditUiTests(TestCase):
    def test_base_carga_script_de_auditoria(self):
        self.assertContains(self.client.get("/legal/acerca/"), "js/audit.js")