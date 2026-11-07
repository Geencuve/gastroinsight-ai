"""
Definición formal de los índices de GastroInsight AI.

IBE (Índice de Balance de Expresiones): promedio de la valencia de los rostros de la mesa.
    Cada rostro aporta el promedio ponderado de las 8 probabilidades de FER+ (pesos positivos para
    expresiones positivas, cero para neutral y negativos para las negativas). Rango: -1 a +1.
IEO (Índice de Experiencia Observable): 0,60·50(IBE+1) + 0,25·100(1−min(2a, 1)) + 0,15·espera,
    donde a es la proporción de rostros buscando atención y la espera resta desde los 10 minutos. Rango: 0 a 100.
"""
from django.db.models import Avg

INDEX_DEFINITIONS = [
    {"code": "IBE", "name": "Índice de Balance de Expresiones", "range": "−1 a +1",
     "formula": "Promedio de la valencia de los rostros: probabilidades de FER+ ponderadas (positivas suman, neutral es cero, negativas restan).",
     "use": "Balance emocional observable de la mesa; se compara antes y después de entregar cada plato o bebida."},
    {"code": "IEO", "name": "Índice de Experiencia Observable", "range": "0 a 100",
     "formula": "60% IBE llevado a 0-100 + 25% búsqueda de atención invertida + 15% tiempo sin atención (resta desde los 10 min).",
     "use": "Estado de cada mesa en vivo, alertas del monitor y termómetro de caja."},
    {"code": "Ts", "name": "Tiempo de servicio", "range": "minutos",
     "formula": "Hora de cierre de la atención menos hora de apertura.",
     "use": "Variable independiente de la hipótesis H1."},
    {"code": "CSAT", "name": "Satisfacción declarada", "range": "1 a 5",
     "formula": "Promedio de las valoraciones del QR por atención y del personal.",
     "use": "Validación externa del IEO y del IBE."},
]


def session_ibe(session):
    from ai_vision.models import DetectionEvent

    value = DetectionEvent.objects.filter(service_session=session, valence__isnull=False).aggregate(v=Avg("valence"))["v"]
    return float(value) if value is not None else None
