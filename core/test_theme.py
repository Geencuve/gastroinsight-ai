from django.test import TestCase


class ThemeTests(TestCase):
    def test_base_incluye_sistema_visual_y_selector_de_tema(self):
        response = self.client.get("/")
        self.assertContains(response, "css/theme.css")
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, "data-theme")
