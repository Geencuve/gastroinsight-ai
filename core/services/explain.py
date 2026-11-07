"""
Transparencia de las recomendaciones: cada idea declara su tipo de cálculo, la fórmula y los datos usados.
Ninguna recomendación del inicio usa modelos predictivos: son reglas de negocio y estadística descriptiva.
"""
import re
import unicodedata

DESCRIPTIVE = "Estadística descriptiva"
ASSOCIATION = "Regla de asociación (análisis de canasta)"
CORRELATION = "Correlación estadística"
OPERATIONAL = "Regla operativa con umbral"

RULES = [
    (r"alegra a las mesas|reaccion negativa al servirlo|no convence", DESCRIPTIVE, "Variación del IBE al servir el plato",
     "Promedio del balance de expresiones (IBE) de la mesa después de recibir el plato menos el de antes. Requiere al menos 3 unidades.",
     "Métricas visuales agregadas por mesa y hora de entrega de cada plato"),
    (r"experiencia cae en la etapa", DESCRIPTIVE, "IEO promedio por etapa del journey",
     "Para cada atención, promedia el IEO en cada tramo (llegada y pedido, espera de platos, consumo, cuenta y pago) y compara las etapas.",
     "Métricas visuales por mesa, horas de confirmación, entrega, cuenta y pago (14 días)"),
    (r"se va sin sentarse", DESCRIPTIVE, "Tasa de abandono de la lista de espera",
     "Grupos que se retiraron sin sentarse ÷ grupos registrados en la lista de espera.", "Lista de espera (14 días)"),
    (r"se usan poco", DESCRIPTIVE, "Uso de cada mesa frente al promedio",
     "Mesas con menos del 40% de las atenciones promedio por mesa del local.", "Atenciones por mesa (28 días)"),
    (r"abiertas hace mas de 2 horas", OPERATIONAL, "Atenciones abiertas por más de 120 minutos",
     "Lista las mesas con atención abierta hace más de 2 horas.", "Atenciones (hora de inicio)"),
    (r"esperando pago", OPERATIONAL, "Pedidos confirmados sin pagar por más de 45 minutos",
     "Cuenta los pedidos confirmados hace más de 45 minutos que aún no se pagan.", "Pedidos (estado y hora de confirmación)"),
    (r"incidencia", OPERATIONAL, "Incidencias técnicas abiertas", "Cuenta las incidencias registradas sin resolver.", "Incidencias"),
    (r"crecieron|cayeron|bajaron|a la baja|subieron", DESCRIPTIVE, "Variación semanal de ventas",
     "Compara la suma de ventas pagadas de los últimos 7 días con los 7 días anteriores: (actual − anterior) ÷ anterior.",
     "Pedidos pagados de las últimas 2 semanas"),
    (r"postre|entrada", DESCRIPTIVE, "Proporción de mesas que piden una categoría",
     "Porcentaje de pedidos pagados (4 semanas) que incluyen al menos un plato de esa categoría.", "Platos de cada pedido pagado"),
    (r"combo|tambien pide", ASSOCIATION, "Confianza de la regla A → B",
     "De los pedidos que incluyen el plato A, porcentaje que también incluye el plato B (confianza del análisis de canasta).",
     "Platos de cada pedido pagado (4 semanas)"),
    (r"no son tu dia|dia mas flojo|flojo", DESCRIPTIVE, "Promedio de ventas por día de la semana",
     "Promedio de ventas de ese día frente a la mediana de los demás días. El potencial supone igualar un día típico.",
     "Pedidos pagados agrupados por día (4 semanas)"),
    (r"joya", DESCRIPTIVE, "Plato bien evaluado con pocas ventas",
     "Platos con nota promedio alta y unidades vendidas bajo la mediana de la carta.", "Evaluaciones y unidades vendidas (4 semanas)"),
    (r"tardes|happy hour|once", DESCRIPTIVE, "Ventas por franja horaria",
     "Compara las ventas de la franja de la tarde con el promedio de las demás franjas.", "Pedidos pagados por hora (4 semanas)"),
    (r"estrella", DESCRIPTIVE, "Plato con más unidades o ingresos",
     "Ordena los platos por unidades vendidas e ingresos y toma el primero.", "Platos vendidos (4 semanas)"),
    (r"casi no se venden|menos vendid", DESCRIPTIVE, "Platos con menos unidades",
     "Platos de la carta con menos unidades vendidas en el período.", "Platos vendidos (4 semanas)"),
    (r"esperan mas|menos contentas|espera", CORRELATION, "Relación entre espera y expresiones (Pearson y Spearman)",
     "Compara el porcentaje de expresiones positivas entre mesas con espera alta y baja, con su coeficiente de correlación.",
     "Tiempos de servicio y métricas visuales agregadas por mesa"),
    (r"malas evaluaciones|peor evaluad", DESCRIPTIVE, "Nota promedio por plato",
     "Platos con nota promedio bajo 3,5 y al menos 3 evaluaciones.", "Evaluaciones de clientes (4 semanas)"),
    (r"tarda mas", DESCRIPTIVE, "Duración promedio de la atención por mesa",
     "Mesa cuya duración promedio supera claramente la del resto.", "Atenciones cerradas"),
    (r"hora punta|reforzar", DESCRIPTIVE, "Hora con más atenciones",
     "Hora del día con más atenciones iniciadas en promedio.", "Atenciones (hora de inicio)"),
]


def _plain(text):
    text = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def method_for(item):
    title = _plain(f"{item.get('title', '')} {item.get('why', '')}")
    for pattern, kind, name, calc, data in RULES:
        if re.search(pattern, title):
            method = {"kind": kind, "name": name, "calc": calc, "data": data}
            break
    else:
        method = {"kind": DESCRIPTIVE, "name": "Regla de negocio sobre tus datos",
                  "calc": "Compara indicadores de tus ventas o atenciones con umbrales fijos.", "data": "Ventas y atenciones del local"}
    if item.get("impact"):
        method["impact_note"] = "El potencial es una estimación simple (diferencia × frecuencia), no una proyección financiera."
    return method


def annotate(result):
    """Agrega «method» a cada idea de cada sección."""
    sections = result.values() if isinstance(result, dict) else []
    for value in sections:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "title" in item:
                    item.setdefault("method", method_for(item))
    return result
