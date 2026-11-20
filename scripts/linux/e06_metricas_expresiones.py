"""
E06 (Tabla 12.4, KPI-01 y KPI-02): métricas del componente de expresiones sobre el conjunto propio.

Antes: carga las muestras etiquetadas (con consentimiento) desde la sección de entrenamiento de la
plataforma. Este script solo lee la base; no modifica nada ni activa calibraciones.

Uso:  venv/bin/python scripts/linux/e06_metricas_expresiones.py

Grupos usados para KPI-01 (según el signo de la valencia de la plataforma):
  positivo = alegría, sorpresa;  neutral = neutral;  negativo = tristeza, enojo, disgusto, miedo, desprecio.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
import numpy as np  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from ai_vision.services import training  # noqa: E402
from ai_vision.services.vision_pipeline import EMOTION_ORDER, EMOTION_VALENCE  # noqa: E402

SALIDA = RAIZ / "evidencias" / "E06"


def grupo(e):
    v = EMOTION_VALENCE.get(e, 0.0)
    return "positivo" if v > 0 else "negativo" if v < 0 else "neutral"


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    muestras = training.expression_samples()
    if not muestras:
        raise SystemExit("No hay muestras de expresión etiquetadas en la base.")
    y = np.array([s.label for s in muestras])
    P = np.array([s.probabilities for s in muestras], dtype=float)
    por_clase = Counter(y)
    base = np.array([EMOTION_ORDER[int(np.argmax(p))] for p in P])

    validas = [c for c, n in por_clase.items() if n >= 2]
    mask = np.isin(y, validas)
    pliegues = max(2, min(5, min(por_clase[c] for c in validas)))
    X = np.log(np.clip(P[mask], 1e-6, 1.0))
    cal = cross_val_predict(LogisticRegression(max_iter=2000, class_weight="balanced"), X, y[mask],
                            cv=StratifiedKFold(n_splits=pliegues, shuffle=True, random_state=7))
    yv, bv = y[mask], base[mask]

    def metr(real, pred):
        g_r, g_p = [grupo(e) for e in real], [grupo(e) for e in pred]
        return {"exactitud_8": float(np.mean(real == pred)),
                "exactitud_3": float(np.mean(np.array(g_r) == np.array(g_p))),
                "f1_macro_3": float(f1_score(g_r, g_p, average="macro"))}

    sin, con = metr(yv, bv), metr(yv, cal)
    mejora = 100 * (con["exactitud_3"] - sin["exactitud_3"])
    datos = {"fecha": datetime.now().isoformat(timespec="minutes"), "muestras": int(len(y)),
             "muestras_por_clase": dict(por_clase), "clases_evaluadas": validas, "pliegues": pliegues,
             "sin_calibracion": sin, "con_calibracion": con, "mejora_pp_3_grupos": round(mejora, 1)}
    (SALIDA / "metricas_expresiones.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    f = lambda x: f"{x:.2f}".replace(".", ",")
    clases = "; ".join(f"{c} {n}" for c, n in sorted(por_clase.items()))
    lineas = ["TABLA 12.4: COMPONENTE DE EXPRESIONES (conjunto propio)",
              f"Muestras etiquetadas: {len(y)} ({clases})",
              f"{'Métrica':<34}{'Sin calibración':>17}{'Con calibración':>17}",
              f"{'Exactitud en 8 clases':<34}{f(sin['exactitud_8']):>17}{f(con['exactitud_8']):>17}",
              f"{'Exactitud en 3 grupos (KPI-01)':<34}{f(sin['exactitud_3']):>17}{f(con['exactitud_3']):>17}   meta ≥ 0,70",
              f"{'F1 macro en 3 grupos':<34}{f(sin['f1_macro_3']):>17}{f(con['f1_macro_3']):>17}",
              f"{'Mejora por calibración (KPI-02)':<34}{'—':>17}{(f'{mejora:.1f} p.p.').replace('.', ','):>17}   meta ≥ 5 p.p.",
              "", f"Validación cruzada estratificada de {pliegues} pliegues (regresión logística sobre FER+, como la plataforma).",
              "Si alguna clase tiene menos de 10 muestras, dilo en la observación de la tabla."]
    (SALIDA / "resumen.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
