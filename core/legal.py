"""Datos de la sección legal. Cambiar LEGAL_VERSION obliga a todos a aceptar de nuevo."""
LEGAL_VERSION = "1.0"
LEGAL_DATE = "29 de octubre de 2026"
TEAM = ["Gustavo Contreras", "Gerardo Cuellar", "Esteban Burgos"]
ADVISOR = "Teresa Jesús Tapia Soto"
COURSE = "Proyecto de Título · Sección TIHI84 · Área de Informática y Telecomunicaciones"

PAGES = {
    "acerca": ("Acerca de nosotros", "core/legal/acerca.html"),
    "terminos": ("Términos y condiciones", "core/legal/terminos.html"),
    "privacidad": ("Política de privacidad", "core/legal/privacidad.html"),
    "uso-educativo": ("Aviso de uso educativo", "core/legal/uso_educativo.html"),
    "contacto": ("Contacto", "core/legal/contacto.html"),
}
URL_NAMES = {"acerca": "legal_about", "terminos": "legal_terms", "privacidad": "legal_privacy",
             "uso-educativo": "legal_education", "contacto": "legal_contact"}

LICENSES = [
    ("Django", "Framework web", "BSD-3-Clause"),
    ("OpenCV", "Procesamiento de video y ejecución de modelos", "Apache 2.0"),
    ("YuNet (OpenCV Zoo)", "Detección de rostros", "MIT"),
    ("FER+ (ONNX Model Zoo)", "Estimación de expresiones", "MIT"),
    ("NumPy y SciPy", "Cálculo numérico y estadística", "BSD-3-Clause"),
    ("scikit-learn", "Calibración del modelo", "BSD-3-Clause"),
    ("Pillow", "Imágenes de platos y promociones", "MIT-CMU"),
    ("ReportLab", "Reportes en PDF", "BSD"),
    ("Chart.js", "Gráficos", "MIT"),
    ("pywebview", "Ventana de escritorio", "BSD-3-Clause"),
    ("segno", "Códigos QR", "BSD-3-Clause"),
    ("waitress", "Servidor de la versión de escritorio", "ZPL 2.1"),
    ("Inter y Space Grotesk", "Tipografías", "SIL Open Font License 1.1"),
]
